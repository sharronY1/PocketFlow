"""
Node definitions for Multi-Agent exploration system
"""
from pocketflow import Node
from utils import (
    call_llm,
    get_embedding,
    search_memory,
    add_to_memory,
)
from utils.vision import caption_image
from utils.perception_interface import PerceptionInterface
import yaml
import threading
import os

# Global lock to protect shared resources (message queue, etc.)
env_lock = threading.Lock()


class PerceptionNode(Node):
    """
    Perception node: Get current environment state
    
    Uses PerceptionInterface abstraction layer, supports switching between different perception implementations
    """
    
    def prep(self, shared):
        # Get perception interface from shared store
        perception = shared["perception"]
        agent_id = shared["agent_id"]
        position = shared["position"]
        
        return perception, agent_id, position
    
    def exec(self, prep_res):
        perception, agent_id, position = prep_res
        
        # Use perception interface to get visible objects
        # Note: Thread safety is handled by the perception implementation itself
        visible = perception.get_visible_objects(agent_id, position)
        
        return visible
    
    def post(self, shared, prep_res, exec_res):
        shared["visible_objects"] = exec_res
        # If unity screenshot path is present, generate a caption for downstream text-based retrieval
        # Example of exec_res: ["screenshot:E:/.../img.png"] or ["chair","table"] for mock
        caption = None
        if exec_res and isinstance(exec_res[0], str) and exec_res[0].startswith("screenshot:"):
            image_path = exec_res[0].split("screenshot:", 1)[1]
            caption = caption_image(image_path)
        shared["visible_caption"] = caption or ", ".join(map(str, exec_res))
        print(f"[{shared['agent_id']}] Position {shared['position']}: sees {exec_res}")
        print(f"[{shared['agent_id']}] Caption: {shared['visible_caption']}")
        return "default"


class RetrieveMemoryNode(Node):
    """Memory retrieval node: Retrieve relevant history from FAISS"""
    
    def prep(self, shared):
        visible_caption = shared.get("visible_caption") or ", ".join(map(str, shared.get("visible_objects", [])))
        position = shared["position"]
        
        # Construct query text using caption (works for both mock text and image-derived caption)
        query = f"What do I know about position {position} with what I see: {visible_caption}?"
        return query, shared["memory_index"], shared["memory_texts"]
    
    def exec(self, prep_res):
        query, index, memory_texts = prep_res
        
        # Get query vector
        query_emb = get_embedding(query)
        
        # Search memory
        results = search_memory(index, query_emb, memory_texts, top_k=3)
        
        return results
    
    def post(self, shared, prep_res, exec_res):
        shared["retrieved_memories"] = exec_res
        
        if exec_res:
            print(f"[{shared['agent_id']}] Retrieved {len(exec_res)} memories:")
            for i, (text, dist) in enumerate(exec_res[:2], 1):
                print(f"  {i}. {text[:80]}...")
        else:
            print(f"[{shared['agent_id']}] No memories found (first time)")
        
        return "default"


class CommunicationNode(Node):
    """Communication node: Read messages from other agents"""
    
    def prep(self, shared):
        return shared["agent_id"], shared["perception"]
    
    def exec(self, prep_res):
        agent_id, perception = prep_res
        try:
            messages = perception.poll_messages(agent_id)
        except Exception as e:
            print(f"[CommunicationNode] Error polling messages: {e}")
            messages = []
        return messages
    
    def post(self, shared, prep_res, exec_res):
        shared["other_agent_messages"] = exec_res
        
        if exec_res:
            print(f"[{shared['agent_id']}] Received {len(exec_res)} messages:")
            for msg in exec_res:
                print(f"  From {msg['sender']}: {msg['message']}")
        
        return "default"


class DecisionNode(Node):
    """Decision node: Decide next action based on context"""
    
    def prep(self, shared):
        # Collect all context needed for decision making
        context = {
            "agent_id": shared["agent_id"],
            "position": shared["position"],
            "visible_objects": shared["visible_objects"],
            "retrieved_memories": shared["retrieved_memories"],
            "other_agent_messages": shared["other_agent_messages"],
            "explored_objects": list(shared["explored_objects"]),
            "step_count": shared["step_count"]
        }
        return context
    
    def exec(self, context):
        # Optional offline mode: skip LLM when DISABLE_LLM is set
        if os.getenv("DISABLE_LLM"):
            action = "forward" if (context.get("step_count", 0) % 2 == 0) else "backward"
            return {
                "thinking": "LLM disabled for local validation.",
                "action": action,
                "reason": "Deterministic fallback decision without LLM.",
                "message_to_others": "Testing remote mode without LLM"
            }

        # Construct decision prompt
        memories_text = "\n".join([
            f"- {text[:100]}" 
            for text, _ in context["retrieved_memories"][:3]
        ]) if context["retrieved_memories"] else "No historical memories"
        
        messages_text = "\n".join([
            f"- {msg['sender']}: {msg['message']}"
            for msg in context["other_agent_messages"]
        ]) if context["other_agent_messages"] else "No messages from other agents"
        
        prompt = f"""You are {context['agent_id']}, an intelligent agent exploring an XR environment.

Current state:
- Position: {context['position']}
- Visible objects: {context['visible_objects']}
- Already explored objects: {context['explored_objects']}
- Steps taken: {context['step_count']}

Historical memories (relevant):
{memories_text}

Messages from other agents:
{messages_text}

Task goal: Explore as many new objects as possible, avoid revisiting already explored areas. Analize the screen shot and decide the next action.

Available actions:
- forward: Move to next position
- backward: Move to previous position
- move_left: Strafe left (key 'a')
- move_right: Strafe right (key 'd')
- move_up: Move up (key 'r')
- move_down: Move down (key 'f')
- look_left: Turn head left (left arrow)
- look_right: Turn head right (right arrow)
- look_up: Look up (up arrow)
- look_down: Look down (down arrow)
- tilt_left: Roll head left (key 'q')
- tilt_right: Roll head right (key 'e')

Please decide the next action based on the above information, output in YAML format:

```yaml
thinking: Your thought process (consider whether to explore new areas or areas already explored)
action: one of [forward, backward, move_left, move_right, move_up, move_down, look_left, look_right, look_up, look_down, tilt_left, tilt_right]
reason: Reason for choosing this action
message_to_others: Information to share with other agents (optional)
```
"""
        
        response = call_llm(prompt)
        
        # Parse YAML
        yaml_str = response.split("```yaml")[1].split("```")[0].strip()
        result = yaml.safe_load(yaml_str)
        
        # Validate required fields
        assert isinstance(result, dict), "Result must be a dictionary"
        assert "action" in result, "Missing action field"
        assert result["action"] in [
            "forward", "backward",
            "move_left", "move_right", "move_up", "move_down",
            "look_left", "look_right", "look_up", "look_down",
            "tilt_left", "tilt_right",
        ], f"Invalid action: {result['action']}"
        assert "reason" in result, "Missing reason field"
        
        return result
    
    def post(self, shared, prep_res, exec_res):
        shared["action"] = exec_res["action"]
        shared["action_reason"] = exec_res.get("reason", "")
        shared["message_to_others"] = exec_res.get("message_to_others", "")
        
        print(f"[{shared['agent_id']}] Decision: {exec_res['action']}")
        print(f"  Reason: {exec_res['reason']}")
        
        return "default"


class ExecutionNode(Node):
    """
    Execution node: Execute action and update environment
    
    Uses PerceptionInterface to execute actions, supports different environment implementations
    """
    
    def prep(self, shared):
        perception = shared["perception"]
        agent_id = shared["agent_id"]
        action = shared["action"]
        
        return perception, agent_id, action
    
    def exec(self, prep_res):
        perception, agent_id, action = prep_res
        
        # Use perception interface to execute action
        # Returns new state (including position, visible objects, etc.)
        new_state = perception.execute_action(agent_id, action)
        
        return new_state
    
    def post(self, shared, prep_res, exec_res):
        # Update position
        shared["position"] = exec_res["position"]
        shared["step_count"] += 1
        
        # Update visible objects (new position after execution)
        if "visible_objects" in exec_res:
            shared["visible_objects"] = exec_res["visible_objects"]
        
        # Send message to other agents
        if shared.get("message_to_others"):
            agent_id = shared["agent_id"]
            message = shared["message_to_others"]
            perception = shared["perception"]
            try:
                perception.send_message(agent_id, "all", message)
                print(f"[{agent_id}] Sent message: {message}")
            except Exception as e:
                print(f"[{agent_id}] Failed to send message: {e}")
        
        # Update explored objects set
        visible = shared["visible_objects"]
        shared["explored_objects"].update(visible)
        
        return "default"


class UpdateMemoryNode(Node):
    """Memory update node: Store new exploration information in FAISS"""
    
    def prep(self, shared):
        # Construct memory text
        memory_text = (
            f"At position {shared['position']}, "
            f"I saw {shared['visible_objects']}. "
            f"I decided to {shared['action']}. "
            f"Reason: {shared['action_reason']}"
        )
        
        return memory_text, shared["memory_index"], shared["memory_texts"]
    
    def exec(self, prep_res):
        memory_text, index, memory_texts = prep_res
        
        # Get embedding
        embedding = get_embedding(memory_text)
        
        # Add to memory
        add_to_memory(index, embedding, memory_text, memory_texts)
        
        return memory_text
    
    def post(self, shared, prep_res, exec_res):
        # Record action history
        shared["action_history"].append({
            "step": shared["step_count"],
            "position": shared["position"],
            "action": shared["action"],
            "visible": shared["visible_objects"]
        })
        
        print(f"[{shared['agent_id']}] Memory updated: {exec_res[:80]}...")
        
        # Decide whether to continue exploration
        max_steps = shared["global_env"].get("max_steps", 20)
        
        if shared["step_count"] >= max_steps:
            print(f"[{shared['agent_id']}] Reached max steps ({max_steps}), ending exploration")
            return "end"
        
        return "continue"


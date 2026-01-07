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
from utils.vision import summarize_img, compare_img
import time
from utils.perception_interface import PerceptionInterface
import yaml
import threading
import os
import re
import glob
from pathlib import Path


def find_previous_screenshot(current_screenshot_path: str, agent_id: str) -> str:
    """
    Find the previous screenshot for the given agent based on timestamp.
    
    Args:
        current_screenshot_path: Path to the current screenshot
        agent_id: Agent identifier to filter screenshots
        
    Returns:
        Path to the previous screenshot, or empty string if not found
    """
    if not current_screenshot_path:
        return ""
    
    current_path = Path(current_screenshot_path)
    screenshot_dir = current_path.parent
    
    if not screenshot_dir.exists():
        return ""
    
    # Find all screenshots for this agent in the same directory
    # Pattern: {agent_id}_*.png
    pattern = str(screenshot_dir / f"{agent_id}_*.png")
    all_screenshots = glob.glob(pattern)
    
    if len(all_screenshots) < 2:
        # No previous screenshot available
        return ""
    
    # Sort by modification time (oldest first)
    all_screenshots_sorted = sorted(all_screenshots, key=lambda p: Path(p).stat().st_mtime)
    
    # Find the index of current screenshot
    current_abs = str(current_path.resolve())
    try:
        current_idx = next(
            i for i, p in enumerate(all_screenshots_sorted) 
            if str(Path(p).resolve()) == current_abs
        )
    except StopIteration:
        # Current screenshot not found in list, return the second most recent
        if len(all_screenshots_sorted) >= 2:
            return all_screenshots_sorted[-2]
        return ""
    
    # Return the screenshot before the current one
    if current_idx > 0:
        return all_screenshots_sorted[current_idx - 1]
    
    return ""


class PerceptionNode(Node):
    """
    Perception node: Get current environment state
    
    Uses PerceptionInterface abstraction layer, supports switching between different perception implementations
    """
    
    def prep(self, memory):
        # Update position counter at the start of iteration (before perception)
        memory["position"] += 1
        
        # Get perception interface from memory store
        perception = memory["perception"]
        agent_id = memory["agent_id"]
        position = memory["position"]
        
        return perception, agent_id, position
    
    def exec(self, prep_res):
        perception, agent_id, position = prep_res
        
        # Use perception interface to get visible objects
        # Note: Thread safety is handled by the perception implementation itself
        # ask for screenshot and return the path
        visible = perception.get_visible_objects(agent_id, position)
        
        return visible
    
    def post(self, memory, prep_res, exec_res):
        memory["visible_objects"] = exec_res
        # If unity screenshot path is present, use summarize_img to get description and objects with positions
        # Example of exec_res: ["screenshot:E:/.../img.png"]
        description = None
        current_image_path = None
        
        if exec_res and isinstance(exec_res[0], str) and exec_res[0].startswith("screenshot:"):
            current_image_path = exec_res[0].split("screenshot:", 1)[1]
            # summarize_img returns {"description": "...", "objects": {"chair": "front-near", ...}}
            summary = summarize_img(current_image_path)
            description = summary.get("description")
            objects_with_positions = summary.get("objects", {})
            # Update visible_objects with object-position dict
            if objects_with_positions:
                memory["visible_objects"] = objects_with_positions
        
        # Set visible_caption: use description if available, otherwise format visible_objects
        if description:
            memory["visible_caption"] = description
        elif isinstance(memory["visible_objects"], dict):
            # Format dict as "object1 (position1), object2 (position2), ..."
            memory["visible_caption"] = ", ".join(
                f"{obj} ({pos})" for obj, pos in memory["visible_objects"].items()
            )
        else:
            memory["visible_caption"] = ", ".join(map(str, memory["visible_objects"]))
        
        print(f"[{memory['agent_id']}] Position {memory['position']}: sees {memory['visible_objects']}")
        if description:
            print(f"[{memory['agent_id']}] Description: {description}")
        
        # Compare with previous screenshot if available
        if current_image_path:
            agent_id = memory["agent_id"]
            prev_image_path = find_previous_screenshot(current_image_path, agent_id)
            
            if prev_image_path:
                print(f"[{agent_id}] Comparing with previous screenshot: {prev_image_path}")
                env_change_text = compare_img(prev_image_path, current_image_path)
                
                # Store env change in memory
                if "env_change" not in memory:
                    memory["env_change"] = []
                memory["env_change"].append({
                    "step": memory["position"],
                    "change": env_change_text,
                    "prev_image": prev_image_path,
                    "curr_image": current_image_path
                })
                
                print(f"[{agent_id}] Environment change: {env_change_text}")
            else:
                print(f"[{agent_id}] No previous screenshot found (first observation)")
        
        return "default"


class RetrieveMemoryNode(Node):
    """Memory retrieval node: Retrieve relevant history from FAISS"""
    
    def prep(self, memory):
        visible_caption = memory.get("visible_caption") or ", ".join(map(str, memory.get("visible_objects", [])))
        position = memory["position"]
        
        # Construct query text using caption (works for both mock text and image-derived caption)
        query = f"What do I know about position {position} with what I see: {visible_caption}?"
        return query, memory["memory_index"], memory["memory_texts"]
    
    def exec(self, prep_res):
        query, index, memory_texts = prep_res
        
        # Get query vector
        query_emb = get_embedding(query)
        
        # Search memory
        results = search_memory(index, query_emb, memory_texts, top_k=3)
        
        return results
    
    def post(self, memory, prep_res, exec_res):
        memory["retrieved_memories"] = exec_res
        
        if exec_res:
            print(f"[{memory['agent_id']}] Retrieved {len(exec_res)} memories:")
            for i, (text, dist) in enumerate(exec_res[:], 1):
                print(f"  {i}. {text[:80]}...")
        else:
            print(f"[{memory['agent_id']}] No memories found (first time)")
        
        return "default"


class CommunicationNode(Node):
    """Communication node: Read messages from other agents"""
    
    def prep(self, memory):
        return memory["agent_id"], memory["perception"]
    
    def exec(self, prep_res):
        agent_id, perception = prep_res
        try:
            messages = perception.poll_messages(agent_id)
        except Exception as e:
            print(f"[CommunicationNode] Error polling messages: {e}")
            messages = []
        return messages
    
    def post(self, memory, prep_res, exec_res):
        memory["other_agent_messages"] = exec_res
        
        if exec_res:
            print(f"[{memory['agent_id']}] Received {len(exec_res)} messages:")
            for msg in exec_res:
                print(f"  From {msg['sender']}: {msg['message']}")
        
        return "default"


class DecisionNode(Node):
    """Decision node: Decide next action based on context"""
    
    def prep(self, memory):
        # Collect all context needed for decision making
        context = {
            "agent_id": memory["agent_id"],
            "position": memory["position"],
            "visible_objects": memory["visible_objects"],
            "retrieved_memories": memory["retrieved_memories"],
            "other_agent_messages": memory["other_agent_messages"],
            "explored_objects": list(memory["explored_objects"]),
            "step_count": memory["step_count"],
            "perception_type": memory.get("perception", {}).get_environment_info().get("type", "unknown"),
            "action_history": memory.get("action_history", []),  # Add action history to context
            "env_change": memory.get("env_change", [])  # Add environment change history
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
                "message_to_others": "Testing without LLM"
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
        
        # Get latest 5 action history records (or all if less than 5)
        action_history = context.get("action_history", [])
        latest_history = action_history[-5:] if len(action_history) > 5 else action_history
        
        # Format action history for prompt
        if latest_history:
            history_text = "\n".join([
                f"  Step {record['step']}: At position {record['position']}, action '{record['action']}', "
                f"visible: {record.get('visible', [])}, "
                f"new objects: {record.get('new_objects', [])}"
                for record in latest_history
            ])
            history_section = f"Recent action history (last {len(latest_history)} steps):\n{history_text}"
        else:
            history_section = "No previous action history (this is the first step)"
        
        # Format environment change history (last 5 entries)
        env_change_history = context.get("env_change", [])
        latest_env_changes = env_change_history[-5:] if len(env_change_history) > 5 else env_change_history
        
        if latest_env_changes:
            env_change_text = "\n".join([
                f"  Step {record['step']}: {record['change']}"
                for record in latest_env_changes
            ])
            env_change_section = f"Recent environment changes (comparing consecutive screenshots):\n{env_change_text}"
        else:
            env_change_section = "No environment change history yet (first observation or screenshots not available)"
        
        # Determine available actions based on perception type
        perception_type = context.get("perception_type", "unknown")
        if perception_type == "unity3d":
            # Simplified action space for unity3d mode (WSAD + Space)
            available_actions = [
                "- forward: Move forward (key 'w')",
                "- backward: Move backward (key 's')",
                "- move_left: Strafe left (key 'a')",
                "- move_right: Strafe right (key 'd')",
            ]
            action_list = "forward, backward, move_left, move_right"
            valid_actions = ["forward", "backward", "move_left", "move_right",]
        else:
            # Full action space for other modes
            available_actions = [
                "- forward: Move to next position",
                "- backward: Move to previous position",
                "- move_left: Strafe left (key 'a')",
                "- move_right: Strafe right (key 'd')",
                "- move_up: Move up (key 'r')",
                "- move_down: Move down (key 'f')",
                "- look_left: Turn head left (left arrow)",
                "- look_right: Turn head right (right arrow)",
                "- look_up: Look up (up arrow)",
                "- look_down: Look down (down arrow)",
                "- tilt_left: Roll head left (key 'q')",
                "- tilt_right: Roll head right (key 'e')",
            ]
            action_list = "forward, backward, move_left, move_right, move_up, move_down, look_left, look_right, look_up, look_down, tilt_left, tilt_right"
            valid_actions = [
                "forward", "backward",
                "move_left", "move_right", "move_up", "move_down",
                "look_left", "look_right", "look_up", "look_down",
                "tilt_left", "tilt_right",
            ]
        
        actions_text = "\n".join(available_actions)
        
        prompt = f"""You are {context['agent_id']}, an autonomous exploration agent exploring within a 3D environment as part of a multi-agent team.
                    Your mission is to maximize the discovery of new objects and unexplored areas while cooperating efficiently with other agents. Avoid redundant exploration, communicate findings clearly, and make strategic movement decisions.
Current state:
- Position: {context['position']}
- Visible objects: {context['visible_objects']}
- Already explored objects: {context['explored_objects']}
- Steps taken: {context['step_count']}

{history_section}

{env_change_section}

Relevant historical memories:
{memories_text}

**Messages from other agents (IMPORTANT - analyze and consider these before deciding):**
{messages_text}
When other agents have reported discoveries or explored certain regions, use this information to **reduce overlap** and **improve overall coverage**.

Task goal: Explore as many new objects as possible, avoid revisiting already explored areas. Analize the screen shot and decide the next action.

Decision strategy:
- Cross-reference other agents' messages with your local observation.
- If another agent found new objects nearby, consider moving closer to assist or expand coverage.
- If you enter an area that is not meant to be explored (for example, the sky or any place outside the interactive scene), or if you get stuck somewhere, please find a way to leave that area.
- If an area is already reported explored or low in novelty, avoid it. Maintain spatial diversity to maximize total system exploration.
- Communicate back only useful information.

Available actions:
{actions_text}

Please decide the next action based on the above information, output in YAML format:

```yaml
thinking: Your thought process (MUST consider messages from other agents if any, and whether to explore new areas)
action: one of [{action_list}]
reason: Reason for choosing this action (mention other agents' messages if they influenced your decision)
message_to_others: Information to share with other agents (optional)
```
"""
        
        response = call_llm(prompt)
        
        # Parse YAML with improved error handling
        try:
            result = parse_yaml_from_llm_response(response)
            
            # Validate required fields
            if not isinstance(result, dict):
                raise ValueError("LLM response is not a dictionary")
            if "action" not in result:
                raise ValueError("Missing 'action' field in LLM response")
            if result["action"] not in valid_actions:
                raise ValueError(f"Invalid action: {result['action']}")
            if "reason" not in result:
                result["reason"] = "No reason provided"
            
        except (IndexError, ValueError, yaml.YAMLError) as e:
            # Fallback: try to extract action from response text
            print(f"[DecisionNode] YAML parsing failed: {e}")
            print(f"[DecisionNode] LLM response was: {response[:500]}...")
            
            # Try regex extraction as fallback
            action_match = re.search(r'action:\s*(\w+)', response, re.IGNORECASE)
            if action_match:
                action = action_match.group(1).lower()
                if action in valid_actions:
                    result = {
                        "thinking": "YAML parsing failed, extracted action from text",
                        "action": action,
                        "reason": "Fallback decision due to YAML parsing error",
                        "message_to_others": ""
                    }
                else:
                    # Final fallback: use deterministic action
                    result = {
                        "thinking": "YAML parsing failed and could not extract valid action",
                        "action": "forward" if context.get("step_count", 0) % 2 == 0 else "backward",
                        "reason": "Fallback to deterministic action due to parsing error",
                        "message_to_others": ""
                    }
            else:
                # Final fallback: use deterministic action
                result = {
                    "thinking": "YAML parsing failed and could not extract action from response",
                    "action": "forward" if context.get("step_count", 0) % 2 == 0 else "backward",
                    "reason": "Fallback to deterministic action due to parsing error",
                    "message_to_others": ""
                }
        
        return result
    
    def post(self, memory, prep_res, exec_res):
        memory["action"] = exec_res["action"]
        memory["action_reason"] = exec_res.get("reason", "")
        memory["message_to_others"] = exec_res.get("message_to_others", "")
        
        print(f"[{memory['agent_id']}] Decision: {exec_res['action']}")
        print(f"  Reason: {exec_res['reason']}")
        
        return "default"


class ExecutionNode(Node):
    """
    Execution node: Execute action and update environment
    
    Uses PerceptionInterface to execute actions, supports different environment implementations
    """
    
    def prep(self, memory):
        perception = memory["perception"]
        agent_id = memory["agent_id"]
        action = memory["action"]
        
        return perception, agent_id, action
    
    def exec(self, prep_res):
        perception, agent_id, action = prep_res

        # Log action execution for debugging (visible in Python console)
        print(f"[ExecutionNode] Agent '{agent_id}' executing action: {action}")

        # Use perception interface to execute action
        # Returns new state (including position, visible objects, etc.)
        new_state = perception.execute_action(agent_id, action)

        print(f"[ExecutionNode] Agent '{agent_id}' new state after action '{action}': position={new_state.get('position')}")

        return new_state
    
    def post(self, memory, prep_res, exec_res):
        # Update step count
        memory["step_count"] += 1
        
        # Note: visible_objects will be updated in the next PerceptionNode
        # ExecutionNode only updates position, not perception
        
        # Send message to other agents
        if memory.get("message_to_others"):
            agent_id = memory["agent_id"]
            message = memory["message_to_others"]
            perception = memory["perception"]
            try:
                perception.send_message(agent_id, "all", message)
                print(f"[{agent_id}] Sent message: {message}")
            except Exception as e:
                print(f"[{agent_id}] Failed to send message: {e}")
        
        # Note: explored_objects will be updated in UpdateMemoryNode based on visible_objects
        # from PerceptionNode, not from visible_objects here
        
        return "default"


class UpdateMemoryNode(Node):
    """Memory update node: Store new exploration information in FAISS"""
    
    def prep(self, memory):
        # Construct memory text with own experience
        memory_text = (
            f"At position {memory['position']}, "
            f"I saw {memory['visible_objects']}. "
            f"I decided to {memory['action']}. "
            f"Reason: {memory['action_reason']}"
        )
        
        # Add messages from other agents (if any)
        if memory.get("other_agent_messages"):
            messages_parts = []
            for msg in memory["other_agent_messages"]:
                messages_parts.append(f"{msg['sender']}: {msg['message']}")
            
            messages_summary = "; ".join(messages_parts)
            memory_text += f" | Context from others: {messages_summary}"
        
        # Prepare data for memory update - use visible_objects directly
        visible_objects = memory.get("visible_objects", {})
        # Handle both dict format (from summarize_img) and list format (fallback)
        if isinstance(visible_objects, dict):
            # Extract object names from dict keys
            objects_list = [
                obj for obj in visible_objects.keys()
                if isinstance(obj, str) and not obj.startswith("screenshot:")
            ]
        elif isinstance(visible_objects, (list, set)):
            # Filter out screenshot paths (in case extraction failed)
            objects_list = [
                obj for obj in visible_objects 
                if isinstance(obj, str) and not obj.startswith("screenshot:")
            ]
        else:
            objects_list = []
        
        return memory_text, memory["memory_index"], memory["memory_texts"], memory["agent_id"], memory["position"], objects_list
    
    def exec(self, prep_res):
        memory_text, index, memory_texts, agent_id, position, objects_list = prep_res
        
        # Get embedding
        embedding = get_embedding(memory_text)
        
        # Add to episodic memory (FAISS)
        add_to_memory(index, embedding, memory_text, memory_texts)
        
        return memory_text, objects_list
    
    def post(self, memory, prep_res, exec_res):
        memory_text, objects_list = exec_res
        
        # Calculate new objects (before updating explored_objects)
        # Filter out screenshot paths and normalize objects
        visible_objects_normalized = []
        visible_objects = memory.get("visible_objects", {})
        if visible_objects:
            # Handle both dict format (from summarize_img) and list format (fallback)
            if isinstance(visible_objects, dict):
                visible_objects_normalized = [
                    obj.lower().strip() 
                    for obj in visible_objects.keys()
                    if isinstance(obj, str) and not obj.startswith("screenshot:")
                ]
            else:
                visible_objects_normalized = [
                    obj.lower().strip() 
                    for obj in visible_objects
                    if isinstance(obj, str) and not obj.startswith("screenshot:")
                ]
        
        # Find new objects that are not in explored_objects yet
        explored_set = memory.get("explored_objects", set())
        new_objects = [
            obj for obj in visible_objects_normalized 
            if obj and obj not in explored_set
        ]
        
        # Record action history with new objects
        memory["action_history"].append({
            "step": memory["step_count"],
            "position": memory["position"],
            "action": memory["action"],
            "visible": memory["visible_objects"],
            "new_objects": new_objects  # Only newly discovered objects
        })
        
        # Update explored_objects with discovered objects
        if objects_list:
            objects_set = set(obj.lower().strip() for obj in objects_list if obj)
            memory["explored_objects"].update(objects_set)
        
        print(f"[{memory['agent_id']}] Memory updated: {memory_text[:100]}...")
        if objects_list:
            print(f"[{memory['agent_id']}] Discovered objects: {objects_list}")
            print(f"[{memory['agent_id']}] Total unique objects explored: {len(memory['explored_objects'])}")
        
        # Decide whether to continue exploration
        max_steps = memory.get("max_steps", 20)
        
        if memory["step_count"] >= max_steps:
            print(f"[{memory['agent_id']}] Reached max steps ({max_steps}), ending exploration")
            return "end"
        
        return "continue"




def parse_yaml_from_llm_response(response: str) -> dict:
    """
    Parse YAML from LLM response with improved error handling.
    
    Extracts YAML from code blocks, cleans up common formatting issues,
    and returns a parsed dictionary.
    
    Args:
        response: Raw LLM response string that may contain YAML in code blocks
        
    Returns:
        Parsed YAML as a dictionary
        
    Raises:
        ValueError: If YAML cannot be parsed or is invalid
        yaml.YAMLError: If YAML parsing fails
    """
    # Try to extract YAML from code block
    if "```yaml" in response:
        yaml_str = response.split("```yaml")[1].split("```")[0].strip()
    elif "```" in response:
        # Fallback: try to extract from any code block
        parts = response.split("```")
        if len(parts) >= 2:
            yaml_str = parts[1].strip()
            if yaml_str.startswith("yaml"):
                yaml_str = yaml_str[4:].strip()
        else:
            yaml_str = response.strip()
    else:
        # No code block, assume entire response is YAML
        yaml_str = response.strip()
    
    # Clean up common YAML issues:
    # Fix problematic single quotes in values (like 'screen', 'cursor' in reason field)
    lines = yaml_str.split('\n')
    cleaned_lines = []
    for line in lines:
        # If line contains a colon (key-value pair)
        if ':' in line and not line.strip().startswith('#'):
            parts = line.split(':', 1)
            if len(parts) == 2:
                key, value = parts
                value = value.strip()
                
                # If value is already properly quoted, leave it alone
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'") and value.count("'") == 2):
                    cleaned_lines.append(line)
                    continue
                
                # If value contains problematic patterns (like 'word1', 'word2')
                # wrap entire value in double quotes and escape internal quotes
                if "'" in value:
                    # Escape any existing double quotes
                    value = value.replace('"', '\\"')
                    # Remove or escape single quotes (YAML prefers double quotes for strings with special chars)
                    value = value.replace("'", "")
                    # Wrap in double quotes
                    value = '"' + value + '"'
                elif ':' in value or (',' in value and not value.startswith('[')):
                    # Values with colons or commas should be quoted
                    value = '"' + value.replace('"', '\\"') + '"'
                
                cleaned_lines.append(key.strip() + ': ' + value)
            else:
                cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)
    yaml_str = '\n'.join(cleaned_lines)
    
    result = yaml.safe_load(yaml_str)
    return result

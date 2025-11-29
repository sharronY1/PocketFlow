# Technical Specification

## 1. Project Workflow

```
Perception → RetrieveMemory → Communication
    ↑                                ↓
    |                           Decision
    |                                ↓
UpdateMemory ← Execution ←──────────┘
    |
    └─→ continue (loop) / end (terminate)
```

## 2. Shared Memory and Message System Data Structure

The system uses a shared memory structure accessible by all agents:

```python
shared_memory = {
    "objects": set(),              # Set of discovered objects (dynamically updated, only increases)
    "agent_positions": {},         # Dict mapping agent_id -> current position
    "message_mailboxes": {},       # Dict mapping agent_id -> list of messages (mailbox system)
    "message_history": []          # Complete history of all messages (never deleted)
}
```

Each message is a dictionary:

```python
{
    "sender": "Agent1",        # Sender ID
    "recipient": "Agent2",     # Recipient ID (can be specific Agent or "all")
    "message": "I found keyboard at position 5"  # Message content
}
```

The mailbox system ensures each agent has their own message queue:
- Messages sent to a specific agent are placed in that agent's mailbox
- Messages sent to "all" are placed in all other agents' mailboxes (excluding sender)
- Reading messages clears the agent's mailbox (prevents duplicate reads)

## 3. Perception Interface Abstraction Layer

The system uses a `PerceptionInterface` abstraction layer to support different perception implementations:
The perception interface provides:
- `get_visible_objects(agent_id, position)`: Get visible objects at current position
- `get_agent_state(agent_id)`: Get agent's current state (position, rotation, etc.)
- `execute_action(agent_id, action, params)`: Execute action and return new state
- `get_environment_info()`: Get global environment information
- `send_message(sender, recipient, message)`: Send message to other agents (optional)
- `poll_messages(agent_id)`: Poll messages for the agent (optional)

This abstraction allows the system to switch between different perception backends without changing the node logic.

## 4. Communication Workflow

In Decision Node, LLM can optionally generate a message when making decisions:

```python
messages_text = "\n".join([
    f"- {msg['sender']}: {msg['message']}"
    for msg in context["other_agent_messages"]
]) if context["other_agent_messages"] else "No messages from other agents"
```

LLM return format (YAML):

```yaml
thinking: "I saw new objects, should inform other Agents"
action: forward
reason: "Continue exploring new areas"
message_to_others: "I found chair and table at position 3"  # ← Optional field
```

**Available actions:**
- `forward`, `backward`: Move forward/backward
- `move_left`, `move_right`, `move_up`, `move_down`: Strafe movements
- `look_left`, `look_right`, `look_up`, `look_down`: Turn head
- `tilt_left`, `tilt_right`: Roll head

Sending messages in execution node:

```python
if shared.get("message_to_others"):
    agent_id = shared["agent_id"]
    message = shared["message_to_others"]
    perception = shared["perception"]
    
    try:
        perception.send_message(agent_id, "all", message)
        print(f"[{agent_id}] Sent message: {message}")
    except Exception as e:
        print(f"[{agent_id}] Failed to send message: {e}")
```

Reading messages in communication node:

The communication node uses the perception interface to poll messages:

```python
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
```

For mock/local perception, messages are managed via mailbox system in shared memory.

## 5. Memory System Architecture

Each agent has an independent memory system:

```
┌────────────────────────────────────────────┐
│      Shared Memory (Shared)                │
│  - objects (discovered objects set)        │
│  - agent_positions (positions)             │
│  - message_mailboxes (message system)      │
│  - message_history (complete log)          │
└────────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│   Agent1 Memory │    │   Agent2 Memory │
│  (Independent,  │    │  (Independent,  │
│    Private)     │    │    Private)     │
├─────────────────┤    ├─────────────────┤
│ memory_index    │    │ memory_index    │
│ memory_texts    │    │ memory_texts    │
└─────────────────┘    └─────────────────┘
```

Agent private storage:

```python
agent_shared = {
    "agent_id": "Agent1",
    "shared_memory": shared_memory,  # Reference to shared memory
    "perception": perception,         # Perception interface instance
    
    # Memory system (private)
    "memory_index": <FAISS index object>,  # Vector database (384-dim)
    "memory_texts": [],                    # Corresponding text list
    
    # Current state
    "position": 0,
    "step_count": 0,
    "visible_objects": [],
    "visible_caption": "",                 # Caption for images or object list
    "retrieved_memories": [],              # Memories retrieved from FAISS
    
    # Communication
    "other_agent_messages": [],
    
    # Decision results
    "action": None,
    "action_reason": "",
    "message_to_others": "",
    
    # Exploration history
    "explored_objects": set(),
    "action_history": []                   # List of action records with messages
}
```

## 6. Vision Processing (Unity Mode)

In Unity mode, the system uses LLM vision models to process screenshots:

1. **Screenshot Capture**: UnityPyAutoGUIPerception captures screenshots of the Unity window
2. **Image Captioning**: `caption_image()` generates a text description of the scene
3. **Object Extraction**: `extract_objects_from_image()` extracts a list of objects from the image

The extracted objects are used as `visible_objects`, and the caption is stored as `visible_caption` for memory retrieval.

```python
# In PerceptionNode post() method
if exec_res and isinstance(exec_res[0], str) and exec_res[0].startswith("screenshot:"):
    image_path = exec_res[0].split("screenshot:", 1)[1]
    caption = caption_image(image_path)
    extracted_objects = extract_objects_from_image(image_path)
    if extracted_objects:
        shared["visible_objects"] = extracted_objects
    shared["visible_caption"] = caption
```

## 7. Memory System Workflow

**a. In update memory node, agent stores new experiences into memory:**

The memory text includes both the agent's own experience and context from other agents' messages:

```python
def prep(self, shared):
    # Construct memory text with own experience
    memory_text = (
        f"At position {shared['position']}, "
        f"I saw {shared['visible_objects']}. "
        f"I decided to {shared['action']}. "
        f"Reason: {shared['action_reason']}"
    )
    
    # Add messages from other agents (if any)
    if shared.get("other_agent_messages"):
        messages_parts = []
        for msg in shared["other_agent_messages"]:
            messages_parts.append(f"{msg['sender']}: {msg['message']}")
        messages_summary = "; ".join(messages_parts)
        memory_text += f" | Context from others: {messages_summary}"
    
    return memory_text, shared["memory_index"], shared["memory_texts"], ...

def exec(self, prep_res):
    memory_text, index, memory_texts, ... = prep_res
    
    # Get embedding (384-dimensional vector)
    embedding = get_embedding(memory_text)
    
    # Add to private memory (FAISS)
    add_to_memory(index, embedding, memory_text, memory_texts)
    
    # Also update shared memory with discovered objects
    if shared_memory and objects_for_shared:
        with env_lock:
            shared_memory["objects"].update(objects_set)
    
    return memory_text, objects_for_shared
```

Text → Vector (384-dim) → FAISS (L2 distance)

**b. In retrieve memory node, retrieve relevant memories:**

The query uses the visible caption (works for both mock text and image-derived captions):

```python
def prep(self, shared):
    visible_caption = shared.get("visible_caption") or ", ".join(map(str, shared.get("visible_objects", [])))
    position = shared["position"]
    
    # Construct query text using caption
    query = f"What do I know about position {position} with what I see: {visible_caption}?"
    return query, shared["memory_index"], shared["memory_texts"]

def exec(self, prep_res):
    query, index, memory_texts = prep_res
    
    # Get query vector
    query_emb = get_embedding(query)
    
    # Search memory (top_k=3)
    results = search_memory(index, query_emb, memory_texts, top_k=3)
    
    return results  # List of (text, distance) tuples
```

Query → Vector → Similarity Search (L2 distance) → Top-K Results

**c. Flow control in update memory node:**

The UpdateMemoryNode decides whether to continue or end exploration based on step count:

```python
# Decide whether to continue exploration
max_steps = shared.get("global_env", {}).get("max_steps", 
             shared.get("shared_memory", {}).get("max_steps", 20))

if shared["step_count"] >= max_steps:
    return "end"  # Terminate exploration
    
return "continue"  # Loop back to PerceptionNode
```

The flow branches at UpdateMemoryNode:
- `"continue"` → loops back to `PerceptionNode`
- `"end"` → terminates the agent's exploration flow

## 8. Perception Types and Modes

The system supports multiple perception modes:

### Mock Mode
- Simulated environment with preset objects at positions
- Uses dictionary-based `MockPerception`
- Objects are predefined in `create_environment()`

### Unity Mode
- Interacts with running Unity game window via `pyautogui`
- Captures screenshots for vision processing
- Sends keyboard inputs for actions
- Requires Unity window to be focused
- Uses `UnityPyAutoGUIPerception`
- Objects are discovered dynamically through image analysis

## 9. Memory Sharing Through Messages

Memory is private to each agent, but agents can share key information through the message system. Agents use messages from other agents when making decisions and include them in their memory context.

**Flow:**
1. Agent receives messages via `CommunicationNode`
2. Messages are included in decision-making context
3. Messages are incorporated into memory when storing new experiences
4. Shared memory tracks all discovered objects globally (but not detailed memory content)


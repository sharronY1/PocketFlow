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

## 2. Message Queue Data Structure

```python
global_env = {
    "objects": {...},
    "agent_positions": {...},
    "message_queue": [],  # ← This is the message queue
    "explored_by_all": set()
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

## 3. Communication Workflow

In Decision Node, LLM can optionally generate a message when making decisions:

```python
messages_text = "\n".join([
    f"- {msg['sender']}: {msg['message']}"
    for msg in context["other_agent_messages"]
]) if context["other_agent_messages"] else "No messages from other agents"
```

LLM return format:

```
thinking: "I saw new objects, should inform other Agents"
action: forward
reason: "Continue exploring new areas"
message_to_others: "I found chair and table at position 3"  # ← Optional field
```

Sending messages, check if there are messages to send in execution node:

```python
if shared.get("message_to_others"):
    agent_id = shared["agent_id"]
    message = shared["message_to_others"]
    env = shared["global_env"]
    
    with env_lock:
        # Send to all other agents
        add_message(env, agent_id, "all", message)
    
    print(f"[{agent_id}] Sent message: {message}")
```

Reading messages, read messages in communication node:

a. Iterate through the message queue  
b. Extract messages if the recipient is self or "all"  
c. Remove read messages from the queue (avoid duplicate reads)  
d. Return the list of extracted messages  

```python
class CommunicationNode(Node):
    """Communication node: Read messages from other agents"""
    
    def prep(self, shared):
        return shared["agent_id"], shared["global_env"]
    
    def exec(self, prep_res):
        agent_id, env = prep_res
        
        # Thread-safe message reading
        with env_lock:
            messages = get_messages_for(env, agent_id)
        
        return messages
    
    def post(self, shared, prep_res, exec_res):
        shared["other_agent_messages"] = exec_res
        
        if exec_res:
            print(f"[{shared['agent_id']}] Received {len(exec_res)} messages:")
            for msg in exec_res:
                print(f"  From {msg['sender']}: {msg['message']}")
        
        return "default"
```

## 4. Memory System Architecture

Each agent has an independent memory system:

```
┌────────────────────────────────────────────┐
│      Global Environment (Shared)           │
│  - objects (positions and items)           │
│  - agent_positions (positions)             │
│  - message_queue (message queue)           │
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
    
    # Memory system (private)
    "memory_index": <FAISS index object>,  # Vector database
    "memory_texts": [],                    # Corresponding text list
    
    # Current state
    "visible_objects": [...],
    "retrieved_memories": [],              # Memories retrieved from FAISS
    
    # Exploration history
    "explored_objects": set(),
    "action_history": []
}
```

## 5. Memory System Workflow

**a. In update memory node, agent stores new experiences into memory:**

```python
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
```

Text → Vector → FAISS

**b. In retrieve memory node, retrieve relevant memories:**

```python
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
```

Query → Vector → Similarity Search

## 6. Memory Sharing Through Messages

Memory is private, but Agents can share key information through the message queue. Agents can use messages when making decisions.


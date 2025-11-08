"""
Centralized messaging server for multi-agent communication.

This FastAPI server provides a centralized message passing system for agents
to communicate with each other. It implements a mailbox-based messaging system
similar to the local environment.py implementation.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import threading
from datetime import datetime

app = FastAPI(title="Environment Messaging Server", version="1.0.0")

# In-memory message storage (mailbox system)
# Structure: {agent_id: [msg1, msg2, ...]}
message_mailboxes: Dict[str, List[Dict[str, Any]]] = {}
message_history: List[Dict[str, Any]] = []
agent_registry: Dict[str, datetime] = {}  # Track agent activity
lock = threading.Lock()  # Thread-safe access


class SendMessageRequest(BaseModel):
    sender: str
    recipient: str  # Can be specific agent_id or "all"
    message: str


class PollMessagesRequest(BaseModel):
    agent_id: str


class PollMessagesResponse(BaseModel):
    messages: List[Dict[str, Any]]


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "Environment Messaging Server",
        "registered_agents": len(agent_registry),
        "total_messages": len(message_history)
    }


@app.post("/messages/send")
async def send_message(request: SendMessageRequest):
    """
    Send a message from one agent to another (or to all agents).
    
    - If recipient is a specific agent_id, message goes to that agent's mailbox
    - If recipient is "all", message goes to all registered agents' mailboxes (except sender)
    """
    with lock:
        # Register sender if not already registered
        agent_registry[request.sender] = datetime.now()
        
        # Create message object
        msg = {
            "sender": request.sender,
            "recipient": request.recipient,
            "message": request.message,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add to history (never deleted)
        message_history.append(msg.copy())
        
        # Deliver to mailbox(es)
        if request.recipient == "all":
            # Send to all registered agents except sender
            all_agents = set(agent_registry.keys())
            all_agents.discard(request.sender)
            
            for agent_id in all_agents:
                if agent_id not in message_mailboxes:
                    message_mailboxes[agent_id] = []
                message_mailboxes[agent_id].append(msg.copy())
        else:
            # Send to specific agent (but not if it's the sender)
            if request.recipient != request.sender:
                if request.recipient not in message_mailboxes:
                    message_mailboxes[request.recipient] = []
                message_mailboxes[request.recipient].append(msg.copy())
        
        return {"status": "sent", "recipient": request.recipient}


@app.post("/messages/poll", response_model=PollMessagesResponse)
async def poll_messages(request: PollMessagesRequest):
    """
    Poll messages for a specific agent.
    
    Returns all messages in the agent's mailbox and clears the mailbox.
    Messages sent by the agent itself are filtered out.
    """
    with lock:
        # Register agent if not already registered
        agent_registry[request.agent_id] = datetime.now()
        
        # Get agent's mailbox
        mailbox = message_mailboxes.get(request.agent_id, [])
        
        # Filter out self-messages (safety check)
        messages = [
            {
                "sender": msg.get("sender"),
                "recipient": msg.get("recipient"),
                "message": msg.get("message"),
                "timestamp": msg.get("timestamp")
            }
            for msg in mailbox
            if msg.get("sender") != request.agent_id
        ]
        
        # Clear the mailbox after reading
        message_mailboxes[request.agent_id] = []
        
        return PollMessagesResponse(messages=messages)


@app.get("/messages/history")
async def get_message_history(limit: Optional[int] = 100):
    """
    Get message history (for debugging/monitoring).
    
    Args:
        limit: Maximum number of messages to return (default: 100)
    
    Returns:
        List of all messages in history
    """
    with lock:
        # Return most recent messages
        recent_messages = message_history[-limit:] if limit else message_history
        return {
            "total": len(message_history),
            "returned": len(recent_messages),
            "messages": recent_messages
        }


@app.get("/agents")
async def list_agents():
    """List all registered agents and their last activity time"""
    with lock:
        return {
            "agents": {
                agent_id: last_seen.isoformat()
                for agent_id, last_seen in agent_registry.items()
            },
            "count": len(agent_registry)
        }


@app.delete("/agents/{agent_id}")
async def unregister_agent(agent_id: str):
    """Unregister an agent and clear its mailbox"""
    with lock:
        if agent_id in agent_registry:
            del agent_registry[agent_id]
        if agent_id in message_mailboxes:
            del message_mailboxes[agent_id]
        return {"status": "unregistered", "agent_id": agent_id}


@app.delete("/messages")
async def clear_all_messages():
    """Clear all messages (for testing/reset)"""
    with lock:
        message_mailboxes.clear()
        message_history.clear()
        agent_registry.clear()
        return {"status": "cleared"}


if __name__ == "__main__":
    import uvicorn
    import os
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    print(f"Starting Environment Messaging Server on {host}:{port}")
    print(f"API docs available at http://{host}:{port}/docs")
    
    uvicorn.run(app, host=host, port=port)


"""
Centralized messaging server for multi-agent communication.

This FastAPI server provides:
1. Message passing system for agents to communicate with each other
2. Synchronization mechanism for coordinated screenshot capture

Architecture:
- Coordinator (central Agent) coordinates all child Agents via /sync/* API
- Child Agents report arrival at PerceptionNode via /sync/ready
- Child Agents block and wait for capture signal via /sync/wait_capture
- Coordinator sends unified capture signal via /sync/trigger_capture
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Set
import threading
from datetime import datetime
import asyncio

app = FastAPI(title="Environment Messaging Server", version="2.0.0")

# ==============================================================================
# Message System
# ==============================================================================
# In-memory message storage (mailbox system)
# Structure: {agent_id: [msg1, msg2, ...]}
message_mailboxes: Dict[str, List[Dict[str, Any]]] = {}
message_history: List[Dict[str, Any]] = []
agent_registry: Dict[str, datetime] = {}  # Track agent activity
lock = threading.Lock()  # Thread-safe access for messages

# ==============================================================================
# Synchronization System
# ==============================================================================
# Synchronization mechanism:
# 1. Child Agents call /sync/ready when reaching PerceptionNode to report ready
# 2. Child Agents call /sync/wait_capture to block and wait for capture signal
# 3. Coordinator calls /sync/status to check if all Agents are ready
# 4. Coordinator calls /sync/trigger_capture to send capture signal
# 5. All waiting Agents receive signal, execute screenshot, then continue their flow

# Set of Agents expected to participate in synchronization
sync_expected_agents: Set[str] = set()

# Set of Agents that have reported ready
sync_ready_agents: Set[str] = set()

# Capture signal flag (True = can capture)
sync_capture_signal: bool = False

# Stop signal flag (True = agents should stop)
sync_stop_signal: bool = False

# Lock for synchronization system
sync_lock = threading.Lock()

# Event for notifying waiting Agents
sync_capture_event = asyncio.Event()

# Event for notifying waiting Agents to stop
sync_stop_event = asyncio.Event()

# Agent error reports (for Unity window crashes, API errors, etc.)
agent_errors: Dict[str, Dict[str, Any]] = {}  # {agent_id: {"error_type": str, "message": str, "timestamp": datetime}}


class SendMessageRequest(BaseModel):
    sender: str
    recipient: str  # Can be specific agent_id or "all"
    message: str


class PollMessagesRequest(BaseModel):
    agent_id: str


class PollMessagesResponse(BaseModel):
    messages: List[Dict[str, Any]]


# ==============================================================================
# Synchronization Request/Response Models
# ==============================================================================

class SyncRegisterAgentsRequest(BaseModel):
    """Register list of Agents participating in synchronization"""
    agent_ids: List[str]


class SyncReadyRequest(BaseModel):
    """Child Agent reports arrival at PerceptionNode"""
    agent_id: str


class SyncWaitCaptureRequest(BaseModel):
    """Child Agent waits for capture signal"""
    agent_id: str
    timeout: Optional[float] = 60.0  # Timeout in seconds


class SyncReportErrorRequest(BaseModel):
    """Agent reports an error condition"""
    agent_id: str
    error_type: str  # e.g., "unity_window_missing", "api_quota_exceeded"
    message: str


class SyncStatusResponse(BaseModel):
    """Synchronization status response"""
    expected_agents: List[str]
    ready_agents: List[str]
    all_ready: bool
    capture_signal: bool
    agent_errors: Optional[Dict[str, Dict[str, Any]]] = None  # Agent error reports


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


# ==============================================================================
# Synchronization APIs
# ==============================================================================
# 
# Usage flow:
# 1. Coordinator calls POST /sync/register_agents at startup to register all child Agents
# 2. When child Agents reach PerceptionNode:
#    a. Call POST /sync/ready to report ready
#    b. Call POST /sync/wait_capture to block and wait for capture signal
# 3. Coordinator loop:
#    a. Call GET /sync/status to check if all Agents are ready
#    b. When all_ready=True, call POST /sync/trigger_capture to send capture signal
# 4. All child Agents receive signal, execute screenshot, continue their flow
# 5. Next round repeats steps 2-4
#

@app.post("/sync/register_agents")
async def sync_register_agents(request: SyncRegisterAgentsRequest):
    """
    Register list of Agents participating in synchronization

    Called by Coordinator at startup to specify which Agents need to participate in synchronization.
    This clears previous synchronization state and starts a new synchronization session.
    """
    global sync_expected_agents, sync_ready_agents, sync_capture_signal, sync_capture_event, sync_stop_signal, sync_stop_event

    with sync_lock:
        sync_expected_agents = set(request.agent_ids)
        sync_ready_agents = set()
        sync_capture_signal = False
        sync_stop_signal = False
        # Create new event object
        sync_capture_event = asyncio.Event()
        sync_stop_event = asyncio.Event()

        return {
            "status": "registered",
            "expected_agents": list(sync_expected_agents),
            "count": len(sync_expected_agents)
        }


@app.post("/sync/ready")
async def sync_ready(request: SyncReadyRequest):
    """
    Child Agent reports arrival at PerceptionNode, ready for screenshot
    
    Child Agent calls this API at the start of PerceptionNode.exec(),
    indicating it's ready and waiting for Coordinator's capture signal.
    """
    # Check if stop signal is active (for agents arriving after emergency stop)
    with sync_lock:
        if sync_stop_signal:
            return {
                "status": "stopped",
                "agent_id": request.agent_id,
                "error": "stop_signal_active",
                "message": "System is in emergency stop state"
            }
    
    with sync_lock:
        # Add to ready set
        sync_ready_agents.add(request.agent_id)
        
        # Check if all expected Agents are ready
        all_ready = sync_expected_agents and sync_ready_agents >= sync_expected_agents
        
        return {
            "status": "ready",
            "agent_id": request.agent_id,
            "ready_count": len(sync_ready_agents),
            "expected_count": len(sync_expected_agents),
            "all_ready": all_ready
        }


@app.post("/sync/wait_capture")
async def sync_wait_capture(request: SyncWaitCaptureRequest):
    """
    Child Agent blocks and waits for capture signal

    Child Agent calls this API to block and wait after reporting ready.
    When Coordinator calls trigger_capture, this API returns,
    and child Agent can execute screenshot operation.

    Args:
        agent_id: Agent identifier
        timeout: Maximum wait time (seconds), default 60 seconds

    Returns:
        should_capture: True means can capture, False means timeout or stop signal
    """
    global sync_capture_event, sync_stop_event, sync_stop_signal

    # Check if stop signal is already active (for agents arriving after emergency stop)
    with sync_lock:
        if sync_stop_signal:
            return {
                "should_capture": False,
                "agent_id": request.agent_id,
                "error": "stop_signal_received"
            }

    # Get current event object reference
    current_capture_event = sync_capture_event
    current_stop_event = sync_stop_event

    try:
        # Wait for either capture signal OR stop signal
        done, pending = await asyncio.wait(
            [current_capture_event.wait(), current_stop_event.wait()],
            timeout=request.timeout,
            return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel pending tasks
        for task in pending:
            task.cancel()

        # Check which event was triggered
        if current_stop_event.is_set():
            return {
                "should_capture": False,
                "agent_id": request.agent_id,
                "error": "stop_signal_received"
            }
        elif current_capture_event.is_set():
            return {
                "should_capture": True,
                "agent_id": request.agent_id
            }
        else:
            return {
                "should_capture": False,
                "agent_id": request.agent_id,
                "error": "timeout"
            }

    except asyncio.TimeoutError:
        return {
            "should_capture": False,
            "agent_id": request.agent_id,
            "error": "timeout"
        }


@app.get("/sync/status", response_model=SyncStatusResponse)
async def sync_status():
    """
    Get current synchronization status
    
    Coordinator polls this API to check if all Agents are ready.
    When all_ready=True, Coordinator can call trigger_capture.
    Also returns any agent error reports.
    """
    with sync_lock:
        all_ready = sync_expected_agents and sync_ready_agents >= sync_expected_agents
        
        # Return current agent errors (copy to avoid lock issues)
        errors_copy = dict(agent_errors) if agent_errors else None
        
        return SyncStatusResponse(
            expected_agents=list(sync_expected_agents),
            ready_agents=list(sync_ready_agents),
            all_ready=all_ready,
            capture_signal=sync_capture_signal,
            agent_errors=errors_copy
        )


@app.post("/sync/trigger_capture")
async def sync_trigger_capture():
    """
    Trigger unified screenshot capture
    
    Called by Coordinator when all Agents are ready to trigger capture signal.
    This will:
    1. Set capture_signal = True
    2. Notify all waiting Agents (via asyncio.Event)
    3. Clear ready_agents set for next round
    """
    global sync_capture_signal, sync_ready_agents, sync_capture_event
    
    with sync_lock:
        # Set capture signal
        sync_capture_signal = True
        
        # Record ready Agents for this round (for return value)
        triggered_agents = list(sync_ready_agents)
        
        # Clear ready set for next round
        sync_ready_agents = set()
    
    # Notify all waiting Agents
    sync_capture_event.set()
    
    # Brief delay then reset signal and event for next round
    await asyncio.sleep(0.1)
    
    with sync_lock:
        sync_capture_signal = False
    
    # Create new event object for next round
    sync_capture_event = asyncio.Event()
    
    return {
        "status": "triggered",
        "triggered_agents": triggered_agents
    }


@app.post("/sync/report_error")
async def sync_report_error(request: SyncReportErrorRequest):
    """
    Agent reports an error condition (e.g., Unity window missing, API quota exceeded)
    
    Called by agents when they detect critical errors that should trigger system-wide stop.
    """
    global agent_errors
    
    with sync_lock:
        agent_errors[request.agent_id] = {
            "error_type": request.error_type,
            "message": request.message,
            "timestamp": datetime.now()
        }
    
    print(f"[SyncServer] Agent {request.agent_id} reported error: {request.error_type} - {request.message}")
    
    return {
        "status": "error_reported",
        "agent_id": request.agent_id,
        "error_type": request.error_type
    }


@app.post("/sync/trigger_stop")
async def sync_trigger_stop():
    """
    Trigger stop signal for all agents

    Called by Coordinator when it detects an error condition that requires
    all agents to stop gracefully.
    
    Note: This is an emergency stop. The stop signal is kept active (not reset)
    so that any agents that arrive later can also detect the stop state.
    """
    global sync_stop_signal, sync_stop_event

    with sync_lock:
        # Set stop signal (keep it True, don't reset for emergency stop)
        sync_stop_signal = True

    # Notify all waiting Agents to stop (immediate notification via Event)
    sync_stop_event.set()

    # Brief delay to ensure event propagation, then return immediately
    await asyncio.sleep(0.1)

    return {
        "status": "stop_triggered",
        "message": "All agents have been signaled to stop. Stop signal remains active."
    }


@app.delete("/sync/reset")
async def sync_reset():
    """
    Reset synchronization state

    Clear all synchronization-related state for debugging or restart.
    """
    global sync_expected_agents, sync_ready_agents, sync_capture_signal, sync_capture_event, sync_stop_signal, sync_stop_event

    with sync_lock:
        sync_expected_agents = set()
        sync_ready_agents = set()
        sync_capture_signal = False
        sync_stop_signal = False
        sync_capture_event = asyncio.Event()
        sync_stop_event = asyncio.Event()

        return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    import os
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    print(f"Starting Environment Messaging Server on {host}:{port}")
    print(f"API docs available at http://{host}:{port}/docs")
    
    uvicorn.run(app, host=host, port=port)


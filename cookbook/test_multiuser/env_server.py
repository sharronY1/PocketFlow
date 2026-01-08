"""
Centralized messaging server for multi-agent communication.

This FastAPI server provides:
1. Message passing system for agents to communicate with each other
2. Synchronization mechanism for coordinated screenshot capture

Architecture:
- Coordinator (中控 Agent) 通过 /sync/* API 协调所有子 Agent
- 子 Agent 通过 /sync/ready 报告已到达 PerceptionNode
- 子 Agent 通过 /sync/wait_capture 阻塞等待截屏信号
- Coordinator 通过 /sync/trigger_capture 发送统一截屏信号
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Set
import threading
from datetime import datetime
import asyncio

app = FastAPI(title="Environment Messaging Server", version="2.0.0")

# ==============================================================================
# Message System (消息系统)
# ==============================================================================
# In-memory message storage (mailbox system)
# Structure: {agent_id: [msg1, msg2, ...]}
message_mailboxes: Dict[str, List[Dict[str, Any]]] = {}
message_history: List[Dict[str, Any]] = []
agent_registry: Dict[str, datetime] = {}  # Track agent activity
lock = threading.Lock()  # Thread-safe access for messages

# ==============================================================================
# Synchronization System (同步系统)
# ==============================================================================
# 同步机制说明:
# 1. 子 Agent 运行到 PerceptionNode 时调用 /sync/ready 报告就绪
# 2. 子 Agent 调用 /sync/wait_capture 阻塞等待截屏信号
# 3. Coordinator 调用 /sync/status 检查是否所有 Agent 都就绪
# 4. Coordinator 调用 /sync/trigger_capture 发送截屏信号
# 5. 所有等待中的 Agent 收到信号后执行截屏，然后继续各自的 flow

# 预期参与同步的 Agent 集合
sync_expected_agents: Set[str] = set()

# 当前已报告 ready 的 Agent 集合
sync_ready_agents: Set[str] = set()

# 截屏信号标志 (True = 可以截屏)
sync_capture_signal: bool = False

# 同步系统的锁
sync_lock = threading.Lock()

# 用于通知等待中的 Agent 的事件
sync_capture_event = asyncio.Event()


class SendMessageRequest(BaseModel):
    sender: str
    recipient: str  # Can be specific agent_id or "all"
    message: str


class PollMessagesRequest(BaseModel):
    agent_id: str


class PollMessagesResponse(BaseModel):
    messages: List[Dict[str, Any]]


# ==============================================================================
# Synchronization Request/Response Models (同步请求/响应模型)
# ==============================================================================

class SyncRegisterAgentsRequest(BaseModel):
    """注册参与同步的 Agent 列表"""
    agent_ids: List[str]


class SyncReadyRequest(BaseModel):
    """子 Agent 报告已到达 PerceptionNode"""
    agent_id: str


class SyncWaitCaptureRequest(BaseModel):
    """子 Agent 等待截屏信号"""
    agent_id: str
    timeout: Optional[float] = 60.0  # 超时时间（秒）


class SyncStatusResponse(BaseModel):
    """同步状态响应"""
    expected_agents: List[str]
    ready_agents: List[str]
    all_ready: bool
    capture_signal: bool


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
# Synchronization APIs (同步 API)
# ==============================================================================
# 
# 使用流程:
# 1. Coordinator 启动时调用 POST /sync/register_agents 注册所有子 Agent
# 2. 子 Agent 运行到 PerceptionNode 时:
#    a. 调用 POST /sync/ready 报告就绪
#    b. 调用 POST /sync/wait_capture 阻塞等待截屏信号
# 3. Coordinator 循环:
#    a. 调用 GET /sync/status 检查是否所有 Agent 就绪
#    b. 当 all_ready=True 时，调用 POST /sync/trigger_capture 发送截屏信号
# 4. 所有子 Agent 收到信号后执行截屏，继续各自的 flow
# 5. 下一轮重复步骤 2-4
#

@app.post("/sync/register_agents")
async def sync_register_agents(request: SyncRegisterAgentsRequest):
    """
    注册参与同步的 Agent 列表
    
    由 Coordinator 在启动时调用，指定哪些 Agent 需要参与同步。
    这会清空之前的同步状态，开始新的同步会话。
    """
    global sync_expected_agents, sync_ready_agents, sync_capture_signal, sync_capture_event
    
    with sync_lock:
        sync_expected_agents = set(request.agent_ids)
        sync_ready_agents = set()
        sync_capture_signal = False
        # 创建新的事件对象
        sync_capture_event = asyncio.Event()
        
        return {
            "status": "registered",
            "expected_agents": list(sync_expected_agents),
            "count": len(sync_expected_agents)
        }


@app.post("/sync/ready")
async def sync_ready(request: SyncReadyRequest):
    """
    子 Agent 报告已到达 PerceptionNode，准备好截屏
    
    子 Agent 在 PerceptionNode.exec() 开始时调用此 API，
    表示自己已经准备好，等待 Coordinator 的截屏信号。
    """
    with sync_lock:
        # 添加到就绪集合
        sync_ready_agents.add(request.agent_id)
        
        # 检查是否所有预期的 Agent 都已就绪
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
    子 Agent 阻塞等待截屏信号
    
    子 Agent 在报告 ready 后调用此 API 阻塞等待。
    当 Coordinator 调用 trigger_capture 后，此 API 返回，
    子 Agent 即可执行截屏操作。
    
    Args:
        agent_id: Agent 标识符
        timeout: 最大等待时间（秒），默认 60 秒
    
    Returns:
        should_capture: True 表示可以截屏
    """
    global sync_capture_event
    
    # 获取当前的事件对象引用
    current_event = sync_capture_event
    
    try:
        # 等待截屏信号，带超时
        await asyncio.wait_for(
            current_event.wait(),
            timeout=request.timeout
        )
        return {
            "should_capture": True,
            "agent_id": request.agent_id
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
    获取当前同步状态
    
    Coordinator 轮询此 API 检查是否所有 Agent 都已就绪。
    当 all_ready=True 时，Coordinator 可以调用 trigger_capture。
    """
    with sync_lock:
        all_ready = sync_expected_agents and sync_ready_agents >= sync_expected_agents
        
        return SyncStatusResponse(
            expected_agents=list(sync_expected_agents),
            ready_agents=list(sync_ready_agents),
            all_ready=all_ready,
            capture_signal=sync_capture_signal
        )


@app.post("/sync/trigger_capture")
async def sync_trigger_capture():
    """
    触发统一截屏
    
    由 Coordinator 调用，当所有 Agent 都已就绪时触发截屏信号。
    这会:
    1. 设置 capture_signal = True
    2. 通知所有等待中的 Agent（通过 asyncio.Event）
    3. 清空 ready_agents 集合，为下一轮做准备
    """
    global sync_capture_signal, sync_ready_agents, sync_capture_event
    
    with sync_lock:
        # 设置截屏信号
        sync_capture_signal = True
        
        # 记录本轮就绪的 Agent（用于返回）
        triggered_agents = list(sync_ready_agents)
        
        # 清空就绪集合，为下一轮做准备
        sync_ready_agents = set()
    
    # 通知所有等待中的 Agent
    sync_capture_event.set()
    
    # 短暂延迟后重置信号和事件，为下一轮做准备
    await asyncio.sleep(0.1)
    
    with sync_lock:
        sync_capture_signal = False
    
    # 创建新的事件对象用于下一轮
    sync_capture_event = asyncio.Event()
    
    return {
        "status": "triggered",
        "triggered_agents": triggered_agents
    }


@app.delete("/sync/reset")
async def sync_reset():
    """
    重置同步状态
    
    清空所有同步相关的状态，用于调试或重新开始。
    """
    global sync_expected_agents, sync_ready_agents, sync_capture_signal, sync_capture_event
    
    with sync_lock:
        sync_expected_agents = set()
        sync_ready_agents = set()
        sync_capture_signal = False
        sync_capture_event = asyncio.Event()
        
        return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    import os
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    print(f"Starting Environment Messaging Server on {host}:{port}")
    print(f"API docs available at http://{host}:{port}/docs")
    
    uvicorn.run(app, host=host, port=port)


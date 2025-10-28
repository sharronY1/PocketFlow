"""
Centralized Environment Service (FastAPI)

Exposes endpoints for multi-machine agents to share environment state and messaging.

Endpoints:
- GET  /env/info
- POST /env/visible        {agent_id, position}
- POST /env/execute        {agent_id, action}
- POST /messages/send      {sender, recipient, message}
- POST /messages/poll      {agent_id}
"""

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any, List
import threading

from utils.environment import (
    create_environment,
    get_visible_objects,
    execute_action,
    add_message,
    get_messages_for,
)


app = FastAPI(title="PocketFlow Env Server", version="1.0.0")

env_lock = threading.Lock()
GLOBAL_ENV: Dict[str, Any] = create_environment(num_positions=10)


class VisibleRequest(BaseModel):
    agent_id: str
    position: int


class ExecuteRequest(BaseModel):
    agent_id: str
    action: str


class SendMessageRequest(BaseModel):
    sender: str
    recipient: str
    message: str


class PollMessageRequest(BaseModel):
    agent_id: str


@app.get("/env/info")
def env_info() -> Dict[str, Any]:
    with env_lock:
        total_objects = sum(len(objs) for objs in GLOBAL_ENV["objects"].values())
        return {
            "type": "remote",
            "num_positions": GLOBAL_ENV["num_positions"],
            "total_objects": total_objects,
            "boundaries": {"min": 0, "max": GLOBAL_ENV["num_positions"] - 1},
            "agent_positions": GLOBAL_ENV["agent_positions"],
            "explored_by_all_count": len(GLOBAL_ENV["explored_by_all"]),
            "explored_by_all": list(GLOBAL_ENV["explored_by_all"]),
        }


@app.post("/env/visible")
def env_visible(req: VisibleRequest) -> Dict[str, Any]:
    with env_lock:
        visible = get_visible_objects(req.position, GLOBAL_ENV)
        return {"visible_objects": visible}


@app.post("/env/execute")
def env_execute(req: ExecuteRequest) -> Dict[str, Any]:
    with env_lock:
        new_pos = execute_action(req.agent_id, req.action, GLOBAL_ENV)
        visible = get_visible_objects(new_pos, GLOBAL_ENV)
        return {
            "position": new_pos,
            "visible_objects": visible,
        }


@app.post("/messages/send")
def send_message(req: SendMessageRequest) -> Dict[str, Any]:
    with env_lock:
        add_message(GLOBAL_ENV, req.sender, req.recipient, req.message)
        return {"ok": True}


@app.post("/messages/poll")
def poll_messages(req: PollMessageRequest) -> Dict[str, Any]:
    with env_lock:
        messages = get_messages_for(GLOBAL_ENV, req.agent_id)
        return {"messages": messages}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("env_server:app", host="0.0.0.0", port=8000, reload=False)



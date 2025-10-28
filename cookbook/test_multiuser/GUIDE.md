Multi‑Agent XR Exploration — One‑Page Guide

This guide replaces ARCHITECTURE.md, PERCEPTION_GUIDE.md, and QUICKSTART.md. It reflects the current code: single‑agent CLI, centralized env server, remote messaging‑only mode, Unity control, and self‑message filtering.

## 1) TL;DR — Quickstart

- Install deps
```bash
pip install -r requirements.txt
```
- Start the centralized environment server (run once)
```bash
uvicorn env_server:app --host 0.0.0.0 --port 8000
```
- Start one agent per machine:
  - Remote agent (laptop; chat‑only optional)
```bash
# bash
export ENV_SERVER_URL=http://<server_ip>:8000
export OPENAI_API_KEY=your-key
# Optional: only chat, no environment exploration
# export MESSAGING_ONLY=1
python /home/monster/PocketFlow/cookbook/test_multiuser/main.py --perception remote --agent-id Laptop
```
  - Unity agent (lab; pyautogui controls the simulator)
```bash
# bash
export ENV_SERVER_URL=http://<server_ip>:8000
export OPENAI_API_KEY=your-key
# optional tuning
# export SCREENSHOT_DIR=/tmp/screens
# export SCREENSHOT_REGION=0,0,1280,720
# export KEY_FORWARD=w; export KEY_BACKWARD=s; export STEP_SLEEP=0.3
python /home/monster/PocketFlow/cookbook/test_multiuser/main.py --perception unity --agent-id Lab
```
- PowerShell equivalents
```powershell
$env:ENV_SERVER_URL = "http://<server_ip>:8000"
$env:OPENAI_API_KEY = "your-key"
# $env:MESSAGING_ONLY = "1"   # optional
python /home/monster/PocketFlow/cookbook/test_multiuser/main.py --perception remote --agent-id Laptop
```

## 2) Architecture (current)

- Single‑agent entrypoint
  - `main.py` runs exactly one agent per process via CLI: `--perception [mock|unity|remote]`, `--agent-id <ID>`.
  - Internally it builds a `Flow` (`create_agent_flow()`) and runs `run_agent(agent_id, shared, perception)`.

- Flow topology
  - `Perception -> RetrieveMemory -> Communication -> Decision -> Execution -> UpdateMemory` → loop on "continue".
  - Responsibilities:
    - Perception: read visible objects or capture screenshot (impl‑specific)
    - RetrieveMemory: vector search in per‑agent memory
    - Communication: poll messages (via perception)
    - Decision: LLM‑based, YAML output; supports `DISABLE_LLM=1` fallback
    - Execution: execute action, broadcast messages
    - UpdateMemory: store memory; stop when `max_steps` reached

- Shared state model
  - Local/mock/unity: a lightweight `global_env` exists in‑process (positions for summaries). Unity primarily uses the simulator + centralized messaging.
  - Distributed: `env_server.py` centralizes environment objects, positions, global explored set, and the message queue.

- Perception implementations (`PerceptionInterface`)
  - `MockPerception`: in‑process dict
  - `UnityPyAutoGUIPerception`: pyautogui keyboard control + screenshots; centralized messaging via `ENV_SERVER_URL`
  - `RemotePerception`: HTTP to `env_server`
    - Normal: uses `/env/visible`, `/env/execute`, `/env/info` + messaging
    - Messaging‑only: `MESSAGING_ONLY=1` (or `messaging_only=True`) disables environment calls; agent only chats

- Messaging semantics
  - Centralized via `env_server` (`/messages/send`, `/messages/poll`)
  - Self‑messages are filtered: agents won’t receive messages they sent (even when broadcasting to `all`)

- Memory & LLM
  - Each agent owns its FAISS‑backed memory. For smoke tests, use `DISABLE_EMBEDDING=1` and/or `DISABLE_LLM=1`.

## 3) Environment Server API

- `GET /env/info` → metadata including `agent_positions`, `total_objects`, `explored_by_all`
- `POST /env/visible` {agent_id, position} → `{visible_objects}`
- `POST /env/execute` {agent_id, action} → `{position, visible_objects}` (applies move, updates explored set)
- `POST /messages/send` {sender, recipient, message} → `{ok: true}`
- `POST /messages/poll` {agent_id} → `{messages: [...]}` (removes delivered; excludes sender==agent_id)

Notes
- Server starts with a random mock layout (used by remote agents unless messaging‑only).
- For pure messaging (e.g., laptop chat‑only + lab Unity), set laptop `MESSAGING_ONLY=1`.

## 4) Usage Patterns

- Single machine mock
```bash
python main.py --perception mock --agent-id Dev
```
- Laptop chat‑only + Lab Unity
```bash
uvicorn env_server:app --host 0.0.0.0 --port 8000
ENV_SERVER_URL=http://<server_ip>:8000 MESSAGING_ONLY=1 python main.py --perception remote --agent-id Laptop
ENV_SERVER_URL=http://<server_ip>:8000 python main.py --perception unity --agent-id Lab
```
- Two Unity machines
```bash
uvicorn env_server:app --host 0.0.0.0 --port 8000
ENV_SERVER_URL=http://<server_ip>:8000 python main.py --perception unity --agent-id LabA
ENV_SERVER_URL=http://<server_ip>:8000 python main.py --perception unity --agent-id LabB
```

## 5) Troubleshooting

- PowerShell vs bash: PowerShell `$env:VAR = "value"` | bash `export VAR=value` | CMD `set VAR=value && command`
- Accidentally started two agents: always run `python main.py --perception ... --agent-id ...` (don’t call `main.main(...)`)
- Unity doesn’t move or capture: ensure window focus; tweak `SCREENSHOT_REGION`, keymap, `STEP_SLEEP`
- Heavy deps: for smoke tests `DISABLE_LLM=1` / `DISABLE_EMBEDDING=1`

## 6) Recent Changes

- `main.py` single‑agent CLI (no two‑thread default)
- `RemotePerception` messaging‑only mode (`MESSAGING_ONLY=1`)
- Unity perception supports centralized messaging
- Self‑message filtering in queue
- README simplified

---
This guide supersedes previous docs and stays aligned with the codebase.


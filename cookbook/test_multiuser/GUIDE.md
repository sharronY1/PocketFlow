Multi‑Agent XR Exploration — One‑Page Guide

This guide replaces ARCHITECTURE.md, PERCEPTION_GUIDE.md, and QUICKSTART.md. It reflects the current code: single‑agent CLI, Unity control, and self‑message filtering.

## 1) TL;DR — Quickstart

- Install deps
```bash
pip install -r requirements.txt
```
- Start one agent:
  - Mock mode (simulated environment)
```bash
export OPENAI_API_KEY=your-key
python main.py --perception mock --agent-id Agent1
```
  - Unity agent (pyautogui controls the simulator)
```bash
export OPENAI_API_KEY=your-key
# optional tuning
# export SCREENSHOT_DIR=/tmp/screens
# export SCREENSHOT_REGION=0,0,1280,720
# export STEP_SLEEP=0.3
python main.py --perception unity --agent-id Lab
```
  - Unity Camera mode (camera extraction package)
```bash
export OPENAI_API_KEY=your-key
export UNITY_OUTPUT_BASE_PATH=/path/to/unity/output
python main.py --perception unity-camera --agent-id Agent1
```

## 2) Architecture (current)

- Single‑agent entrypoint
  - `main.py` runs exactly one agent per process via CLI: `--perception [mock|unity|unity-camera]`, `--agent-id <ID>`.
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
  - Local/mock/unity: shared memory exists in‑process (positions, objects, message mailboxes).

- Perception implementations (`PerceptionInterface`)
  - `MockPerception`: in‑process dict
  - `UnityPyAutoGUIPerception`: pyautogui keyboard control + screenshots
  - `UnityCameraPerception`: Unity camera extraction package integration

- Messaging semantics
  - Messages are managed via mailbox system in shared memory
  - Self‑messages are filtered: agents won't receive messages they sent (even when broadcasting to `all`)

- Memory & LLM
  - Each agent owns its FAISS‑backed memory. For smoke tests, use `DISABLE_EMBEDDING=1` and/or `DISABLE_LLM=1`.

## 3) Usage Patterns

- Single machine mock
```bash
python main.py --perception mock --agent-id Dev
```
- Unity mode
```bash
python main.py --perception unity --agent-id Lab
```
- Unity Camera mode
```bash
export UNITY_OUTPUT_BASE_PATH=/path/to/unity/output
python main.py --perception unity-camera --agent-id Agent1
```

## 4) Troubleshooting

- PowerShell vs bash: PowerShell `$env:VAR = "value"` | bash `export VAR=value` | CMD `set VAR=value && command`
- Accidentally started two agents: always run `python main.py --perception ... --agent-id ...` (don’t call `main.main(...)`)
- Unity doesn’t move or capture: ensure window focus; tweak `SCREENSHOT_REGION`, keymap, `STEP_SLEEP`
- Heavy deps: for smoke tests `DISABLE_LLM=1` / `DISABLE_EMBEDDING=1`

## 5) Recent Changes

- `main.py` single‑agent CLI (no two‑thread default)
- Unity perception supports messaging via shared memory
- Self‑message filtering in mailbox system
- README simplified

---
This guide supersedes previous docs and stays aligned with the codebase.


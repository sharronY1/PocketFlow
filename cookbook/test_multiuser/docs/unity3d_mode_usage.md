# Unity3D Mode Usage Guide

## Overview

The `unity3d` mode is a simplified Unity3D perception mode designed for basic navigation without requiring Meta XR Simulator window focus.

## Key Features

1. **No Window Focus Required**: Unlike `unity-camera` mode, this mode does not automatically focus the Meta XR Simulator window
2. **Simplified Action Space**: Only supports WSAD movement + Space (jump)
   - `forward` → W key
   - `backward` → S key
   - `move_left` → A key
   - `move_right` → D key
   - `jump` → Space key

## Setup

### Environment Variables

Set the following environment variables before running:

```bash
# Required
export UNITY_OUTPUT_BASE_PATH="/path/to/unity/output"

# Optional
export AGENT_REQUEST_DIR="/path/to/request/dir"  # Defaults to {UNITY_OUTPUT_BASE_PATH}/agent_requests
export STEP_SLEEP="0.3"  # Sleep time after each action (seconds)
export SCREENSHOT_TIMEOUT="5.0"  # Max time to wait for screenshot (seconds)
export MAX_STEPS="105"  # Maximum exploration steps
```

### Usage

#### Command Line

```bash
python main.py --perception unity3d --agent-id Agent1
```

Or set environment variable:

```bash
export PERCEPTION=unity3d
python main.py
```

#### Python Code

```python
from utils.perception_interface import create_perception

# Create unity3d perception instance
perception = create_perception(
    "unity3d",
    unity_output_base_path="/path/to/unity/output",
    agent_request_dir="/path/to/request/dir",  # Optional
    press_time=0.3,
    screenshot_timeout=5.0,
)

# Get environment info
info = perception.get_environment_info()
print(info)  # {'type': 'unity3d', 'unity_output_base_path': '...', 'agent_request_dir': '...'}

# Execute action
result = perception.execute_action("Agent1", "forward")

# Get visible objects (screenshots)
visible = perception.get_visible_objects("Agent1", position=0)
```

## Differences from Other Modes

| Feature | mock | unity | unity-camera | unity3d |
|---------|------|-------|--------------|---------|
| Window Focus | N/A | Yes | Yes | No |
| Screenshot Method | Simulated | pyautogui | Unity Camera | Unity Camera |
| Action Space | forward/backward | Full (12 actions) | Full (12 actions) | Simplified (5 actions) |
| Use Case | Testing | Full XR exploration | Full XR exploration | Basic Unity3D navigation |

## Action Space Comparison

### Full Action Space (unity, unity-camera)
- Movement: forward, backward, move_left, move_right, move_up, move_down
- Camera: look_left, look_right, look_up, look_down, tilt_left, tilt_right

### Simplified Action Space (unity3d)
- Movement: forward, backward, move_left, move_right
- Jump: jump

## Unity Setup

Make sure your Unity project has:

1. Camera extraction package installed
2. Screenshot output directory configured
3. Agent request directory configured
4. Unity application running and in focus (or foreground)

## Example Workflow

```bash
# 1. Set environment variables
export UNITY_OUTPUT_BASE_PATH="D:/Unity/Output"
export PERCEPTION=unity3d
export MAX_STEPS=50

# 2. Start Unity application

# 3. Run agent
python main.py --agent-id Agent1

# 4. Agent will:
#    - Request screenshots from Unity
#    - Analyze screenshots using vision AI
#    - Decide next action (forward/backward/move_left/move_right/jump)
#    - Execute action using pyautogui
#    - Repeat until MAX_STEPS reached
```

## Troubleshooting

### Screenshot Not Found

**Problem**: `[Unity3DPerception] Warning: Screenshot not found for agent...`

**Solutions**:
- Ensure Unity application is running
- Check `UNITY_OUTPUT_BASE_PATH` is correct
- Verify Unity has permissions to write to output directory
- Increase `SCREENSHOT_TIMEOUT` if Unity is slow

### Invalid Action Error

**Problem**: `Invalid action: <action_name>`

**Solutions**:
- Verify action is one of: forward, backward, move_left, move_right, jump
- Check DecisionNode is using correct action list for unity3d mode
- Review LLM output for malformed responses

### Unity Not Responding to Keys

**Problem**: Actions not executed in Unity

**Solutions**:
- Ensure Unity window is in focus (click on it manually)
- Check pyautogui is installed: `pip install pyautogui`
- Verify key bindings in Unity match action mappings (WSAD + Space)
- Adjust `STEP_SLEEP` if actions execute too quickly

## Notes

- The LLM (DecisionNode) automatically adapts to use only the 5 available actions in unity3d mode
- Screenshot processing is identical to unity-camera mode
- Messaging between agents works the same as other modes (requires ENV_SERVER_URL)


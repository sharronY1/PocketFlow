"""
Multi-Agent XR Environment Exploration System - Main Program
"""
import os
import sys
from utils import create_environment, create_memory
from utils.perception_interface import create_perception, PerceptionInterface
from utils.window_manager import find_and_focus_meta_xr_simulator
from utils.config_loader import get_config_value, sync_unity_config
from flow import create_agent_flow
import time
import argparse


def run_agent(agent_id: str, perception: PerceptionInterface, max_steps: int = 20):
    """
    Run exploration flow for a single agent
    
    Args:
        agent_id: Agent identifier
        perception: Perception interface instance
        max_steps: Maximum exploration steps
    """
    print(f"\n{'='*60}")
    print(f"Starting {agent_id}...")
    print(f"{'='*60}\n")
    
    # Create agent's memory store (renamed from agent_shared)
    memory = {
        # Basic identification
        "agent_id": agent_id,
        "perception": perception,
        
        # Position and step tracking
        "position": 0,
        "step_count": 0,
        "max_steps": max_steps,
        
        # Episodic memory system (FAISS vector index + texts)
        "memory_index": create_memory(dimension=384),
        "memory_texts": [],
        
        # Current observation state (updated each step)
        "visible_objects": {},  # dict format: {object_name: position_description}
        "visible_caption": "",  # text description of current view
        "retrieved_memories": [],  # top-k memories from FAISS search
        "other_agent_messages": [],  # messages received from other agents
        
        # Decision results (current step)
        "action": None,
        "action_reason": "",
        "message_to_others": "",
        
        # Exploration history (accumulated)
        "explored_objects": set(),  # all objects discovered by this agent
        "action_history": [],  # list of {step, position, action, visible, new_objects}
        "env_change": []  # list of {step, change, prev_image, curr_image} for environment changes
    }
    
    # Create and run flow
    flow = create_agent_flow()
    
    try:
        flow.run(memory)
    except Exception as e:
        print(f"\n[{agent_id}] Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"{agent_id} Exploration Summary")
    print(f"{'='*60}")
    print(f"Total steps: {memory['step_count']}")
    print(f"Final position: {memory['position']}")
    print(f"Unique objects explored: {len(memory['explored_objects'])}")
    print(f"Objects: {memory['explored_objects']}")
    print(f"Memories stored: {len(memory['memory_texts'])}")
    
    # Show sample memories (first 3)
    if memory['memory_texts']:
        print(f"\nSample memories:")
        for i, mem in enumerate(memory['memory_texts'][:3], 1):
            print(f"  {i}. {mem[:120]}...")
    
    print(f"{'='*60}\n")
    
    return memory


def main(perception_type: str = "mock", agent_id: str = "Agent"):
    """
    Main program entry point (single agent)
    
    Args:
        perception_type: Perception type ("mock", "unity", "unity-camera", or "unity3d")
        agent_id: Unique agent identifier
    """
    print("\n" + "="*60)
    print("Multi-Agent XR Environment Exploration System")
    print("="*60)
    
    # Sync Unity configuration file
    print("\n[System] Syncing Unity configuration...")
    sync_unity_config()
    
    # Read max_steps from config file
    max_steps_default = get_config_value("max_steps", 105 if perception_type in ["unity", "unity-camera", "unity3d"] else 3)
    max_steps = int(os.getenv("MAX_STEPS", str(max_steps_default)))
    
    # Create perception interface
    print(f"\n[System] Creating {perception_type} perception interface...")
    if perception_type == "mock":
        # Mock mode: use preset environment with predefined objects
        mock_env = create_environment(num_positions=10)
        print(f"[System] Mock environment created with {mock_env['num_positions']} positions")
        print("\n[System] Environment layout:")
        for pos in sorted(mock_env["objects"].keys()):
            print(f"  Position {pos}: {mock_env['objects'][pos]}")
        perception = create_perception("mock", env=mock_env)
        print("[System] Using MockPerception (simulated environment)")
    elif perception_type == "xr":
        # TODO: Configure real XR client
        # xr_client = YourXRClient(host="localhost", port=8080)
        # perception = create_perception("xr", xr_client=xr_client, config={...})
        print("[System] XR perception not yet implemented, falling back to mock")
        mock_env = create_environment(num_positions=10)
        perception = create_perception("mock", env=mock_env)
    elif perception_type == "unity":
        # Find and focus Meta XR Simulator window
        print("\n[System] Attempting to find and focus Meta XR Simulator window...")
        focus_success = find_and_focus_meta_xr_simulator()
        
        if not focus_success:
            print("[System] Error: Could not find Meta XR Simulator window.")
            print("[System] Please make sure Meta XR Simulator is running before starting the agent.")
            print("[System] Exiting...")
            sys.exit(1)
        
        # Unity window must be focused. Configure optional screenshot directory/region via env vars.
        screenshot_dir = os.getenv("SCREENSHOT_DIR")
        # SCREENSHOT_REGION format: left,top,width,height
        region_str = os.getenv("SCREENSHOT_REGION", "").strip()
        capture_region = None
        if region_str:
            try:
                parts = [int(x) for x in region_str.split(',')]
                if len(parts) == 4:
                    capture_region = tuple(parts)  # type: ignore
            except Exception:
                pass
        perception = create_perception(
            "unity",
            screenshot_dir=screenshot_dir,
            capture_region=capture_region,
            step_sleep_seconds=float(os.getenv("STEP_SLEEP", "0.3")),
        )
        print("[System] Using UnityPyAutoGUIPerception (pyautogui).")
    elif perception_type == "unity-camera":
        # Unity camera extraction package integration (Agent-controlled screenshots)
        # Find and focus Meta XR Simulator window (same as unity mode)
        print("\n[System] Attempting to find and focus Meta XR Simulator window...")
        focus_success = find_and_focus_meta_xr_simulator()
        
        if not focus_success:
            print("[System] Warning: Could not find Meta XR Simulator window.")
            print("[System] The agent will continue, but Unity window may not be focused.")
            print("[System] Make sure Meta XR Simulator is running for best results.")
        
        # Priority: environment variable > config file
        unity_output_base_path = os.getenv("UNITY_OUTPUT_BASE_PATH") or get_config_value("unity_output_base_path")
        if not unity_output_base_path:
            raise ValueError("UNITY_OUTPUT_BASE_PATH is required (set in config.json or environment variable)")
        agent_request_dir = os.getenv("AGENT_REQUEST_DIR")  # Optional
        perception = create_perception(
            "unity-camera",
            unity_output_base_path=unity_output_base_path,
            agent_request_dir=agent_request_dir,
            step_sleep_seconds=float(os.getenv("STEP_SLEEP", "0.3")),
            screenshot_timeout=float(os.getenv("SCREENSHOT_TIMEOUT", "5.0")),
        )
        print("[System] Using UnityCameraPerception (camera extraction package). Make sure Unity is running with autoScreenshotEnabled=false.")
    elif perception_type == "unity3d":
        # Simplified Unity3D perception mode (WSAD + Space only, no window focus required)
        print("\n[System] Using unity3d mode for Unity3D (no window focus required)")
        
        # Priority: environment variable > config file
        unity_output_base_path = get_config_value("unity_output_base_path") or os.getenv("UNITY_OUTPUT_BASE_PATH")
        if not unity_output_base_path:
            raise ValueError("UNITY_OUTPUT_BASE_PATH is required (set in config.json or environment variable)")
        agent_request_dir = os.getenv("AGENT_REQUEST_DIR")  # Optional
        perception = create_perception(
            "unity3d",
            unity_output_base_path=unity_output_base_path,
            agent_request_dir=agent_request_dir,
            # Default press duration 1.0s for clearer movement in unity3d mode
            step_sleep_seconds=float(os.getenv("STEP_SLEEP", "1")),
            screenshot_timeout=float(os.getenv("SCREENSHOT_TIMEOUT", "5.0")),
        )
        print("[System] Using Unity3DPerception (simplified action space: WSAD + Space). Make sure Unity is running.")
    else:
        raise ValueError(f"Unknown perception type: {perception_type}")
    
    env_info = perception.get_environment_info()
    print(f"[System] Environment info: {env_info}")
    print(f"[System] Max steps: {max_steps}")
    
    print("\n[System] Starting agent...")
    start_time = time.time()
    final_memory = run_agent(agent_id, perception, max_steps)
    elapsed_time = time.time() - start_time
    
    # Print overall summary
    print("\n" + "="*60)
    print("FINAL SYSTEM SUMMARY")
    print("="*60)
    print(f"Total execution time: {elapsed_time:.2f} seconds")
    print(f"Total unique objects discovered: {len(final_memory['explored_objects'])}")
    print(f"Objects: {final_memory['explored_objects']}")
    print("="*60)
    
    print("\n[System] Exploration completed!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a single exploration agent")
    parser.add_argument("--perception", default=os.getenv("PERCEPTION", "unity"), choices=["mock", "unity", "unity-camera", "unity3d"], help="Perception type")
    parser.add_argument("--agent-id", default=os.getenv("AGENT_ID", "Agent"), help="Unique agent id")
    args = parser.parse_args()
    main(args.perception, args.agent_id)

"""
Multi-Agent XR Environment Exploration System - Main Program
"""
import os
from utils import create_environment, create_shared_memory, create_memory
from utils.perception_interface import create_perception, PerceptionInterface
from flow import create_agent_flow
import time
import argparse


def run_agent(agent_id: str, shared_memory: dict, perception: PerceptionInterface, max_steps: int = 20):
    """
    Run exploration flow for a single agent
    
    Args:
        agent_id: Agent identifier
        shared_memory: Shared memory structure (replaces global_env for Unity mode)
        perception: Perception interface instance
        max_steps: Maximum exploration steps
    """
    print(f"\n{'='*60}")
    print(f"Starting {agent_id}...")
    print(f"{'='*60}\n")
    
    # Create agent's private shared store
    agent_shared = {
        "agent_id": agent_id,
        "shared_memory": shared_memory,  # Shared memory accessible by all agents
        "perception": perception,  # Add perception interface
        "position": 0,
        "step_count": 0,
        
        # Memory system
        "memory_index": create_memory(dimension=384),
        "memory_texts": [],
        
        # Current state
        "visible_objects": [],
        "retrieved_memories": [],
        "other_agent_messages": [],
        
        # Decision results
        "action": None,
        "action_reason": "",
        "message_to_others": "",
        
        # Exploration history
        "explored_objects": set(),
        "action_history": []
    }
    
    # Initialize agent position in shared memory
    if shared_memory:
        shared_memory["agent_positions"][agent_id] = 0
    
    # Create and run flow
    flow = create_agent_flow()
    
    try:
        flow.run(agent_shared)
    except Exception as e:
        print(f"\n[{agent_id}] Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"{agent_id} Exploration Summary")
    print(f"{'='*60}")
    print(f"Total steps: {agent_shared['step_count']}")
    print(f"Final position: {agent_shared['position']}")
    print(f"Unique objects explored: {len(agent_shared['explored_objects'])}")
    print(f"Objects: {agent_shared['explored_objects']}")
    print(f"Memories stored: {len(agent_shared['memory_texts'])}")
    
    # Show sample memories (first 3)
    if agent_shared['memory_texts']:
        print(f"\nSample memories:")
        for i, mem in enumerate(agent_shared['memory_texts'][:3], 1):
            print(f"  {i}. {mem[:120]}...")
    
    print(f"{'='*60}\n")


def main(perception_type: str = "mock", agent_id: str = "Agent"):
    """
    Main program entry point (single agent)
    
    Args:
        perception_type: Perception type ("mock", "unity", or "unity-camera")
        agent_id: Unique agent identifier
    """
    print("\n" + "="*60)
    print("Multi-Agent XR Environment Exploration System")
    print("="*60)
    
    # Create shared memory for Unity mode (dynamic object discovery)
    # For mock mode, still use create_environment with preset objects
    print("\n[System] Creating shared memory...")
    if perception_type == "unity" or perception_type == "unity-camera":
        # Unity mode: use shared memory where objects are discovered dynamically
        shared_memory = create_shared_memory()
        shared_memory["max_steps"] = int(os.getenv("MAX_STEPS", "3"))
        print("[System] Shared memory created for Unity mode (objects will be discovered dynamically)")
    elif perception_type == "mock":
        # Mock mode: use preset environment with predefined objects
        shared_memory = create_environment(num_positions=10)
        shared_memory["max_steps"] = int(os.getenv("MAX_STEPS", "3"))
        print(f"[System] Mock environment created with {shared_memory['num_positions']} positions")
        print("\n[System] Environment layout:")
        for pos in sorted(shared_memory["objects"].keys()):
            print(f"  Position {pos}: {shared_memory['objects'][pos]}")
    
    # Create perception interface
    print(f"\n[System] Creating {perception_type} perception interface...")
    if perception_type == "mock":
        # perception is a mock perception interface
        perception = create_perception("mock", env=shared_memory)
        print("[System] Using MockPerception (simulated environment)")
    elif perception_type == "xr":
        # TODO: Configure real XR client
        # xr_client = YourXRClient(host="localhost", port=8080)
        # perception = create_perception("xr", xr_client=xr_client, config={...})
        print("[System] XR perception not yet implemented, falling back to mock")
        perception = create_perception("mock", env=shared_memory)
    elif perception_type == "unity":
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
        print("[System] Using UnityPyAutoGUIPerception (pyautogui). Make sure the Unity window is focused.")
    elif perception_type == "unity-camera":
        # Unity camera extraction package integration (Agent-controlled screenshots)
        unity_output_base_path = os.getenv("UNITY_OUTPUT_BASE_PATH")
        if not unity_output_base_path:
            raise ValueError("UNITY_OUTPUT_BASE_PATH environment variable is required for unity-camera perception")
        agent_request_dir = os.getenv("AGENT_REQUEST_DIR")  # Optional
        perception = create_perception(
            "unity-camera",
            unity_output_base_path=unity_output_base_path,
            agent_request_dir=agent_request_dir,
            step_sleep_seconds=float(os.getenv("STEP_SLEEP", "0.3")),
            screenshot_timeout=float(os.getenv("SCREENSHOT_TIMEOUT", "5.0")),
        )
        print("[System] Using UnityCameraPerception (camera extraction package). Make sure Unity is running with autoScreenshotEnabled=false.")
    else:
        raise ValueError(f"Unknown perception type: {perception_type}")
    
    env_info = perception.get_environment_info()
    print(f"[System] Environment info: {env_info}")
    
    print("\n[System] Starting agent...")
    start_time = time.time()
    run_agent(agent_id, shared_memory, perception, 15)
    elapsed_time = time.time() - start_time
    
    # Print overall summary
    print("\n" + "="*60)
    print("FINAL SYSTEM SUMMARY")
    print("="*60)
    print(f"Total execution time: {elapsed_time:.2f} seconds")
    
    # Print shared memory summary
    if "objects" in shared_memory:
        objects = shared_memory["objects"]
        print(f"Total unique objects discovered by all agents: {len(objects)}")
        print(f"Objects: {objects}")
    else:
        print("No objects discovered (shared memory not used)")
    
    print(f"\nFinal agent positions:")
    for aid, pos in shared_memory.get("agent_positions", {}).items():
        print(f"  {aid}: position {pos}")
    
    # Print message history
    if "message_history" in shared_memory and shared_memory["message_history"]:
        print(f"\nMessage history ({len(shared_memory['message_history'])} messages):")
        for i, msg in enumerate(shared_memory["message_history"][:10], 1):  # Show first 10
            print(f"  {i}. {msg['sender']} → {msg['recipient']}: {msg['message'][:80]}")
        if len(shared_memory["message_history"]) > 10:
            print(f"  ... and {len(shared_memory['message_history']) - 10} more messages")
    
    print("="*60)
    
    print("\n[System] Exploration completed!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a single exploration agent")
    parser.add_argument("--perception", default=os.getenv("PERCEPTION", "unity"), choices=["mock", "unity", "unity-camera"], help="Perception type")
    parser.add_argument("--agent-id", default=os.getenv("AGENT_ID", "Agent"), help="Unique agent id")
    args = parser.parse_args()
    main(args.perception, args.agent_id)


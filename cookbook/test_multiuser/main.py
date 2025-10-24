"""
Multi-Agent XR Environment Exploration System - Main Program
"""
import threading
import os
from utils import create_environment, create_memory
from utils.perception_interface import create_perception, PerceptionInterface
from flow import create_agent_flow
import time


def run_agent(agent_id: str, global_env: dict, perception: PerceptionInterface, max_steps: int = 20):
    """
    Run exploration flow for a single agent
    
    Args:
        agent_id: Agent identifier
        global_env: Global shared environment
        perception: Perception interface instance
        max_steps: Maximum exploration steps
    """
    print(f"\n{'='*60}")
    print(f"Starting {agent_id}...")
    print(f"{'='*60}\n")
    
    # Create agent's private shared store
    agent_shared = {
        "agent_id": agent_id,
        "global_env": global_env,
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
    
    # Initialize agent position in environment
    global_env["agent_positions"][agent_id] = 0
    
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
    print(f"{'='*60}\n")


def main(perception_type: str = "mock"):
    """
    Main program entry point
    
    Args:
        perception_type: Perception type ("mock" or "xr")
    """
    print("\n" + "="*60)
    print("Multi-Agent XR Environment Exploration System")
    print("="*60)
    
    # Create global environment (still used for positions/messages even in unity mode)
    print("\n[System] Creating environment...")
    global_env = create_environment(num_positions=10)
    global_env["max_steps"] = int(os.getenv("MAX_STEPS", "3"))
    
    # Only print mock layout when using mock
    if perception_type == "mock":
        print(f"[System] Environment created with {global_env['num_positions']} positions")
        print("\n[System] Environment layout:")
        for pos in sorted(global_env["objects"].keys()):
            print(f"  Position {pos}: {global_env['objects'][pos]}")
    
    # Create perception interface
    print(f"\n[System] Creating {perception_type} perception interface...")
    if perception_type == "mock":
        # perception is a mock perception interface
        perception = create_perception("mock", env=global_env)
        print("[System] Using MockPerception (simulated environment)")
    elif perception_type == "xr":
        # TODO: Configure real XR client
        # xr_client = YourXRClient(host="localhost", port=8080)
        # perception = create_perception("xr", xr_client=xr_client, config={...})
        print("[System] XR perception not yet implemented, falling back to mock")
        perception = create_perception("mock", env=global_env)
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
            keymap={"forward": os.getenv("KEY_FORWARD", "w"), "backward": os.getenv("KEY_BACKWARD", "s")},
            step_sleep_seconds=float(os.getenv("STEP_SLEEP", "0.3")),
        )
        print("[System] Using UnityPyAutoGUIPerception (pyautogui). Make sure the Unity window is focused.")
    else:
        raise ValueError(f"Unknown perception type: {perception_type}")
    
    env_info = perception.get_environment_info()
    print(f"[System] Environment info: {env_info}")
    
    # Create two agent threads
    print("\n[System] Starting 2 agents...")
    
    agent1_thread = threading.Thread(
        target=run_agent,
        args=("Agent1", global_env, perception, 15),
        name="Agent1Thread"
    )
    
    agent2_thread = threading.Thread(
        target=run_agent,
        args=("Agent2", global_env, perception, 15),
        name="Agent2Thread"
    )
    
    # Start threads
    start_time = time.time()
    agent1_thread.start()
    agent2_thread.start()
    
    # Wait for both agents to complete
    agent1_thread.join()
    agent2_thread.join()
    
    elapsed_time = time.time() - start_time
    
    # Print overall summary
    print("\n" + "="*60)
    print("FINAL SYSTEM SUMMARY")
    print("="*60)
    print(f"Total execution time: {elapsed_time:.2f} seconds")
    print(f"Total unique objects explored by all agents: {len(global_env['explored_by_all'])}")
    print(f"Objects: {global_env['explored_by_all']}")
    print(f"Coverage: {len(global_env['explored_by_all'])} / {sum(len(objs) for objs in global_env['objects'].values())} objects")
    print(f"Final agent positions:")
    for agent_id, pos in global_env["agent_positions"].items():
        print(f"  {agent_id}: position {pos}")
    print("="*60)
    
    print("\n[System] Exploration completed!")


if __name__ == "__main__":
    main("unity")


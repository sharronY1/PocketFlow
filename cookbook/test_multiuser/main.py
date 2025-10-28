"""
Multi-Agent XR Environment Exploration System - Main Program
"""
import os
from utils import create_environment, create_memory
from utils.perception_interface import create_perception, PerceptionInterface
from flow import create_agent_flow
import time
import argparse


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


def main(perception_type: str = "mock", agent_id: str = "Agent"):
    """
    Main program entry point (single agent)
    
    Args:
        perception_type: Perception type ("mock", "unity", or "remote")
        agent_id: Unique agent identifier
    """
    print("\n" + "="*60)
    print("Multi-Agent XR Environment Exploration System")
    print("="*60)
    
    # Create global environment only for local/mock/unity modes
    print("\n[System] Creating environment...")
    if perception_type in ("mock", "unity"):
        global_env = create_environment(num_positions=10)
        global_env["max_steps"] = int(os.getenv("MAX_STEPS", "3"))
    else:
        # For remote mode, keep a lightweight dict for non-shared fields
        global_env = {"max_steps": int(os.getenv("MAX_STEPS", "3")), "agent_positions": {}}
    
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
            step_sleep_seconds=float(os.getenv("STEP_SLEEP", "0.3")),
        )
        print("[System] Using UnityPyAutoGUIPerception (pyautogui). Make sure the Unity window is focused.")
    elif perception_type == "remote":
        base_url = os.getenv("ENV_SERVER_URL")
        if not base_url:
            raise ValueError("ENV_SERVER_URL is required for remote perception")
        perception = create_perception("remote", base_url=base_url)
        print(f"[System] Using RemotePerception at {base_url}")
    else:
        raise ValueError(f"Unknown perception type: {perception_type}")
    
    env_info = perception.get_environment_info()
    print(f"[System] Environment info: {env_info}")
    
    print("\n[System] Starting agent...")
    start_time = time.time()
    run_agent(agent_id, global_env, perception, 15)
    elapsed_time = time.time() - start_time
    
    # Print overall summary
    print("\n" + "="*60)
    print("FINAL SYSTEM SUMMARY")
    print("="*60)
    print(f"Total execution time: {elapsed_time:.2f} seconds")
    # Support both local and remote modes
    explored = None
    total_objects = None
    if "explored_by_all" in global_env and "objects" in global_env:
        explored = global_env["explored_by_all"]
        total_objects = sum(len(objs) for objs in global_env["objects"].values())
    else:
        try:
            info = perception.get_environment_info()
            explored = set(info.get("explored_by_all", []))
            total_objects = int(info.get("total_objects", 0))
        except Exception:
            explored = set()
            total_objects = 0
    print(f"Total unique objects explored by all agents: {len(explored)}")
    print(f"Objects: {explored}")
    print(f"Coverage: {len(explored)} / {total_objects} objects")
    print(f"Final agent positions:")
    for aid, pos in global_env["agent_positions"].items():
        print(f"  {aid}: position {pos}")
    print("="*60)
    
    print("\n[System] Exploration completed!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a single exploration agent")
    parser.add_argument("--perception", default=os.getenv("PERCEPTION", "unity"), choices=["mock", "unity", "remote"], help="Perception type")
    parser.add_argument("--agent-id", default=os.getenv("AGENT_ID", "Agent"), help="Unique agent id")
    args = parser.parse_args()
    main(args.perception, args.agent_id)


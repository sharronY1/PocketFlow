"""
Coordinator Main Program - Entry point for the Coordinator Agent

Usage:
======
Start the Coordinator Agent to coordinate synchronized screenshots across multiple sub-agents:

    python coordinator_main.py --agents Agent1 Agent2 Agent3 --server http://localhost:8000

Arguments:
    --agents        Required, list of sub-agent IDs to synchronize
    --server        Optional, sync server URL (default: http://localhost:8000)
    --rounds        Optional, maximum rounds (default: 100)
    --poll-interval Optional, polling interval in seconds (default: 0.5)
    --timeout       Optional, wait timeout in seconds (default: 120)

Environment Variables:
    SYNC_SERVER_URL    Sync server URL
    MAX_ROUNDS         Maximum rounds

System Architecture:
====================

1. Startup Sequence:
   ┌─────────────────────────────────────────────────────────┐
   │ Step 1: Start env_server.py (sync server)              │
   │         python env_server.py                            │
   │         Ensure accessible at http://localhost:8000      │
   └─────────────────────────────────────────────────────────┘
                            ↓
   ┌─────────────────────────────────────────────────────────┐
   │ Step 2: Start Coordinator                               │
   │         python coordinator_main.py --agents Agent1 Agent2│
   │         Coordinator registers expected agent list       │
   └─────────────────────────────────────────────────────────┘
                            ↓
   ┌─────────────────────────────────────────────────────────┐
   │ Step 3: Start sub-agents (can be on different computers)│
   │         python main.py --agent-id Agent1 --sync         │
   │         python main.py --agent-id Agent2 --sync         │
   │         Sub-agents report ready at PerceptionNode       │
   └─────────────────────────────────────────────────────────┘

2. Synchronization Flow:
   
   SubAgent1: PerceptionNode → ready → wait...
   SubAgent2: PerceptionNode → ready → wait...
                                       ↓
   Coordinator: CollectStatus → all ready!
   Coordinator: Decision → capture_all
   Coordinator: Dispatch → trigger_capture
                                       ↓
   SubAgent1: receive signal → capture → continue flow...
   SubAgent2: receive signal → capture → continue flow...
                                       ↓
   (next round repeats)
"""

import os
import sys
import argparse
import requests
from typing import List
import time

from coordinator_flow import create_coordinator_flow
from utils.config_loader import get_config_value
from utils.logger import setup_logger, close_logger


def register_agents(server_url: str, agent_ids: List[str]) -> bool:
    """
    Register participating agents with the sync server
    
    This step must be completed before sub-agents start,
    telling the sync server which agents to wait for.
    
    Args:
        server_url: Sync server URL
        agent_ids: List of agent IDs participating in sync
        
    Returns:
        True if successful, False otherwise
    """
    try:
        print(f"[Coordinator] Registering agents: {agent_ids}")
        resp = requests.post(
            f"{server_url}/sync/register_agents",
            json={"agent_ids": agent_ids},
            timeout=10
        )
        resp.raise_for_status()
        
        data = resp.json()
        print(f"[Coordinator] Registration successful!")
        print(f"[Coordinator] Expected agents: {data.get('expected_agents', [])}")
        return True
        
    except requests.RequestException as e:
        print(f"[Coordinator] Error registering agents: {e}")
        return False


def check_server_health(server_url: str) -> bool:
    """
    Check if sync server is available
    
    Args:
        server_url: Sync server URL
        
    Returns:
        True if server is healthy, False otherwise
    """
    try:
        resp = requests.get(f"{server_url}/", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("status") == "running":
            print(f"[Coordinator] Sync server is running at {server_url}")
            return True
        else:
            print(f"[Coordinator] Unexpected server status: {data}")
            return False
            
    except requests.RequestException as e:
        print(f"[Coordinator] Cannot connect to sync server at {server_url}: {e}")
        return False


def run_coordinator(
    server_url: str,
    agent_ids: List[str],
    max_rounds: int = 100,
    poll_interval: float = 0.5,
    wait_timeout: float = 120.0,
    max_consecutive_timeouts: int = 3
):
    """
    Run Coordinator Flow
    
    Args:
        server_url: Sync server URL
        agent_ids: List of agent IDs participating in sync
        max_rounds: Maximum synchronization rounds
        poll_interval: Polling interval (seconds)
        wait_timeout: Wait timeout (seconds)
    """
    # Setup logger to write all console output to file
    log_file = setup_logger(name="Coordinator", log_dir="logs")
    print(f"[System] Log file: {log_file}")
    
    print("\n" + "=" * 60)
    print("Multi-Agent Coordinator")
    print("=" * 60)
    print(f"Sync server: {server_url}")
    print(f"Agents to coordinate: {agent_ids}")
    print(f"Max rounds: {max_rounds}")
    print(f"Poll interval: {poll_interval}s")
    print(f"Wait timeout: {wait_timeout}s")
    print("=" * 60 + "\n")
    
    # Step 1: Check server health
    if not check_server_health(server_url):
        print("\n[Coordinator] Error: Sync server is not available!")
        print("[Coordinator] Please start env_server.py first:")
        print("    python env_server.py")
        sys.exit(1)
    
    # Step 2: Register agents
    if not register_agents(server_url, agent_ids):
        print("\n[Coordinator] Error: Failed to register agents!")
        sys.exit(1)
    
    # Step 3: Initialize shared store
    shared = {
        # Configuration parameters
        "sync_server_url": server_url,
        "agent_ids": agent_ids,
        "max_rounds": max_rounds,
        "poll_interval": poll_interval,
        "wait_timeout": wait_timeout,

        "max_consecutive_timeouts": max_consecutive_timeouts,
        "consecutive_timeouts": 0,

        # Runtime state
        "round": 0,
        "current_status": {},
        "current_decision": {},
        "should_continue": True,
        "dispatch_result": {},
    }
    
    # Step 4: Create and run Flow
    print("\n[Coordinator] Starting coordination loop...")
    print("[Coordinator] Waiting for agents to connect...")
    print("[Coordinator] (Start your agents with --sync flag now)")
    print()
    
    flow = create_coordinator_flow()
    start_time = time.time()
    
    try:
        flow.run(shared)
    except KeyboardInterrupt:
        print("\n\n[Coordinator] Interrupted by user")
    except Exception as e:
        print(f"\n[Coordinator] Error: {e}")
        import traceback
        traceback.print_exc()
    
    elapsed_time = time.time() - start_time
    
    # Step 5: Print summary
    print("\n" + "=" * 60)
    print("Coordinator Summary")
    print("=" * 60)
    print(f"Total rounds completed: {shared.get('round', 0)}")
    print(f"Total execution time: {elapsed_time:.2f} seconds")
    print(f"Average time per round: {elapsed_time / max(1, shared.get('round', 1)):.2f} seconds")
    print("=" * 60)
    print("\n[Coordinator] Coordination completed!")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Run the Coordinator for multi-agent synchronized screenshots",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage with two agents
  python coordinator_main.py --agents Agent1 Agent2
  
  # Custom server URL and more rounds
  python coordinator_main.py --agents Agent1 Agent2 Agent3 --server http://192.168.1.100:8000 --rounds 200
  
  # With shorter timeout and poll interval
  python coordinator_main.py --agents Agent1 Agent2 --timeout 60 --poll-interval 0.2
        """
    )
    
    parser.add_argument(
        "--agents",
        nargs="+",
        required=True,
        help="List of agent IDs to coordinate (e.g., --agents Agent1 Agent2)"
    )
    
    parser.add_argument(
        "--server",
        default=os.getenv("SYNC_SERVER_URL") or get_config_value("env_server_url") or "http://localhost:8000",
        help="Sync server URL (default: from config.json env_server_url)"
    )
    
    parser.add_argument(
        "--rounds",
        type=int,
        default=int(os.getenv("MAX_ROUNDS", "100")),
        help="Maximum number of synchronization rounds (default: 100)"
    )
    
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.5,
        help="Polling interval in seconds (default: 0.5)"
    )
    
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Wait timeout in seconds (default: 120)"
    )


    parser.add_argument(
        "--max-consecutive-timeouts",
        type=int,
        default=3,
        help="Maximum consecutive timeouts before emergency stop (default: 3)"
    )
    
    args = parser.parse_args()
    
    run_coordinator(
        server_url=args.server,
        agent_ids=args.agents,
        max_rounds=args.rounds,
        poll_interval=args.poll_interval,
        wait_timeout=args.timeout,
        max_consecutive_timeouts=args.max_consecutive_timeouts
    )


if __name__ == "__main__":
    main()

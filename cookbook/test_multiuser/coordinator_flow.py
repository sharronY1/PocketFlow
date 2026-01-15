"""
Coordinator Flow for Multi-Agent Synchronized Screenshot System

Architecture Overview:
======================
                    Coordinator Flow
    ┌─────────────────────────────────────────────────┐
    │                                                 │
    │  CollectStatusNode → DecisionNode → DispatchNode│
    │         ↑                               │       │
    │         └───────── "continue" ──────────┘       │
    │                    "end" → finish               │
    └─────────────────────────────────────────────────┘
                         │
                         ▼
    ┌──────────────────────────────────────────────────┐
    │              Sync Server (env_server.py)         │
    │  /sync/status  /sync/trigger_capture             │
    └──────────────────────────────────────────────────┘
                         │
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
      ┌─────────┐   ┌─────────┐   ┌─────────┐
      │ Agent 1 │   │ Agent 2 │   │ Agent N │
      │(SubFlow)│   │(SubFlow)│   │(SubFlow)│
      └─────────┘   └─────────┘   └─────────┘

Synchronization Flow:
=====================
1. All sub-agents run to PerceptionNode → report "ready" to sync server → block and wait
2. Coordinator's CollectStatusNode detects all agents are ready
3. Coordinator's DecisionNode decides to trigger capture (extensible interface reserved)
4. Coordinator's DispatchNode sends unified capture signal
5. All sub-agents receive signal → capture screenshot simultaneously → continue their flow
6. Sub-agents complete current round → enter next PerceptionNode → report ready
7. Repeat steps 2-6

Key Design Decisions:
=====================
- No round number needed: All agents block and wait, capture simultaneously, naturally synchronized
- No WaitResultNode needed: After capture, agents naturally enter next round and report ready
- DecisionNode reserves LLM extension interface: Simple implementation now, can add intelligent decisions later
"""

from pocketflow import Flow, Node
from typing import Dict, List, Any, Optional
import requests
import time
import os


class CollectStatusNode(Node):
    """
    Collect status node for all sub-agents

    Responsibilities:
    - Poll sync server to check if all agents have reported ready
    - When all agents are ready, return "default" to continue to DecisionNode
    - On timeout, return "timeout" for error handling

    How it works:
    - Sub-agents call /sync/ready in PerceptionNode.exec() to report ready
    - This node calls /sync/status to check all_ready status
    - Poll interval and timeout are configurable
    """

    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """Prep phase: Get configuration parameters"""
        return {
            "sync_server_url": shared["sync_server_url"],
            "agent_ids": shared["agent_ids"],
            "poll_interval": shared.get("poll_interval", 0.5),  # Poll interval (seconds)
            "wait_timeout": shared.get("wait_timeout", 120),    # Wait timeout (seconds)
            "round": shared.get("round", 0),
            "consecutive_timeouts": shared.get("consecutive_timeouts", 0),
            "max_consecutive_timeouts": shared.get("max_consecutive_timeouts", 3)
        }
    
    def exec(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """
        Exec phase: Poll and wait for all agents to be ready

        Returns:
            {
                "all_ready": bool,      # Whether all agents are ready
                "ready_agents": list,   # List of ready agents
                "timeout": bool,        # Whether timeout occurred
                "round": int            # Current round number
            }
        """
        server_url = prep_res["sync_server_url"]
        agent_ids = prep_res["agent_ids"]
        poll_interval = prep_res["poll_interval"]
        timeout = prep_res["wait_timeout"]
        current_round = prep_res["round"]

        print(f"[Coordinator] Round {current_round + 1}: Waiting for all agents to be ready...")
        print(f"[Coordinator] Expected agents: {agent_ids}")

        start_time = time.time()
        last_status = {}

        while time.time() - start_time < timeout:
            try:
                # Call sync server to get status
                resp = requests.get(f"{server_url}/sync/status", timeout=10)
                resp.raise_for_status()
                status = resp.json()

                ready_agents = status.get("ready_agents", [])
                all_ready = status.get("all_ready", False)
                agent_errors = status.get("agent_errors", {})

                # Check for agent errors (Unity window missing, API quota, etc.)
                if agent_errors:
                    print(f"[Coordinator] CRITICAL: Agent errors detected!")
                    for agent_id, error_info in agent_errors.items():
                        error_type = error_info.get("error_type", "unknown")
                        error_msg = error_info.get("message", "")
                        print(f"[Coordinator]   Agent {agent_id}: {error_type} - {error_msg}")
                    
                    return {
                        "all_ready": False,
                        "ready_agents": ready_agents,
                        "timeout": False,
                        "round": current_round,
                        "agent_error_detected": True,
                        "agent_errors": agent_errors
                    }

                # Only print when status changes
                if status != last_status:
                    print(f"[Coordinator] Status: {len(ready_agents)}/{len(agent_ids)} agents ready")
                    if ready_agents:
                        print(f"[Coordinator] Ready: {ready_agents}")
                    last_status = status

                if all_ready:
                    print(f"[Coordinator] All agents are ready!")
                    return {
                        "all_ready": True,
                        "ready_agents": ready_agents,
                        "timeout": False,
                        "round": current_round,
                        "agent_error_detected": False
                    }

            except requests.RequestException as e:
                print(f"[Coordinator] Error checking status: {e}")

            time.sleep(poll_interval)

        # Timeout
        print(f"[Coordinator] Timeout waiting for agents after {timeout}s")
        return {
            "all_ready": False,
            "ready_agents": last_status.get("ready_agents", []),
            "timeout": True,
            "round": current_round,
            "agent_error_detected": False
        }

    
    def post(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """Post phase: Update shared state, decide next step"""
        shared["current_status"] = exec_res
        shared["round"] = exec_res["round"]

        # Check for agent errors (Unity window missing, API quota, etc.)
        if exec_res.get("agent_error_detected"):
            print("[Coordinator] Agent error detected, triggering emergency stop!")
            return "emergency_stop"

        if exec_res.get("timeout"):
            consecutive_timeouts = shared.get("consecutive_timeouts", 0) + 1
            shared["consecutive_timeouts"] = consecutive_timeouts

            max_timeouts = prep_res["max_consecutive_timeouts"]
            print(f"[Coordinator] Warning: Timeout occurred ({consecutive_timeouts}/{max_timeouts})")

            if consecutive_timeouts >= max_timeouts:
                print(f"[Coordinator] Too many consecutive timeouts, triggering emergency stop!")
                return "emergency_stop"

            return "timeout"

        # Reset consecutive timeouts on success
        shared["consecutive_timeouts"] = 0

        if not exec_res.get("all_ready"):
            print("[Coordinator] Not all agents ready, waiting...")
            return "timeout"

        return "default"


class EmergencyStopNode(Node):
    """
    Emergency stop node: Broadcast stop signal to all agents when critical errors occur
    """

    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """Prep phase: Get decision and configuration"""
        return {
            "sync_server_url": shared["sync_server_url"],
            "agent_ids": shared["agent_ids"],
            "round": shared.get("round", 0)
        }

    def exec(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """
        Exec phase: Send stop signal to all agents

        Returns:
            {
                "success": bool,
                "message": str,
                "error": str (optional)
            }
        """
        server_url = prep_res["sync_server_url"]

        try:
            print("[Coordinator] Broadcasting emergency stop signal to all agents...")
            resp = requests.post(
                f"{server_url}/sync/trigger_stop",
                timeout=10
            )
            resp.raise_for_status()

            return {
                "success": True,
                "message": "Emergency stop signal broadcasted successfully"
            }

        except requests.RequestException as e:
            print(f"[Coordinator] Error broadcasting stop signal: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def post(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """Post phase: Decide flow direction"""
        if exec_res.get("success"):
            print("[Coordinator] Emergency stop completed, ending coordination")
        else:
            print("[Coordinator] Emergency stop failed, but ending coordination anyway")

        return "end"


class DecisionNode(Node):
    """
    Decision node (core extension point)
    
    Current responsibilities:
    - Decide whether to trigger unified capture commands
    
    Future extensions:
    - Decide what commands to send based on agent states
    - Decide which agents to send specific messages to
    - Adjust exploration strategy
    - Can integrate LLM for complex decisions
    
    Reserved interface:
    - exec() return format supports multiple action types
    - Can implement more complex decision logic by modifying exec()
    """
    
    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """Prep phase: Collect context needed for decision"""
        current_status = shared.get("current_status", {})
        round_num = shared.get("round", 0)
        max_rounds = shared.get("max_rounds", 100)
        
        return {
            "round": round_num,
            "ready_agents": current_status.get("ready_agents", []),
            "max_rounds": max_rounds,
            # === Reserved: Can add more context in future ===
            # "agent_states": current_status.get("agent_states", {}),
            # "message_history": shared.get("coordinator_message_history", []),
        }
    
    def exec(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """
        Exec phase: Generate coordination commands for this round
        
        Current implementation: Simply return capture_all command
        
        Return format (supports future extension):
        {
            "action": str,           # Currently fixed to "capture_all"
            "should_continue": bool, # Whether to continue loop
            "reasoning": str,        # Decision reasoning (optional)
            
            # === Reserved fields: For future extension ===
            # "target_agents": list,  # Target agents (for directed messages)
            # "message": str,         # Message to send
            # "strategy_adjustment": dict,  # Strategy adjustment parameters
        }
        
        TODO: Can integrate LLM for intelligent decisions in the future
        Example:
            from utils import call_llm
            prompt = f"Based on agent states: {prep_res['agent_states']}, decide..."
            response = call_llm(prompt)
            # Parse LLM response and return decision
        """
        round_num = prep_res["round"]
        max_rounds = prep_res["max_rounds"]
        ready_agents = prep_res["ready_agents"]
        
        # === Current simple implementation: Trigger capture every round ===
        should_continue = round_num < max_rounds
        
        decision = {
            "action": "capture_all",
            "should_continue": should_continue,
            "reasoning": f"Round {round_num + 1}: All {len(ready_agents)} agents ready, triggering synchronized capture"
        }
        
        print(f"[Coordinator] Decision: {decision['action']}")
        print(f"[Coordinator] Reasoning: {decision['reasoning']}")
        
        return decision
    
    def post(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """Post phase: Save decision result"""
        shared["current_decision"] = exec_res
        shared["should_continue"] = exec_res["should_continue"]
        
        return "default"


class DispatchNode(Node):
    """
    Command dispatch node
    
    Responsibilities:
    - Send corresponding commands to sync server based on DecisionNode's decision
    - Current implementation: Send unified capture signal
    - After sending signal, sync server will clear ready state for next round
    
    How it works:
    - Call POST /sync/trigger_capture to send capture signal
    - Sync server will:
      1. Notify all waiting agents (via asyncio.Event)
      2. Clear ready_agents set
    - Sub-agents receive signal, capture screenshot, then continue flow
    """
    
    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """Prep phase: Get decision and configuration"""
        return {
            "sync_server_url": shared["sync_server_url"],
            "decision": shared.get("current_decision", {}),
            "round": shared.get("round", 0)
        }
    
    def exec(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """
        Exec phase: Send capture signal
        
        Returns:
            {
                "success": bool,
                "triggered_agents": list,
                "error": str (optional)
            }
        """
        server_url = prep_res["sync_server_url"]
        decision = prep_res["decision"]
        round_num = prep_res["round"]
        
        action = decision.get("action", "capture_all")
        
        if action == "capture_all":
            try:
                # Send unified capture signal
                print(f"[Coordinator] Sending capture signal to all agents...")
                resp = requests.post(
                    f"{server_url}/sync/trigger_capture",
                    timeout=10
                )
                resp.raise_for_status()
                
                data = resp.json()
                triggered_agents = data.get("triggered_agents", [])
                
                print(f"[Coordinator] Capture signal sent! Triggered agents: {triggered_agents}")
                
                return {
                    "success": True,
                    "triggered_agents": triggered_agents,
                    "round": round_num
                }
                
            except requests.RequestException as e:
                print(f"[Coordinator] Error sending capture signal: {e}")
                return {
                    "success": False,
                    "triggered_agents": [],
                    "error": str(e),
                    "round": round_num
                }
        
        # === Reserved: Handle other action types ===
        # elif action == "message":
        #     # Send message to specific agent
        #     pass
        # elif action == "broadcast":
        #     # Broadcast message to all agents
        #     pass
        
        else:
            print(f"[Coordinator] Unknown action type: {action}")
            return {
                "success": False,
                "error": f"Unknown action: {action}",
                "round": round_num
            }
    
    def post(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """
        Post phase: Update state and decide flow direction
        
        Key points:
        - After sending capture signal, sync server has already cleared ready state
        - Sub-agents will naturally enter next PerceptionNode and report ready after capture
        - So here we just update round count, then go back to CollectStatusNode for next round
        """
        shared["dispatch_result"] = exec_res
        
        # Update round count
        shared["round"] = exec_res.get("round", 0) + 1
        
        # Check whether to continue
        if not shared.get("should_continue", True):
            print(f"[Coordinator] Reached max rounds, ending coordination")
            return "end"
        
        if not exec_res.get("success"):
            print(f"[Coordinator] Dispatch failed, but continuing to next round...")
        
        # Continue to next round
        return "continue"


def create_coordinator_flow() -> Flow:
    """
    Create Coordinator Flow

    Flow structure:
    ===============
    CollectStatusNode → DecisionNode → DispatchNode
            ↑                               │
            └───────── "continue" ──────────┘
                       "end" → finish
                       "emergency_stop" → EmergencyStopNode → end

    Branch description:
    - CollectStatusNode:
      - "default" → DecisionNode (all agents ready)
      - "timeout" → CollectStatusNode (retry)
      - "emergency_stop" → EmergencyStopNode (Unity crash or too many timeouts)

    - DecisionNode:
      - "default" → DispatchNode

    - DispatchNode:
      - "continue" → CollectStatusNode (continue to next round)
      - "end" → finish

    - EmergencyStopNode:
      - "end" → finish

    Returns:
        Configured Flow instance
    """
    # Create nodes
    collect = CollectStatusNode()
    decide = DecisionNode()
    dispatch = DispatchNode()
    emergency_stop = EmergencyStopNode()

    # Connect nodes: CollectStatus → Decision → Dispatch
    collect >> decide >> dispatch

    # Branch handling
    collect - "timeout" >> collect  # Timeout retry
    collect - "emergency_stop" >> emergency_stop  # Emergency stop
    dispatch - "continue" >> collect  # Continue to next round
    dispatch - "end"  # End (no subsequent nodes)
    emergency_stop - "end"  # Emergency stop ends

    # Create and return Flow
    return Flow(start=collect)


if __name__ == "__main__":
    # Test Flow creation
    print("Creating Coordinator Flow...")
    flow = create_coordinator_flow()
    print("Flow created successfully!")
    print("\nFlow structure:")
    print("  CollectStatusNode → DecisionNode → DispatchNode")
    print("          ↑                               │")
    print("          └───────── 'continue' ──────────┘")
    print("                     'end' → finish")

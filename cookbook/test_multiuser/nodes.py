"""
Node definitions for Multi-Agent exploration system

Synchronization Mode:
====================
When sync_enabled=True in private_property, PerceptionNode will:
1. Report "ready" to the sync server (Coordinator)
2. Block and wait for capture signal from Coordinator
3. Execute screenshot only after receiving signal
4. This ensures all agents capture screenshots at the same time

To enable sync mode, set in private_property:
    private_property["sync_enabled"] = True
    private_property["sync_server_url"] = "http://localhost:8000"
"""
from pocketflow import Node
from utils import (
    call_llm,
    get_embedding,
)
from utils.vision import summarize_img, compare_img
from utils.clip_features import extract_visual_features
from utils.shared_memory_client import (
    SharedMemoryClient,
    get_shared_memory_client,
    search_and_update_or_add
)
import time
from utils.perception_interface import PerceptionInterface
import yaml
import threading
import os
import re
import glob
from pathlib import Path
import numpy as np
import requests


def find_previous_screenshot(current_screenshot_path: str, agent_id: str) -> str:
    """
    Find the previous screenshot for the given agent based on timestamp.
    
    Args:
        current_screenshot_path: Path to the current screenshot
        agent_id: Agent identifier to filter screenshots
        
    Returns:
        Path to the previous screenshot, or empty string if not found
    """
    if not current_screenshot_path:
        return ""
    
    current_path = Path(current_screenshot_path)
    screenshot_dir = current_path.parent
    
    if not screenshot_dir.exists():
        return ""
    
    # Find all screenshots for this agent in the same directory
    # Pattern: {agent_id}_*.png
    pattern = str(screenshot_dir / f"{agent_id}_*.png")
    all_screenshots = glob.glob(pattern)
    
    if len(all_screenshots) < 2:
        # No previous screenshot available
        return ""
    
    # Sort by modification time (oldest first)
    all_screenshots_sorted = sorted(all_screenshots, key=lambda p: Path(p).stat().st_mtime)
    
    # Find the index of current screenshot
    current_abs = str(current_path.resolve())
    try:
        current_idx = next(
            i for i, p in enumerate(all_screenshots_sorted) 
            if str(Path(p).resolve()) == current_abs
        )
    except StopIteration:
        # Current screenshot not found in list, return the second most recent
        if len(all_screenshots_sorted) >= 2:
            return all_screenshots_sorted[-2]
        return ""
    
    # Return the screenshot before the current one
    if current_idx > 0:
        return all_screenshots_sorted[current_idx - 1]
    
    return ""


class PerceptionNode(Node):
    """
    Perception node: Get current environment state
    
    Uses PerceptionInterface abstraction layer, supports switching between different perception implementations.
    
    Synchronization Mode (sync_enabled=True):
    =========================================
    When enabled, this node coordinates with a central Coordinator to ensure
    all agents capture screenshots at the same time:
    
    1. Report "ready" to sync server → wait for other agents
    2. Block until Coordinator sends capture signal
    3. Execute screenshot
    4. Continue with post-processing
    
    This is useful for multi-agent scenarios where agents run on different
    computers and need to capture synchronized observations.
    
    Configuration (in private_property):
        sync_enabled: bool - Enable/disable sync mode (default: False)
        sync_server_url: str - URL of the sync server (default: http://localhost:8000)
        sync_wait_timeout: float - Max wait time for capture signal in seconds (default: 60)
    """
    
    def prep(self, private_property):
        # Update position counter at the start of iteration (before perception)
        private_property["position"] += 1
        
        # Get perception interface from private_property store
        perception = private_property["perception"]
        agent_id = private_property["agent_id"]
        position = private_property["position"]
        
        # Get sync configuration
        sync_enabled = private_property.get("sync_enabled", False)
        sync_server_url = private_property.get("sync_server_url", "http://localhost:8000")
        sync_wait_timeout = private_property.get("sync_wait_timeout", 60.0)
        
        return {
            "perception": perception,
            "agent_id": agent_id,
            "position": position,
            "sync_enabled": sync_enabled,
            "sync_server_url": sync_server_url,
            "sync_wait_timeout": sync_wait_timeout
        }
    
    def exec(self, prep_res):
        """
        执行阶段：获取环境感知（可能需要同步等待）
        
        Synchronization Flow:
        1. If sync_enabled, report ready to Coordinator
        2. If sync_enabled, block and wait for capture signal
        3. Execute screenshot via perception interface
        """
        perception = prep_res["perception"]
        agent_id = prep_res["agent_id"]
        position = prep_res["position"]
        sync_enabled = prep_res["sync_enabled"]
        sync_server_url = prep_res["sync_server_url"]
        sync_wait_timeout = prep_res["sync_wait_timeout"]
        
        # === 同步模式：等待 Coordinator 的截屏信号 ===
        if sync_enabled:
            # Step 1: 向 Coordinator 报告已到达 PerceptionNode
            self._report_ready(sync_server_url, agent_id)
            
            # Step 2: 阻塞等待 Coordinator 的截屏信号
            capture_ok = self._wait_for_capture_signal(
                sync_server_url, 
                agent_id, 
                sync_wait_timeout
            )
            
            if not capture_ok:
                print(f"[{agent_id}] Warning: Timeout waiting for capture signal, proceeding anyway")
        
        # Step 3: 执行截屏
        # Use perception interface to get visible objects
        # Note: Thread safety is handled by the perception implementation itself
        visible = perception.get_visible_objects(agent_id, position)
        
        return visible
    
    def _report_ready(self, server_url: str, agent_id: str) -> bool:
        """
        向 Coordinator 报告已准备好截屏
        
        调用 POST /sync/ready 告知 Coordinator 本 Agent 已到达 PerceptionNode
        
        Args:
            server_url: 同步服务器地址
            agent_id: Agent 标识符
            
        Returns:
            True if successfully reported, False otherwise
        """
        try:
            resp = requests.post(
                f"{server_url}/sync/ready",
                json={"agent_id": agent_id},
                timeout=10
            )
            resp.raise_for_status()
            
            data = resp.json()
            ready_count = data.get("ready_count", 0)
            expected_count = data.get("expected_count", 0)
            
            print(f"[{agent_id}] Reported ready to Coordinator ({ready_count}/{expected_count} ready)")
            return True
            
        except requests.RequestException as e:
            print(f"[{agent_id}] Error reporting ready to Coordinator: {e}")
            return False
    
    def _wait_for_capture_signal(
        self, 
        server_url: str, 
        agent_id: str, 
        timeout: float
    ) -> bool:
        """
        阻塞等待 Coordinator 的截屏信号
        
        调用 POST /sync/wait_capture 阻塞等待，直到 Coordinator 调用 trigger_capture
        
        Args:
            server_url: 同步服务器地址
            agent_id: Agent 标识符
            timeout: 最大等待时间（秒）
            
        Returns:
            True if capture signal received, False if timeout
        """
        print(f"[{agent_id}] Waiting for synchronized capture signal...")
        
        try:
            resp = requests.post(
                f"{server_url}/sync/wait_capture",
                json={"agent_id": agent_id, "timeout": timeout},
                timeout=timeout + 5  # HTTP timeout slightly longer than wait timeout
            )
            resp.raise_for_status()
            
            data = resp.json()
            should_capture = data.get("should_capture", False)
            
            if should_capture:
                print(f"[{agent_id}] Received capture signal from Coordinator!")
                return True
            else:
                error = data.get("error", "unknown")
                print(f"[{agent_id}] Wait for capture failed: {error}")
                return False
                
        except requests.Timeout:
            print(f"[{agent_id}] HTTP request timeout waiting for capture signal")
            return False
        except requests.RequestException as e:
            print(f"[{agent_id}] Error waiting for capture signal: {e}")
            return False
    
    def post(self, private_property, prep_res, exec_res):
        private_property["visible_objects"] = exec_res
        # If unity screenshot path is present, use summarize_img to get description and objects with positions
        # Example of exec_res: ["screenshot:E:/.../img.png"]
        description = None
        current_image_path = None
        
        if exec_res and isinstance(exec_res[0], str) and exec_res[0].startswith("screenshot:"):
            current_image_path = exec_res[0].split("screenshot:", 1)[1]
            # summarize_img returns {"description": "...", "objects": {"chair": "front-near", ...}}
            summary = summarize_img(current_image_path)
            description = summary.get("description")
            objects_with_positions = summary.get("objects", {})
            # Update visible_objects with object-position dict
            if objects_with_positions:
                private_property["visible_objects"] = objects_with_positions
        
        # Set visible_caption: use description if available, otherwise format visible_objects
        if description:
            private_property["visible_caption"] = description
        elif isinstance(private_property["visible_objects"], dict):
            # Format dict as "object1 (position1), object2 (position2), ..."
            private_property["visible_caption"] = ", ".join(
                f"{obj} ({pos})" for obj, pos in private_property["visible_objects"].items()
            )
        else:
            private_property["visible_caption"] = ", ".join(map(str, private_property["visible_objects"]))
        
        print(f"[{private_property['agent_id']}] Position {private_property['position']}: sees {private_property['visible_objects']}")
        if description:
            print(f"[{private_property['agent_id']}] Description: {description}")
        
        # Compare with previous screenshot if available
        if current_image_path:
            agent_id = private_property["agent_id"]
            prev_image_path = find_previous_screenshot(current_image_path, agent_id)
            
            if prev_image_path:
                print(f"[{agent_id}] Comparing with previous screenshot: {prev_image_path}")
                env_change_text = compare_img(prev_image_path, current_image_path)
                
                # Store env change in private_property
                if "env_change" not in private_property:
                    private_property["env_change"] = []
                private_property["env_change"].append({
                    "step": private_property["position"],
                    "change": env_change_text,
                    "prev_image": prev_image_path,
                    "curr_image": current_image_path
                })
                
                print(f"[{agent_id}] Environment change: {env_change_text}")
            else:
                print(f"[{agent_id}] No previous screenshot found (first observation)")
        
        return "default"


class CommunicationNode(Node):
    """Communication node: Read messages from other agents"""
    
    def prep(self, private_property):
        return private_property["agent_id"], private_property["perception"]
    
    def exec(self, prep_res):
        agent_id, perception = prep_res
        try:
            messages = perception.poll_messages(agent_id)
        except Exception as e:
            print(f"[CommunicationNode] Error polling messages: {e}")
            messages = []
        return messages
    
    def post(self, private_property, prep_res, exec_res):
        private_property["other_agent_messages"] = exec_res
        
        if exec_res:
            print(f"[{private_property['agent_id']}] Received {len(exec_res)} messages:")
            for msg in exec_res:
                print(f"  From {msg['sender']}: {msg['message']}")
        
        return "default"


class SharedMemoryRetrieveNode(Node):
    """
    Shared Memory Retrieve Node: Search the distributed shared memory for matching entities.
    
    This node:
    1. Extracts CLIP visual features from current screenshot (if available)
    2. Gets description embedding from visible_caption
    3. Searches the shared memory server for matching entities
    4. Stores retrieval results for subsequent processing
    
    Flow according to diagram:
    - retrieve mem → found entry (same obj) → update entry
    - retrieve mem → found entry (diff obj) → save new entry
    - retrieve mem → not found → save new entry
    """
    
    def prep(self, private_property):
        agent_id = private_property["agent_id"]
        position = private_property["position"]
        visible_objects = private_property.get("visible_objects", {})
        visible_caption = private_property.get("visible_caption", "")
        
        # Get screenshot path if available
        screenshot_path = None
        if isinstance(visible_objects, dict):
            # Check if there's a screenshot path in visible_objects
            for key in visible_objects:
                if isinstance(key, str) and key.startswith("screenshot:"):
                    screenshot_path = key.split("screenshot:", 1)[1]
                    break
        elif isinstance(visible_objects, list):
            for item in visible_objects:
                if isinstance(item, str) and item.startswith("screenshot:"):
                    screenshot_path = item.split("screenshot:", 1)[1]
                    break
        
        # Also check if screenshot path was stored directly
        if not screenshot_path:
            # Try to find from current observation
            raw_visible = private_property.get("visible_objects", [])
            if isinstance(raw_visible, list) and raw_visible:
                first_item = raw_visible[0]
                if isinstance(first_item, str) and first_item.startswith("screenshot:"):
                    screenshot_path = first_item.split("screenshot:", 1)[1]
        
        # Store screenshot path for later use
        if screenshot_path:
            private_property["_current_screenshot_path"] = screenshot_path
        
        # Get shared memory client from private_property store (or create new one)
        shared_memory_client = private_property.get("shared_memory_client")
        if shared_memory_client is None:
            shared_memory_client = get_shared_memory_client()
            private_property["shared_memory_client"] = shared_memory_client
        
        return {
            "agent_id": agent_id,
            "position": position,
            "visible_caption": visible_caption,
            "visible_objects": visible_objects,
            "screenshot_path": screenshot_path,
            "shared_memory_client": shared_memory_client
        }
    
    def exec(self, prep_res):
        agent_id = prep_res["agent_id"]
        visible_caption = prep_res["visible_caption"]
        visible_objects = prep_res["visible_objects"]
        screenshot_path = prep_res["screenshot_path"]
        client = prep_res["shared_memory_client"]
        
        # Check if shared memory server is available
        if not client.is_available():
            print(f"[{agent_id}] SharedMemory server not available, skipping shared memory retrieval")
            return {
                "server_available": False,
                "visual_features": None,
                "description_embedding": None,
                "search_result": None,
                "objects_to_process": []
            }
        
        # Extract CLIP visual features from screenshot
        visual_features = None
        if screenshot_path and os.path.exists(screenshot_path):
            print(f"[{agent_id}] Extracting CLIP features from: {screenshot_path}")
            visual_features = extract_visual_features(screenshot_path)
            if visual_features is not None:
                print(f"[{agent_id}] CLIP features extracted: shape={visual_features.shape}")
        
        # Get description embedding
        description_embedding = None
        if visible_caption:
            description_embedding = get_embedding(visible_caption)
            if description_embedding is not None:
                print(f"[{agent_id}] Description embedding: shape={description_embedding.shape}")
        
        # Search shared memory
        search_result = None
        if visual_features is not None or description_embedding is not None:
            search_result = client.search(
                visual_features=visual_features,
                description_embedding=description_embedding,
                agent_id=agent_id
            )
            
            if search_result.match_found:
                print(f"[{agent_id}] SharedMemory search: found {len(search_result.matches)} matches")
                if search_result.is_same_object:
                    print(f"[{agent_id}]   → Same object detected (entity_id: {search_result.top_entity_id})")
                else:
                    print(f"[{agent_id}]   → Similar but different object")
            else:
                print(f"[{agent_id}] SharedMemory search: no matches found")
        
        # Prepare list of objects to process (for adding to shared memory)
        objects_to_process = []
        if isinstance(visible_objects, dict):
            for obj_name, position in visible_objects.items():
                if isinstance(obj_name, str):
                    objects_to_process.append({
                        "name": obj_name,
                        "position": position
                    })
        elif isinstance(visible_objects, (list, set)):
            for obj in visible_objects:
                if isinstance(obj, str):
                    objects_to_process.append({
                        "name": obj,
                        "position": ""
                    })
        
        return {
            "server_available": True,
            "visual_features": visual_features,
            "description_embedding": description_embedding,
            "search_result": search_result,
            "objects_to_process": objects_to_process
        }
    
    def post(self, private_property, prep_res, exec_res):
        # Store results in private_property for later use by SharedMemoryUpdateNode
        private_property["_shared_memory_retrieval"] = {
            "server_available": exec_res["server_available"],
            "visual_features": exec_res["visual_features"],
            "description_embedding": exec_res["description_embedding"],
            "search_result": exec_res["search_result"],
            "objects_to_process": exec_res["objects_to_process"]
        }
        
        # Store retrieved shared memory info for DecisionNode context
        if exec_res["search_result"] and exec_res["search_result"].matches:
            private_property["shared_memory_matches"] = [
                {
                    "entity_id": m.entity_id,
                    "entity_type": m.entity_type,
                    "description": m.description_text,
                    "similarity": m.combined_score,
                    "visit_count": m.meta_info.get("visit_count", 0),
                    "discovered_by": m.inferred_properties.get("discovered_by_agents", [])
                }
                for m in exec_res["search_result"].matches[:5]  # Top 5
            ]
        else:
            private_property["shared_memory_matches"] = []
        
        return "default"


class SharedMemoryUpdateNode(Node):
    """
    Shared Memory Update Node: Update or add entities to shared memory based on retrieval results.
    
    This node implements the flow:
    - If same object found → Update entry (last_updated, discovered_by_agents, exploration_priority, visit_count)
    - If different object found OR not found → Save new entry into shared memory
    """
    
    def prep(self, private_property):
        agent_id = private_property["agent_id"]
        position = private_property["position"]
        step_count = private_property["step_count"]
        visible_caption = private_property.get("visible_caption", "")
        
        # Get retrieval results from SharedMemoryRetrieveNode
        retrieval = private_property.get("_shared_memory_retrieval", {})
        
        # Get shared memory client
        shared_memory_client = private_property.get("shared_memory_client")
        
        return {
            "agent_id": agent_id,
            "position": position,
            "step_count": step_count,
            "visible_caption": visible_caption,
            "retrieval": retrieval,
            "shared_memory_client": shared_memory_client
        }
    
    def exec(self, prep_res):
        agent_id = prep_res["agent_id"]
        step_count = prep_res["step_count"]
        visible_caption = prep_res["visible_caption"]
        retrieval = prep_res["retrieval"]
        client = prep_res["shared_memory_client"]
        
        if not retrieval.get("server_available") or client is None:
            return {
                "action": "skipped",
                "reason": "Server not available",
                "entities_updated": [],
                "entities_added": []
            }
        
        search_result = retrieval.get("search_result")
        visual_features = retrieval.get("visual_features")
        description_embedding = retrieval.get("description_embedding")
        objects_to_process = retrieval.get("objects_to_process", [])
        
        entities_updated = []
        entities_added = []
        
        if search_result and search_result.is_same_object and search_result.top_entity_id:
            # === Same object found → Update entry ===
            entity_id = search_result.top_entity_id
            
            success = client.update_entity(
                entity_id=entity_id,
                agent_id=agent_id,
                current_step=step_count,
                new_visual_features=visual_features,
                new_description_embedding=description_embedding
            )
            
            if success:
                print(f"[{agent_id}] SharedMemory: Updated existing entity {entity_id}")
                entities_updated.append(entity_id)
            else:
                print(f"[{agent_id}] SharedMemory: Failed to update entity {entity_id}")
            
            return {
                "action": "updated",
                "reason": "Same object found",
                "entities_updated": entities_updated,
                "entities_added": entities_added
            }
        
        else:
            # === Not found OR different object → Save new entry ===
            # Add each observed object as a new entity
            for obj in objects_to_process:
                obj_name = obj["name"]
                obj_position = obj.get("position", "")
                
                # Determine entity type from object name
                entity_type = obj_name.lower().strip()
                
                entity_id = client.add_entity(
                    entity_type=entity_type,
                    visual_features=visual_features,  # Shared visual features for now
                    description_embedding=description_embedding,  # Shared description for now
                    description_text=f"{obj_name} - {visible_caption}",
                    discovered_by_agent=agent_id,
                    current_step=step_count,
                    relative_position=obj_position,
                    region=""  # Could be inferred from position or environment
                )
                
                if entity_id:
                    print(f"[{agent_id}] SharedMemory: Added new entity {entity_id} ({entity_type})")
                    entities_added.append(entity_id)
                else:
                    print(f"[{agent_id}] SharedMemory: Failed to add entity for {obj_name}")
            
            return {
                "action": "added",
                "reason": "New objects found" if not search_result or not search_result.match_found else "Different objects",
                "entities_updated": entities_updated,
                "entities_added": entities_added
            }
    
    def post(self, private_property, prep_res, exec_res):
        # Store update results in private_property
        private_property["_shared_memory_update_result"] = exec_res
        
        # Log summary
        agent_id = private_property["agent_id"]
        if exec_res["entities_updated"]:
            print(f"[{agent_id}] SharedMemory update summary: {len(exec_res['entities_updated'])} entities updated")
        if exec_res["entities_added"]:
            print(f"[{agent_id}] SharedMemory update summary: {len(exec_res['entities_added'])} entities added")
        
        # Clean up temporary retrieval data
        if "_shared_memory_retrieval" in private_property:
            del private_property["_shared_memory_retrieval"]
        
        # Read the flow control action from UpdateMemoryNode (stored in private_property)
        # UpdateMemoryNode sets this before returning
        flow_action = private_property.get("_flow_control_action", "continue")
        
        return flow_action


class DecisionNode(Node):
    """Decision node: Decide next action based on context"""
    
    def prep(self, private_property):
        # Collect all context needed for decision making
        context = {
            "agent_id": private_property["agent_id"],
            "position": private_property["position"],
            "visible_objects": private_property["visible_objects"],
            "retrieved_memories": private_property["retrieved_memories"],
            "other_agent_messages": private_property["other_agent_messages"],
            "explored_objects": list(private_property["explored_objects"]),
            "step_count": private_property["step_count"],
            "perception_type": private_property.get("perception", {}).get_environment_info().get("type", "unknown"),
            "action_history": private_property.get("action_history", []),  # Add action history to context
            "env_change": private_property.get("env_change", [])  # Add environment change history
        }
        return context
    
    def exec(self, context):
        # Optional offline mode: skip LLM when DISABLE_LLM is set
        if os.getenv("DISABLE_LLM"):
            action = "forward" if (context.get("step_count", 0) % 2 == 0) else "backward"
            return {
                "thinking": "LLM disabled for local validation.",
                "action": action,
                "reason": "Deterministic fallback decision without LLM.",
                "message_to_others": "Testing without LLM"
            }

        # Construct decision prompt
        memories_text = "\n".join([
            f"- {text[:100]}" 
            for text, _ in context["retrieved_memories"][:3]
        ]) if context["retrieved_memories"] else "No historical memories"
        
        messages_text = "\n".join([
            f"- {msg['sender']}: {msg['message']}"
            for msg in context["other_agent_messages"]
        ]) if context["other_agent_messages"] else "No messages from other agents"
        
        # Get latest 5 action history records (or all if less than 5)
        action_history = context.get("action_history", [])
        latest_history = action_history[-5:] if len(action_history) > 5 else action_history
        
        # Format action history for prompt
        if latest_history:
            history_text = "\n".join([
                f"  Step {record['step']}: At position {record['position']}, action '{record['action']}', "
                f"visible: {record.get('visible', [])}, "
                f"new objects: {record.get('new_objects', [])}"
                for record in latest_history
            ])
            history_section = f"Recent action history (last {len(latest_history)} steps):\n{history_text}"
        else:
            history_section = "No previous action history (this is the first step)"
        
        # Format environment change history (last 1 entry only)
        env_change_history = context.get("env_change", [])
        latest_env_change = env_change_history[-1] if env_change_history else None
        
        if latest_env_change:
            env_change_section = f"Latest environment change (comparing consecutive screenshots):\n  Step {latest_env_change['step']}: {latest_env_change['change']}"
        else:
            env_change_section = "No environment change history yet (first observation or screenshots not available)"
        
        # Determine available actions based on perception type
        perception_type = context.get("perception_type", "unknown")
        if perception_type == "unity3d":
            # Simplified action space for unity3d mode (WSAD + Space)
            available_actions = [
                "- forward: Move forward (key 'w')",
                "- backward: Move backward (key 's')",
                "- move_left: Strafe left (key 'a')",
                "- move_right: Strafe right (key 'd')",
            ]
            action_list = "forward, backward, move_left, move_right"
            valid_actions = ["forward", "backward", "move_left", "move_right",]
        else:
            # Full action space for other modes
            available_actions = [
                "- forward: Move to next position",
                "- backward: Move to previous position",
                "- move_left: Strafe left (key 'a')",
                "- move_right: Strafe right (key 'd')",
                "- move_up: Move up (key 'r')",
                "- move_down: Move down (key 'f')",
                "- look_left: Turn head left (left arrow)",
                "- look_right: Turn head right (right arrow)",
                "- look_up: Look up (up arrow)",
                "- look_down: Look down (down arrow)",
                "- tilt_left: Roll head left (key 'q')",
                "- tilt_right: Roll head right (key 'e')",
            ]
            action_list = "forward, backward, move_left, move_right, move_up, move_down, look_left, look_right, look_up, look_down, tilt_left, tilt_right"
            valid_actions = [
                "forward", "backward",
                "move_left", "move_right", "move_up", "move_down",
                "look_left", "look_right", "look_up", "look_down",
                "tilt_left", "tilt_right",
            ]
        
        actions_text = "\n".join(available_actions)
        
        prompt = f"""You are {context['agent_id']}, an autonomous exploration agent exploring within a 3D environment as part of a multi-agent team.
                    Your mission is to maximize the discovery of new objects and unexplored areas while cooperating efficiently with other agents. Avoid redundant exploration, communicate findings clearly, and make strategic movement decisions.
Current state:
- Position: {context['position']}
- Visible objects: {context['visible_objects']}
- Already explored objects: {context['explored_objects']}
- Steps taken: {context['step_count']}

{history_section}

{env_change_section}

Relevant historical memories:
{memories_text}

**Messages from other agents (IMPORTANT - analyze and consider these before deciding):**
{messages_text}
When other agents have reported discoveries or explored certain regions, use this information to **reduce overlap** and **improve overall coverage**.

Task goal: Explore as many new objects as possible, avoid revisiting already explored areas. Analize the screen shot and decide the next action.

Decision strategy:
- Cross-reference other agents' messages with your local observation.
- If another agent found new objects nearby, consider moving closer to assist or expand coverage.
- Important: If you enter an area that is not meant to be explored or meaningless(for example, the sky or any place outside the interactive scene),  please find a way to leave that area.
- Important: Based on the environment change and action history, analyze if you get stuck somewhere. If so, please find a way to leave that area.
- If an area is already reported explored or low in novelty, avoid it. Maintain spatial diversity to maximize total system exploration.
- Communicate back only useful information. 

Available actions:
{actions_text}

Please decide the next action based on the above information, output in YAML format:

```yaml
thinking: Your thought process (MUST consider messages from other agents if any, and whether to explore new areas)
action: one of [{action_list}]
reason: Reason for choosing this action (mention other agents' messages if they influenced your decision)
message_to_others: Information to share with other agents (optional)
```
"""
        
        response = call_llm(prompt)
        
        # Parse YAML with improved error handling
        try:
            result = parse_yaml_from_llm_response(response)
            
            # Validate required fields
            if not isinstance(result, dict):
                raise ValueError("LLM response is not a dictionary")
            if "action" not in result:
                raise ValueError("Missing 'action' field in LLM response")
            if result["action"] not in valid_actions:
                raise ValueError(f"Invalid action: {result['action']}")
            if "reason" not in result:
                result["reason"] = "No reason provided"
            
        except (IndexError, ValueError, yaml.YAMLError) as e:
            # Fallback: try to extract action from response text
            print(f"[DecisionNode] YAML parsing failed: {e}")
            print(f"[DecisionNode] LLM response was: {response[:500]}...")
            
            # Try regex extraction as fallback
            action_match = re.search(r'action:\s*(\w+)', response, re.IGNORECASE)
            if action_match:
                action = action_match.group(1).lower()
                if action in valid_actions:
                    result = {
                        "thinking": "YAML parsing failed, extracted action from text",
                        "action": action,
                        "reason": "Fallback decision due to YAML parsing error",
                        "message_to_others": ""
                    }
                else:
                    # Final fallback: use deterministic action
                    result = {
                        "thinking": "YAML parsing failed and could not extract valid action",
                        "action": "forward" if context.get("step_count", 0) % 2 == 0 else "backward",
                        "reason": "Fallback to deterministic action due to parsing error",
                        "message_to_others": ""
                    }
            else:
                # Final fallback: use deterministic action
                result = {
                    "thinking": "YAML parsing failed and could not extract action from response",
                    "action": "forward" if context.get("step_count", 0) % 2 == 0 else "backward",
                    "reason": "Fallback to deterministic action due to parsing error",
                    "message_to_others": ""
                }
        
        return result
    
    def post(self, private_property, prep_res, exec_res):
        private_property["action"] = exec_res["action"]
        private_property["action_reason"] = exec_res.get("reason", "")
        private_property["message_to_others"] = exec_res.get("message_to_others", "")
        
        print(f"[{private_property['agent_id']}] Decision: {exec_res['action']}")
        print(f"  Reason: {exec_res['reason']}")
        
        return "default"


class ExecutionNode(Node):
    """
    Execution node: Execute action and update environment
    
    Uses PerceptionInterface to execute actions, supports different environment implementations
    """
    
    def prep(self, private_property):
        perception = private_property["perception"]
        agent_id = private_property["agent_id"]
        action = private_property["action"]
        
        return perception, agent_id, action
    
    def exec(self, prep_res):
        perception, agent_id, action = prep_res

        # Log action execution for debugging (visible in Python console)
        print(f"[ExecutionNode] Agent '{agent_id}' executing action: {action}")

        # Use perception interface to execute action
        # Returns new state (including position, visible objects, etc.)
        new_state = perception.execute_action(agent_id, action)

        print(f"[ExecutionNode] Agent '{agent_id}' new state after action '{action}': position={new_state.get('position')}")

        return new_state
    
    def post(self, private_property, prep_res, exec_res):
        # Update step count
        private_property["step_count"] += 1
        
        # Note: visible_objects will be updated in the next PerceptionNode
        # ExecutionNode only updates position, not perception
        
        # Send message to other agents
        if private_property.get("message_to_others"):
            agent_id = private_property["agent_id"]
            message = private_property["message_to_others"]
            perception = private_property["perception"]
            try:
                perception.send_message(agent_id, "all", message)
                print(f"[{agent_id}] Sent message: {message}")
            except Exception as e:
                print(f"[{agent_id}] Failed to send message: {e}")
        
        # Note: explored_objects will be updated in UpdateMemoryNode based on visible_objects
        # from PerceptionNode, not from visible_objects here
        
        return "default"


class UpdateMemoryNode(Node):
    """Memory update node: Update exploration history and discovered objects"""
    
    def prep(self, private_property):
        agent_id = private_property["agent_id"]
        position = private_property["position"]
        step_count = private_property["step_count"]
        action = private_property["action"]
        action_reason = private_property["action_reason"]
        visible_objects = private_property.get("visible_objects", {})
        
        # Prepare data for update - extract objects list
        # Handle both dict format (from summarize_img) and list format (fallback)
        if isinstance(visible_objects, dict):
            # Extract object names from dict keys
            objects_list = [
                obj for obj in visible_objects.keys()
                if isinstance(obj, str) and not obj.startswith("screenshot:")
            ]
        elif isinstance(visible_objects, (list, set)):
            # Filter out screenshot paths (in case extraction failed)
            objects_list = [
                obj for obj in visible_objects 
                if isinstance(obj, str) and not obj.startswith("screenshot:")
            ]
        else:
            objects_list = []
        
        return {
            "agent_id": agent_id,
            "position": position,
            "step_count": step_count,
            "action": action,
            "action_reason": action_reason,
            "visible_objects": visible_objects,
            "objects_list": objects_list
        }
    
    def exec(self, prep_res):
        # No local memory operations needed - shared memory handles storage
        return prep_res
    
    def post(self, private_property, prep_res, exec_res):
        agent_id = exec_res["agent_id"]
        objects_list = exec_res["objects_list"]
        visible_objects = exec_res["visible_objects"]
        
        # Calculate new objects (before updating explored_objects)
        # Filter out screenshot paths and normalize objects
        visible_objects_normalized = []
        if visible_objects:
            # Handle both dict format (from summarize_img) and list format (fallback)
            if isinstance(visible_objects, dict):
                visible_objects_normalized = [
                    obj.lower().strip() 
                    for obj in visible_objects.keys()
                    if isinstance(obj, str) and not obj.startswith("screenshot:")
                ]
            else:
                visible_objects_normalized = [
                    obj.lower().strip() 
                    for obj in visible_objects
                    if isinstance(obj, str) and not obj.startswith("screenshot:")
                ]
        
        # Find new objects that are not in explored_objects yet
        explored_set = private_property.get("explored_objects", set())
        new_objects = [
            obj for obj in visible_objects_normalized 
            if obj and obj not in explored_set
        ]
        
        # Record action history with new objects
        private_property["action_history"].append({
            "step": private_property["step_count"],
            "position": private_property["position"],
            "action": private_property["action"],
            "visible": private_property["visible_objects"],
            "new_objects": new_objects  # Only newly discovered objects
        })
        
        # Update explored_objects with discovered objects
        if objects_list:
            objects_set = set(obj.lower().strip() for obj in objects_list if obj)
            private_property["explored_objects"].update(objects_set)
        
        print(f"[{agent_id}] Updated exploration history")
        if objects_list:
            print(f"[{agent_id}] Discovered objects: {objects_list}")
            print(f"[{agent_id}] Total unique objects explored: {len(private_property['explored_objects'])}")
        
        # Decide whether to continue exploration
        max_steps = private_property.get("max_steps", 20)
        
        if private_property["step_count"] >= max_steps:
            print(f"[{agent_id}] Reached max steps ({max_steps}), ending exploration")
            # Store flow control action for SharedMemoryUpdateNode
            private_property["_flow_control_action"] = "end"
            return "end"
        
        # Store flow control action for SharedMemoryUpdateNode
        private_property["_flow_control_action"] = "continue"
        return "continue"




def parse_yaml_from_llm_response(response: str) -> dict:
    """
    Parse YAML from LLM response with improved error handling.
    
    Extracts YAML from code blocks, cleans up common formatting issues,
    and returns a parsed dictionary.
    
    Args:
        response: Raw LLM response string that may contain YAML in code blocks
        
    Returns:
        Parsed YAML as a dictionary
        
    Raises:
        ValueError: If YAML cannot be parsed or is invalid
        yaml.YAMLError: If YAML parsing fails
    """
    # Try to extract YAML from code block
    if "```yaml" in response:
        yaml_str = response.split("```yaml")[1].split("```")[0].strip()
    elif "```" in response:
        # Fallback: try to extract from any code block
        parts = response.split("```")
        if len(parts) >= 2:
            yaml_str = parts[1].strip()
            if yaml_str.startswith("yaml"):
                yaml_str = yaml_str[4:].strip()
        else:
            yaml_str = response.strip()
    else:
        # No code block, assume entire response is YAML
        yaml_str = response.strip()
    
    # Clean up common YAML issues:
    # Fix problematic single quotes in values (like 'screen', 'cursor' in reason field)
    lines = yaml_str.split('\n')
    cleaned_lines = []
    for line in lines:
        # If line contains a colon (key-value pair)
        if ':' in line and not line.strip().startswith('#'):
            parts = line.split(':', 1)
            if len(parts) == 2:
                key, value = parts
                value = value.strip()
                
                # If value is already properly quoted, leave it alone
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'") and value.count("'") == 2):
                    cleaned_lines.append(line)
                    continue
                
                # If value contains problematic patterns (like 'word1', 'word2')
                # wrap entire value in double quotes and escape internal quotes
                if "'" in value:
                    # Escape any existing double quotes
                    value = value.replace('"', '\\"')
                    # Remove or escape single quotes (YAML prefers double quotes for strings with special chars)
                    value = value.replace("'", "")
                    # Wrap in double quotes
                    value = '"' + value + '"'
                elif ':' in value or (',' in value and not value.startswith('[')):
                    # Values with colons or commas should be quoted
                    value = '"' + value.replace('"', '\\"') + '"'
                
                cleaned_lines.append(key.strip() + ': ' + value)
            else:
                cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)
    yaml_str = '\n'.join(cleaned_lines)
    
    result = yaml.safe_load(yaml_str)
    return result

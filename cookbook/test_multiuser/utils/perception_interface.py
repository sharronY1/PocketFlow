"""
Perception Interface Abstraction Layer

This module defines abstract interfaces for environment perception, enabling easy switching 
between different perception implementations:
- MockPerception: Simulated environment (for development and testing)
- XRPerception: Real XR application interface (to be integrated with actual XR software)
- UnityCameraPerception: Unity camera extraction package integration (Agent-controlled screenshots)
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import requests
import os
import time
import json
from pathlib import Path
import glob
import platform
import math

IS_WINDOWS = platform.system() == "Windows"

try:
    import pyautogui  # type: ignore
except Exception:
    pyautogui = None

try:
    import pydirectinput  # type: ignore
except Exception:
    pydirectinput = None

try:
    from .config_loader import get_config_value
except ImportError:
    # Fallback if import fails
    def get_config_value(key: str, default: Any = None) -> Any:
        return default


def _normalize_vector(vec: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """Normalize a 3D vector; return the original if magnitude is near zero."""
    mag = math.sqrt(vec[0] * vec[0] + vec[1] * vec[1] + vec[2] * vec[2])
    if mag < 1e-8:
        return vec
    return (vec[0] / mag, vec[1] / mag, vec[2] / mag)


def quaternion_to_directions(qx: float, qy: float, qz: float, qw: float) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]:
    """
    Convert quaternion (Unity left-handed: x→right, y→up, z→forward) to forward/right/up unit vectors.
    Formulas based on Unity convention:
        forward = (2(xz + wy), 2(yz - wx), 1 - 2(xx + yy))
        right   = (1 - 2(yy + zz), 2(xy + wz), 2(xz - wy))
        up      = (2(xy - wz), 1 - 2(xx + zz), 2(yz + wx))
    """
    forward = (
        2 * (qx * qz + qw * qy),
        2 * (qy * qz - qw * qx),
        1 - 2 * (qx * qx + qy * qy),
    )
    right = (
        1 - 2 * (qy * qy + qz * qz),
        2 * (qx * qy + qw * qz),
        2 * (qx * qz - qw * qy),
    )
    up = (
        2 * (qx * qy - qw * qz),
        1 - 2 * (qx * qx + qz * qz),
        2 * (qy * qz + qw * qx),
    )
    return _normalize_vector(forward), _normalize_vector(right), _normalize_vector(up)


def read_camera_position_from_poses(
    screenshot_path: str,
    unity_output_base_path: Optional[str] = None
) -> Optional[Dict[str, Tuple[float, ...]]]:
    """
    Read pose file and return current position/rotation and initial position/rotation.

    CSV format: frameCount,timeUtc,x,y,z,qx,qy,qz,qw,screenshotName

    Returns:
        {
            "position": (x, y, z),             # Row matching screenshotName, or last row if not found
            "rotation": (qx, qy, qz, qw),
            "initial_position": (ix, iy, iz),  # First data row
            "initial_rotation": (iqx, iqy, iqz, iqw)
        }
    """
    if not screenshot_path:
        return None

    screenshot_name = Path(screenshot_path).name

    # Determine unity_output_base_path
    if unity_output_base_path is None:
        unity_output_base_path = get_config_value("unity_output_base_path") or os.getenv("UNITY_OUTPUT_BASE_PATH")

    if not unity_output_base_path:
        try:
            screenshot_parts = Path(screenshot_path).parts
            if "screenshots" in screenshot_parts:
                screenshots_idx = screenshot_parts.index("screenshots")
                unity_output_base_path = str(Path(*screenshot_parts[:screenshots_idx]))
        except Exception:
            pass

    if not unity_output_base_path:
        return None

    poses_dir = Path(unity_output_base_path) / "poses"
    if not poses_dir.exists():
        return None

    csv_files = list(poses_dir.glob("**/*.csv"))

    def parse_line(line: str) -> Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float, float], str]]:
        parts = line.strip().split(",")
        if len(parts) < 9:
            return None
        try:
            pos = (float(parts[2]), float(parts[3]), float(parts[4]))
            rot = (float(parts[5]), float(parts[6]), float(parts[7]), float(parts[8]))
            name = parts[9] if len(parts) > 9 else ""
            return pos, rot, name
        except Exception:
            return None

    for csv_file in csv_files:
        try:
            with open(csv_file, "r", encoding="utf-8") as f:
                lines = [ln.strip() for ln in f if ln.strip()]
        except Exception:
            continue

        if len(lines) <= 1:
            continue

        first_data = None
        matched_pose = None
        last_data = None

        for line in lines[1:]:
            parsed = parse_line(line)
            if not parsed:
                continue
            pos, rot, name = parsed
            if first_data is None:
                first_data = (pos, rot)
            last_data = (pos, rot)
            if name and screenshot_name in name:
                matched_pose = (pos, rot)

        if first_data is None:
            continue

        use_pose = matched_pose or last_data
        if use_pose is None:
            continue

        return {
            "position": use_pose[0],
            "rotation": use_pose[1],
            "initial_position": first_data[0],
            "initial_rotation": first_data[1],
        }

    return None


class PerceptionInterface(ABC):
    """
    Abstract perception interface
    
    All perception implementations must inherit from this class and implement its methods
    """
    
    @abstractmethod
    def get_visible_objects(self, agent_id: str, position: Any) -> List[str]:
        """
        Get visible objects at agent's current position
        
        Args:
            agent_id: Agent identifier
            position: Agent's current position (can be int/coordinates/transform, etc.)
        
        Returns:
            List of visible objects
        """
        pass
    
    @abstractmethod
    def get_agent_state(self, agent_id: str) -> Dict[str, Any]:
        """
        Get agent's current state
        
        Args:
            agent_id: Agent identifier
        
        Returns:
            Dictionary containing position, rotation, etc.
            Example: {"position": 1, "rotation": 0, "velocity": 0}
        """
        pass
    
    @abstractmethod
    def execute_action(self, agent_id: str, action: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Execute agent action and return new state
        
        Args:
            agent_id: Agent identifier
            action: Action name (e.g., "forward", "backward", "turn_left", etc.)
            params: Optional action parameters
        
        Returns:
            New state after execution
        """
        pass
    
    @abstractmethod
    def get_environment_info(self) -> Dict[str, Any]:
        """
        Get global environment information
        
        Returns:
            Environment metadata (size, boundaries, total objects, etc.)
        """
        pass

    # Optional messaging hooks for shared environments
    def send_message(self, sender: str, recipient: str, message: str) -> None:
        raise NotImplementedError

    def poll_messages(self, agent_id: str) -> List[Dict[str, Any]]:
        raise NotImplementedError


class MockPerception(PerceptionInterface):
    """
    Mock perception implementation
    
    Uses simple dictionary data structures to simulate XR environment, for development and testing
    """
    
    def __init__(self, env: Dict[str, Any]):
        """
        Args:
            env: Environment dictionary containing objects, agent_positions, etc.
        """
        self.env = env
    
    def get_visible_objects(self, agent_id: str, position: Any) -> List[str]:
        """Get visible objects from simulated environment"""
        return self.env["objects"].get(position, [])
    
    def get_agent_state(self, agent_id: str) -> Dict[str, Any]:
        """Get agent state"""
        position = self.env["agent_positions"].get(agent_id, 0)
        return {
            "position": position,
            "rotation": 0,  # Mock environment doesn't support rotation yet
            "velocity": 0
        }
    
    def execute_action(self, agent_id: str, action: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Execute action and update simulated environment
        
        Supported actions:
        - "forward": Move forward
        - "backward": Move backward
        """
        current_pos = self.env["agent_positions"].get(agent_id, 0)
        
        if action == "forward":
            new_pos = min(current_pos + 1, self.env["num_positions"] - 1)
        elif action == "backward":
            new_pos = max(current_pos - 1, 0)
        else:
            new_pos = current_pos  # Unknown action, stay in place
        
        # Update position
        self.env["agent_positions"][agent_id] = new_pos
        
        # Update global exploration record
        visible = self.get_visible_objects(agent_id, new_pos)
        self.env["explored_by_all"].update(visible)
        
        return {
            "position": new_pos,
            "rotation": 0,
            "velocity": 0,
            "visible_objects": visible
        }
    
    def get_environment_info(self) -> Dict[str, Any]:
        """Get environment information"""
        return {
            "type": "mock",
            "num_positions": self.env["num_positions"],
            "total_objects": sum(len(objs) for objs in self.env["objects"].values()),
            "boundaries": {"min": 0, "max": self.env["num_positions"] - 1}
        }


class XRPerception(PerceptionInterface):
    """
    XR application perception implementation (template)
    
    This is a template class that needs to be filled based on actual XR platform
    """
    
    def __init__(self, xr_client=None, config: Optional[Dict] = None):
        """
        Args:
            xr_client: XR application client connection (SDK, API client, etc.)
            config: Configuration parameters (API address, authentication, etc.)
        """
        self.xr_client = xr_client
        self.config = config or {}
        
        # TODO: Initialize connection to XR application
        # Example:
        # self.xr_client = UnityClient(host=config.get("host"), port=config.get("port"))
        # self.xr_client.connect()
    
    def get_visible_objects(self, agent_id: str, position: Any) -> List[str]:
        """
        Get visible objects from real XR application
        
        TODO: Implement real XR perception logic
        """
        # Example implementation (needs modification based on actual XR API):
        # try:
        #     scene_data = self.xr_client.get_scene(agent_id)
        #     return scene_data.visible_objects
        # except Exception as e:
        #     print(f"[XRPerception] Error getting visible objects: {e}")
        #     return []
        
        raise NotImplementedError(
            "XRPerception.get_visible_objects() needs to be implemented based on actual XR application API"
        )
    
    def get_agent_state(self, agent_id: str) -> Dict[str, Any]:
        """
        Get agent state from real XR application
        
        TODO: Implement real state retrieval logic
        """
        # Example implementation:
        # try:
        #     transform = self.xr_client.get_agent_transform(agent_id)
        #     return {
        #         "position": transform.position,
        #         "rotation": transform.rotation,
        #         "velocity": transform.velocity
        #     }
        # except Exception as e:
        #     print(f"[XRPerception] Error getting agent state: {e}")
        #     return {"position": None, "rotation": None, "velocity": None}
        
        raise NotImplementedError(
            "XRPerception.get_agent_state() needs to be implemented based on actual XR application API"
        )
    
    def execute_action(self, agent_id: str, action: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Execute action in real XR application
        
        TODO: Implement real action execution logic
        """
        # Example implementation:
        # try:
        #     result = self.xr_client.execute_action(agent_id, action, params or {})
        #     return {
        #         "position": result.new_position,
        #         "rotation": result.new_rotation,
        #         "velocity": result.velocity,
        #         "visible_objects": result.visible_objects
        #     }
        # except Exception as e:
        #     print(f"[XRPerception] Error executing action: {e}")
        #     return {}
        
        raise NotImplementedError(
            "XRPerception.execute_action() needs to be implemented based on actual XR application API"
        )
    
    def get_environment_info(self) -> Dict[str, Any]:
        """
        Get XR environment information
        
        TODO: Implement real environment info retrieval
        """
        # Example implementation:
        # try:
        #     env_info = self.xr_client.get_environment_metadata()
        #     return {
        #         "type": "xr",
        #         "scene_name": env_info.scene_name,
        #         "total_objects": env_info.object_count,
        #         "boundaries": env_info.boundaries
        #     }
        # except Exception as e:
        #     print(f"[XRPerception] Error getting environment info: {e}")
        #     return {"type": "xr", "error": str(e)}
        
        raise NotImplementedError(
            "XRPerception.get_environment_info() needs to be implemented based on actual XR application API"
        )


class UnityPyAutoGUIPerception(PerceptionInterface):
    """
    Perception implementation that interacts with a running Unity game window via pyautogui.

    - Actions (built-in mapping):
      - "forward"    -> 'w'
      - "backward"   -> 's'
      - "move_left"  -> 'a'
      - "move_right" -> 'd'
      - "move_up"    -> 'r'
      - "move_down"  -> 'f'
      - "look_left"  -> 'left'
      - "look_right" -> 'right'
      - "look_up"    -> 'up'
      - "look_down"  -> 'down'
      - "tilt_left"  -> 'q'
      - "tilt_right" -> 'e'
    - Perception:
      - Captures a screenshot (full screen or specified region)
      - Returns a placeholder list containing the screenshot path as visible "objects"

    Note: Ensure the Unity window has focus when running. This class does not switch focus.
    """

    def __init__(
        self,
        screenshot_dir: Optional[str] = None,
        capture_region: Optional[tuple] = None,  # (left, top, width, height)
        keymap: Optional[Dict[str, str]] = None,
        press_time: float = 0.3,
        messaging_base_url: Optional[str] = None,
    ):
        if pyautogui is None:
            raise RuntimeError("pyautogui is not installed. Please `pip install pyautogui`.")

        self.capture_region = capture_region
        self.press_time = press_time
        self.agent_steps: Dict[str, int] = {}

        base_dir = Path(screenshot_dir) if screenshot_dir else Path.cwd() / "screenshots"
        base_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir = base_dir
        # Optional centralized messaging server (FastAPI env_server)
        # Priority: parameter > environment variable > config file
        self.messaging_base_url = (messaging_base_url or os.getenv("ENV_SERVER_URL") or get_config_value("env_server_url") or "").rstrip("/")

    def _capture(self, agent_id: str) -> str:
        ts = time.strftime("%Y%m%d-%H%M%S")
        filename = f"{agent_id}_{ts}_{int(time.time()*1000)%1000:03d}.png"
        path = self.screenshot_dir / filename

        img = pyautogui.screenshot(region=self.capture_region) if self.capture_region else pyautogui.screenshot()
        img.save(path)
        return str(path)

    def get_visible_objects(self, agent_id: str, position: Any) -> List[str]:
        path = self._capture(agent_id)
        return [f"screenshot:{path}"]

    def get_agent_state(self, agent_id: str) -> Dict[str, Any]:
        return {
            "position": self.agent_steps.get(agent_id, 0),
            "rotation": None,
            "velocity": None,
        }

    def execute_action(self, agent_id: str, action: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        self._perform_movement_action(action)

        # Update logical step counter
        self.agent_steps[agent_id] = self.agent_steps.get(agent_id, 0) + 1

        # Don't capture screenshot here - it will be done in the next PerceptionNode
        # This avoids redundant screenshots and ensures all screenshot processing
        # (caption generation and object extraction) happens in one place
        return {
            "position": self.agent_steps[agent_id],
            "rotation": None,
            "velocity": None,
            "visible_objects": [],  # Will be updated in next PerceptionNode
        }

    def _perform_movement_action(self, action: str) -> None:
        """Encapsulated movement action handler with internal key mapping (no env vars)."""
        mapping: Dict[str, str] = {
            "forward": "w",
            "backward": "s",
            "move_left": "a",
            "move_right": "d",
            "move_up": "r",
            "move_down": "f",
            "look_left": "left",
            "look_right": "right",
            "look_up": "up",
            "look_down": "down",
            "tilt_left": "q",
            "tilt_right": "e",
        }
        key = mapping.get(action)
        if not key:
            return
        try:
            pyautogui.keyDown(key)
            time.sleep(self.press_time)
        finally:
            pyautogui.keyUp(key)

    def get_environment_info(self) -> Dict[str, Any]:
        return {
            "type": "unity",
            "screenshot_dir": str(self.screenshot_dir),
            "capture_region": self.capture_region,
        }

    # Messaging via centralized server when configured
    def send_message(self, sender: str, recipient: str, message: str) -> None:
        if not self.messaging_base_url:
            raise NotImplementedError("Messaging server not configured. Set ENV_SERVER_URL or pass messaging_base_url.")
        resp = requests.post(f"{self.messaging_base_url}/messages/send", json={"sender": sender, "recipient": recipient, "message": message}, timeout=10)
        resp.raise_for_status()

    def poll_messages(self, agent_id: str) -> List[Dict[str, Any]]:
        if not self.messaging_base_url:
            raise NotImplementedError("Messaging server not configured. Set ENV_SERVER_URL or pass messaging_base_url.")
        resp = requests.post(f"{self.messaging_base_url}/messages/poll", json={"agent_id": agent_id}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("messages", [])


class Unity3DPerception(PerceptionInterface):
    """
    Perception implementation for Unity3D with simplified action space.
    
    This class communicates with Unity via file system (same as UnityCameraPerception):
    - Writes screenshot request files to Unity's agent_requests directory
    - Unity reads requests and captures screenshots with agent ID and timestamp in filename
    - Reads the generated screenshot files from Unity's output directory
    
    Differences from unity-camera mode:
    - Does NOT require Meta XR Simulator window focus
    - Simplified action space (WSAD only, no jump):
      - "forward"    -> 'w'
      - "backward"   -> 's'
      - "move_left"  -> 'a'
      - "move_right" -> 'd'
    """

    def __init__(
        self,
        unity_output_base_path: str,
        agent_request_dir: Optional[str] = None,
        press_time: float = 0.3,
        screenshot_timeout: float = 5.0,
        messaging_base_url: Optional[str] = None,
    ):
        """
        Args:
            unity_output_base_path: Base path where Unity saves screenshots (e.g., "D:/output")
            agent_request_dir: Directory for Agent screenshot requests (defaults to {unity_output_base_path}/agent_requests)
            press_time: Press time for movement actions
            screenshot_timeout: Maximum time to wait for screenshot to appear (seconds)
            messaging_base_url: Optional centralized messaging server URL
        """
        # For unity3d mode we use keyboard-based control via pydirectinput on Windows only.
        if not IS_WINDOWS:
            raise RuntimeError("Unity3DPerception keyboard control is only supported on Windows.")
        if pydirectinput is None:
            raise RuntimeError("pydirectinput is not installed. Please `pip install pydirectinput` for unity3d mode.")
        
        self.unity_output_base_path = Path(unity_output_base_path)
        self.press_time = press_time
        self.screenshot_timeout = screenshot_timeout
        self.agent_steps: Dict[str, int] = {}
        
        # Setup agent request directory (camera extraction requests)
        if agent_request_dir:
            self.agent_request_dir = Path(agent_request_dir)
        else:
            self.agent_request_dir = self.unity_output_base_path / "agent_requests"
        self.agent_request_dir.mkdir(parents=True, exist_ok=True)
        
        # Optional centralized messaging server
        # Priority: parameter > environment variable > config file
        self.messaging_base_url = (messaging_base_url or os.getenv("ENV_SERVER_URL") or get_config_value("env_server_url") or "").rstrip("/")
        
        # Track last screenshot request time to detect new screenshots
        self._last_request_time: Dict[str, float] = {}

    def _request_screenshot(self, agent_id: str) -> str:
        """Request screenshot from Unity and return the expected screenshot path"""
        timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        timestamp_ms = f"{timestamp}_{int(time.time()*1000)%1000:03d}"
        
        # Create request JSON
        request_data = {
            "agent_id": agent_id,
            "timestamp": timestamp_ms
        }
        
        # Write request file
        request_filename = f"{agent_id}_{timestamp_ms}.request"
        request_path = self.agent_request_dir / request_filename
        
        try:
            with open(request_path, 'w') as f:
                json.dump(request_data, f)
            self._last_request_time[agent_id] = time.time()
            print(f"[Unity3DPerception] Screenshot request sent: {request_path}")
        except Exception as e:
            raise RuntimeError(f"Failed to write screenshot request: {e}")
        
        return timestamp_ms

    def _find_latest_screenshot(self, agent_id: str, timestamp: str, timeout: float) -> Optional[str]:
        """Find the latest screenshot matching agent_id and timestamp"""
        start_time = time.time()
        
        # Search in Unity output directory structure
        # Simplified path: {outputBasePath}/screenshots/{CameraName}/
        # Filename format: {agent_id}_{timestamp}_{ProjectName}_{CameraName}_screenshot_frame_*.png
        
        # Use recursive search to find all matching files, then filter for "Main Camera" folder
        search_patterns = [
            # Pattern 1: Recursively search in screenshots folder
            str(self.unity_output_base_path / "screenshots" / "**" / f"{agent_id}_{timestamp}*.png"),
            # Pattern 2: Timestamp folder search (if using ByTimestamp mode)
            str(self.unity_output_base_path / "screenshots" / "**" / timestamp / f"{agent_id}_{timestamp}*.png"),
            # Pattern 3: Legacy path support (with project subfolder)
            str(self.unity_output_base_path / "**" / "*_screenshots" / "**" / f"{agent_id}_{timestamp}*.png"),
            # Pattern 4: Fallback - any file with agent_id and timestamp
            str(self.unity_output_base_path / "**" / f"{agent_id}_{timestamp}*.png"),
        ]
        
        while time.time() - start_time < timeout:
            for pattern in search_patterns:
                matches = glob.glob(pattern, recursive=True)
                
                if matches:
                    # Filter: match files in "Main Camera" or "MainCamera" folder (case-insensitive)
                    # Support both "main camera" (space), "main_camera" (underscore), and "maincamera" (no separator)
                    main_camera_matches = [
                        m for m in matches 
                        if any(
                            "main camera" in part.lower() or 
                            "main_camera" in part.lower() or 
                            (part.lower().startswith("main") and "camera" in part.lower())
                            for part in Path(m).parts
                        )
                    ]
                    
                    if main_camera_matches:
                        # Return the most recently modified file
                        latest = max(main_camera_matches, key=lambda p: Path(p).stat().st_mtime)
                        # Check if file was created after our request
                        if Path(latest).stat().st_mtime >= self._last_request_time.get(agent_id, 0):
                            return latest
                    # If no main camera matches found, return any match (fallback)
                    elif matches:
                        latest = max(matches, key=lambda p: Path(p).stat().st_mtime)
                        if Path(latest).stat().st_mtime >= self._last_request_time.get(agent_id, 0):
                            return latest
            
            time.sleep(0.1)  # Check every 100ms
        
        return None

    def get_visible_objects(self, agent_id: str, position: Any) -> List[str]:
        """Request screenshot from Unity and return path"""
        # Request screenshot
        timestamp = self._request_screenshot(agent_id)
        
        # Wait for screenshot to be created
        screenshot_path = self._find_latest_screenshot(agent_id, timestamp, self.screenshot_timeout)
        
        if screenshot_path:
            print(f"[Unity3DPerception] Screenshot received: {screenshot_path}")
            return [f"screenshot:{screenshot_path}"]
        else:
            print(f"[Unity3DPerception] Warning: Screenshot not found for agent {agent_id}, timestamp {timestamp}")
            # Return empty list or fallback behavior
            return []

    def get_agent_state(self, agent_id: str) -> Dict[str, Any]:
        return {
            "position": self.agent_steps.get(agent_id, 0),
            "rotation": None,
            "velocity": None,
        }

    def execute_action(self, agent_id: str, action: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute movement action (unity3d mode) via keyboard simulation.
        
        Priority:
        1) pydirectinput (Windows-friendly for games)
        2) SendInput fallback (Win32)
        3) pyautogui (generic)
        """
        action_str = str(action).strip().lower()
        print(f"[Unity3DPerception] Agent '{agent_id}' executing action via keyboard: {action_str}")

        self._perform_movement_action(action_str)

        # Update logical step counter
        self.agent_steps[agent_id] = self.agent_steps.get(agent_id, 0) + 1
        
        return {
            "position": self.agent_steps[agent_id],
            "rotation": None,
            "velocity": None,
            "visible_objects": [],  # Will be updated in next PerceptionNode
        }

    def _perform_movement_action(self, action: str) -> None:
        """Simplified movement action handler - only WSAD (with console logging).
        
        - On Windows: uses pydirectinput
        """
        mapping: Dict[str, str] = {
            "forward": "w",
            "backward": "s",
            "move_left": "a",
            "move_right": "d",
        }
        key = mapping.get(action)
        if not key:
            print(f"[Unity3DPerception] Warning: Unknown action '{action}', skipping.")
            return

        # At this point we already ensured we are on Windows and pydirectinput is available.
        print(f"[Unity3DPerception] (pydirectinput) Pressing key '{key}' for action '{action}' "
              f"(press_time={self.press_time}s).")
        try:
            pydirectinput.keyDown(key)
            time.sleep(self.press_time)
        except Exception as e:
            print(f"[Unity3DPerception] Error while executing action '{action}' with pydirectinput: {e}")
        finally:
            try:
                pydirectinput.keyUp(key)
            except Exception as e:
                print(f"[Unity3DPerception] Error while releasing key '{key}' with pydirectinput: {e}")

    def get_environment_info(self) -> Dict[str, Any]:
        return {
            "type": "unity3d",
            "unity_output_base_path": str(self.unity_output_base_path),
            "agent_request_dir": str(self.agent_request_dir),
        }

    # Messaging via centralized server when configured
    def send_message(self, sender: str, recipient: str, message: str) -> None:
        if not self.messaging_base_url:
            raise NotImplementedError("Messaging server not configured. Set ENV_SERVER_URL or pass messaging_base_url.")
        resp = requests.post(
            f"{self.messaging_base_url}/messages/send",
            json={"sender": sender, "recipient": recipient, "message": message},
            timeout=10
        )
        resp.raise_for_status()

    def poll_messages(self, agent_id: str) -> List[Dict[str, Any]]:
        if not self.messaging_base_url:
            raise NotImplementedError("Messaging server not configured. Set ENV_SERVER_URL or pass messaging_base_url.")
        resp = requests.post(
            f"{self.messaging_base_url}/messages/poll",
            json={"agent_id": agent_id},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("messages", [])


class UnityCameraPerception(PerceptionInterface):
    """
    Perception implementation that uses Unity camera extraction package for Agent-controlled screenshots.
    
    This class communicates with Unity via file system:
    - Writes screenshot request files to Unity's agent_requests directory
    - Unity reads requests and captures screenshots with agent ID and timestamp in filename
    - Reads the generated screenshot files from Unity's output directory
    
    - Actions (built-in mapping via pyautogui for movement):
      - "forward"    -> 'w'
      - "backward"   -> 's'
      - "move_left"  -> 'a'
      - "move_right" -> 'd'
      - "move_up"    -> 'r'
      - "move_down"  -> 'f'
      - "look_left"  -> 'left'
      - "look_right" -> 'right'
      - "look_up"    -> 'up'
      - "look_down"  -> 'down'
      - "tilt_left"  -> 'q'
      - "tilt_right" -> 'e'
    """

    def __init__(
        self,
        unity_output_base_path: str,
        agent_request_dir: Optional[str] = None,
        press_time: float = 1.0,
        screenshot_timeout: float = 5.0,
        messaging_base_url: Optional[str] = None,
    ):
        """
        Args:
            unity_output_base_path: Base path where Unity saves screenshots (e.g., "D:/output")
            agent_request_dir: Directory for Agent screenshot requests (defaults to {unity_output_base_path}/agent_requests)
            press_time: Press time for movement actions
            screenshot_timeout: Maximum time to wait for screenshot to appear (seconds)
            messaging_base_url: Optional centralized messaging server URL
        """
        if pyautogui is None:
            raise RuntimeError("pyautogui is not installed. Please `pip install pyautogui`.")
        
        self.unity_output_base_path = Path(unity_output_base_path)
        self.press_time = press_time
        self.screenshot_timeout = screenshot_timeout
        self.agent_steps: Dict[str, int] = {}
        
        # Setup agent request directory
        if agent_request_dir:
            self.agent_request_dir = Path(agent_request_dir)
        else:
            self.agent_request_dir = self.unity_output_base_path / "agent_requests"
        self.agent_request_dir.mkdir(parents=True, exist_ok=True)
        
        # Optional centralized messaging server
        # Priority: parameter > environment variable > config file
        self.messaging_base_url = (messaging_base_url or os.getenv("ENV_SERVER_URL") or get_config_value("env_server_url") or "").rstrip("/")
        
        # Track last screenshot request time to detect new screenshots
        self._last_request_time: Dict[str, float] = {}

    def _request_screenshot(self, agent_id: str) -> str:
        """Request screenshot from Unity and return the expected screenshot path"""
        timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        timestamp_ms = f"{timestamp}_{int(time.time()*1000)%1000:03d}"
        
        # Create request JSON
        request_data = {
            "agent_id": agent_id,
            "timestamp": timestamp_ms
        }
        
        # Write request file
        request_filename = f"{agent_id}_{timestamp_ms}.request"
        request_path = self.agent_request_dir / request_filename
        
        try:
            with open(request_path, 'w') as f:
                json.dump(request_data, f)
            self._last_request_time[agent_id] = time.time()
        except Exception as e:
            raise RuntimeError(f"Failed to write screenshot request: {e}")
        
        return timestamp_ms

    def _find_latest_screenshot(self, agent_id: str, timestamp: str, timeout: float) -> Optional[str]:
        """Find the latest screenshot matching agent_id and timestamp"""
        start_time = time.time()
        
        # Search in Unity output directory structure
        # Simplified path: {outputBasePath}/screenshots/{CameraName}/
        # Filename format: {agent_id}_{timestamp}_{ProjectName}_{CameraName}_screenshot_frame_*.png
        
        # Use recursive search to find all matching files, then filter for "Main Camera" folder
        search_patterns = [
            # Pattern 1: Recursively search in screenshots folder
            str(self.unity_output_base_path / "screenshots" / "**" / f"{agent_id}_{timestamp}*.png"),
            # Pattern 2: Timestamp folder search (if using ByTimestamp mode)
            str(self.unity_output_base_path / "screenshots" / "**" / timestamp / f"{agent_id}_{timestamp}*.png"),
            # Pattern 3: Legacy path support (with project subfolder)
            str(self.unity_output_base_path / "**" / "*_screenshots" / "**" / f"{agent_id}_{timestamp}*.png"),
            # Pattern 4: Fallback - any file with agent_id and timestamp
            str(self.unity_output_base_path / "**" / f"{agent_id}_{timestamp}*.png"),
        ]
        
        while time.time() - start_time < timeout:
            for pattern in search_patterns:
                matches = glob.glob(pattern, recursive=True)
                
                if matches:
                    # Filter: only match files in "Main Camera" folder (case-insensitive, but preserve space)
                    main_camera_matches = [
                        m for m in matches 
                        if any("main camera" in part.lower() for part in Path(m).parts)
                    ]
                    
                    if main_camera_matches:
                        # Return the most recently modified file
                        latest = max(main_camera_matches, key=lambda p: Path(p).stat().st_mtime)
                        # Check if file was created after our request
                        if Path(latest).stat().st_mtime >= self._last_request_time.get(agent_id, 0):
                            return latest
            
            time.sleep(0.1)  # Check every 100ms
        
        return None

    def get_visible_objects(self, agent_id: str, position: Any) -> List[str]:
        """Request screenshot from Unity and return path"""
        # Request screenshot
        timestamp = self._request_screenshot(agent_id)
        
        # Wait for screenshot to be created
        screenshot_path = self._find_latest_screenshot(agent_id, timestamp, self.screenshot_timeout)
        
        if screenshot_path:
            return [f"screenshot:{screenshot_path}"]
        else:
            print(f"[UnityCameraPerception] Warning: Screenshot not found for agent {agent_id}, timestamp {timestamp}")
            # Return empty list or fallback behavior
            return []

    def get_agent_state(self, agent_id: str) -> Dict[str, Any]:
        return {
            "position": self.agent_steps.get(agent_id, 0),
            "rotation": None,
            "velocity": None,
        }

    def execute_action(self, agent_id: str, action: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute movement action using pyautogui"""
        self._perform_movement_action(action)
        
        # Update logical step counter
        self.agent_steps[agent_id] = self.agent_steps.get(agent_id, 0) + 1
        
        return {
            "position": self.agent_steps[agent_id],
            "rotation": None,
            "velocity": None,
            "visible_objects": [],  # Will be updated in next PerceptionNode
        }

    def _perform_movement_action(self, action: str) -> None:
        """Encapsulated movement action handler with internal key mapping"""
        mapping: Dict[str, str] = {
            "forward": "w",
            "backward": "s",
            "move_left": "a",
            "move_right": "d",
            "move_up": "r",
            "move_down": "f",
            "look_left": "left",
            "look_right": "right",
            "look_up": "up",
            "look_down": "down",
            "tilt_left": "q",
            "tilt_right": "e",
        }
        key = mapping.get(action)
        if not key:
            return
        try:
            pyautogui.keyDown(key)
            time.sleep(self.press_time)
        finally:
            pyautogui.keyUp(key)

    def get_environment_info(self) -> Dict[str, Any]:
        return {
            "type": "unity-camera",
            "unity_output_base_path": str(self.unity_output_base_path),
            "agent_request_dir": str(self.agent_request_dir),
        }

    # Messaging via centralized server when configured
    def send_message(self, sender: str, recipient: str, message: str) -> None:
        if not self.messaging_base_url:
            raise NotImplementedError("Messaging server not configured. Set ENV_SERVER_URL or pass messaging_base_url.")
        resp = requests.post(
            f"{self.messaging_base_url}/messages/send",
            json={"sender": sender, "recipient": recipient, "message": message},
            timeout=10
        )
        resp.raise_for_status()

    def poll_messages(self, agent_id: str) -> List[Dict[str, Any]]:
        if not self.messaging_base_url:
            raise NotImplementedError("Messaging server not configured. Set ENV_SERVER_URL or pass messaging_base_url.")
        resp = requests.post(
            f"{self.messaging_base_url}/messages/poll",
            json={"agent_id": agent_id},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("messages", [])


# Factory function: convenient for creating different perception implementations
def create_perception(perception_type: str = "mock", **kwargs) -> PerceptionInterface:
    """
    Factory function for creating perception instances
    
    Args:
        perception_type: Perception type ("mock", "xr", "unity", "unity-camera", or "unity3d")
        **kwargs: Arguments passed to perception class constructor
    
    Returns:
        Perception instance
    
    Examples:
        # Create mock perception
        perception = create_perception("mock", env=mock_env)
        
        # Create XR perception
        perception = create_perception("xr", xr_client=client, config={"host": "localhost"})
        
        # Create Unity3D perception (simplified action space)
        perception = create_perception("unity3d", unity_output_base_path="/path/to/output")
    """
    if perception_type == "mock":
        return MockPerception(kwargs.get("env"))
    elif perception_type == "xr":
        return XRPerception(
            xr_client=kwargs.get("xr_client"),
            config=kwargs.get("config")
        )
    elif perception_type == "unity":
        return UnityPyAutoGUIPerception(
            screenshot_dir=kwargs.get("screenshot_dir"),
            capture_region=kwargs.get("capture_region"),
            keymap=kwargs.get("keymap"),
            press_time=kwargs.get("press_time", 0.3),
            messaging_base_url=kwargs.get("messaging_base_url") or os.getenv("ENV_SERVER_URL"),
        )
    elif perception_type == "unity3d":
        # New simplified Unity3D perception mode (WSAD + Space only, no window focus required)
        unity_output_base_path = kwargs.get("unity_output_base_path") or os.getenv("UNITY_OUTPUT_BASE_PATH")
        if not unity_output_base_path:
            raise ValueError("Unity3DPerception requires 'unity_output_base_path' or UNITY_OUTPUT_BASE_PATH")
        return Unity3DPerception(
            unity_output_base_path=unity_output_base_path,
            agent_request_dir=kwargs.get("agent_request_dir") or os.getenv("AGENT_REQUEST_DIR"),
            press_time=float(kwargs.get("press_time", os.getenv("STEP_SLEEP", "0.3"))),
            screenshot_timeout=float(kwargs.get("screenshot_timeout", os.getenv("SCREENSHOT_TIMEOUT", "5.0"))),
            messaging_base_url=kwargs.get("messaging_base_url") or os.getenv("ENV_SERVER_URL"),
        )
    elif perception_type == "unity-camera":
        unity_output_base_path = kwargs.get("unity_output_base_path") or os.getenv("UNITY_OUTPUT_BASE_PATH")
        if not unity_output_base_path:
            raise ValueError("UnityCameraPerception requires 'unity_output_base_path' or UNITY_OUTPUT_BASE_PATH")
        return UnityCameraPerception(
            unity_output_base_path=unity_output_base_path,
            agent_request_dir=kwargs.get("agent_request_dir") or os.getenv("AGENT_REQUEST_DIR"),
            press_time=float(kwargs.get("press_time", os.getenv("STEP_SLEEP", "1.0"))),
            screenshot_timeout=float(kwargs.get("screenshot_timeout", os.getenv("SCREENSHOT_TIMEOUT", "5.0"))),
            messaging_base_url=kwargs.get("messaging_base_url") or os.getenv("ENV_SERVER_URL"),
        )
    else:
        raise ValueError(f"Unknown perception type: {perception_type}")


if __name__ == "__main__":
    # Test mock perception
    print("Testing MockPerception...")
    
    # Create mock environment
    mock_env = {
        "objects": {
            0: ["chair", "lamp"],
            1: ["table", "book"],
            2: ["phone"]
        },
        "num_positions": 3,
        "agent_positions": {},
        "message_mailboxes": {},  # Dict: {agent_id: [msg1, msg2, ...]}
        "explored_by_all": set()
    }
    
    # Create using factory function
    perception = create_perception("mock", env=mock_env)
    
    # Test environment info
    env_info = perception.get_environment_info()
    print(f"\nEnvironment Info: {env_info}")
    
    # Test agent state
    perception.env["agent_positions"]["Agent1"] = 0
    state = perception.get_agent_state("Agent1")
    print(f"\nAgent1 Initial State: {state}")
    
    # Test perception
    visible = perception.get_visible_objects("Agent1", 0)
    print(f"Agent1 sees at position 0: {visible}")
    
    # Test action execution
    new_state = perception.execute_action("Agent1", "forward")
    print(f"\nAfter moving forward: {new_state}")
    
    visible = perception.get_visible_objects("Agent1", new_state["position"])
    print(f"Agent1 now sees: {visible}")
    
    print("\n✅ MockPerception test completed!")

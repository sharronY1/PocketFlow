"""
Perception Interface Abstraction Layer

This module defines abstract interfaces for environment perception, enabling easy switching 
between different perception implementations:
- MockPerception: Simulated environment (for development and testing)
- XRPerception: Real XR application interface (to be integrated with actual XR software)
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import requests
import os
import time
from pathlib import Path

try:
    import pyautogui  # type: ignore
except Exception:
    pyautogui = None


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

    # Optional messaging hooks for remote/shared environments
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

    - Actions:
      - "forward"  -> press 'w'
      - "backward" -> press 's'
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
        step_sleep_seconds: float = 0.3,
        messaging_base_url: Optional[str] = None,
    ):
        if pyautogui is None:
            raise RuntimeError("pyautogui is not installed. Please `pip install pyautogui`.")

        self.capture_region = capture_region
        self.keymap = keymap or {"forward": "w", "backward": "s"}
        self.step_sleep_seconds = step_sleep_seconds
        self.agent_steps: Dict[str, int] = {}

        base_dir = Path(screenshot_dir) if screenshot_dir else Path.cwd() / "screenshots"
        base_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir = base_dir
        # Optional centralized messaging server (FastAPI env_server)
        self.messaging_base_url = (messaging_base_url or os.getenv("ENV_SERVER_URL") or "").rstrip("/")

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
        key = self.keymap.get(action)
        if key:
            try:
                pyautogui.keyDown(key)
                time.sleep(self.step_sleep_seconds)
            finally:
                pyautogui.keyUp(key)

        # Update logical step counter
        self.agent_steps[agent_id] = self.agent_steps.get(agent_id, 0) + 1

        # Capture new perception after movement
        path = self._capture(agent_id)
        return {
            "position": self.agent_steps[agent_id],
            "rotation": None,
            "velocity": None,
            "visible_objects": [f"screenshot:{path}"],
        }

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


class RemotePerception(PerceptionInterface):
    """
    Remote perception implementation that calls a centralized environment service over HTTP.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')

    def get_visible_objects(self, agent_id: str, position: Any) -> List[str]:
        resp = requests.post(f"{self.base_url}/env/visible", json={"agent_id": agent_id, "position": position}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("visible_objects", [])

    def get_agent_state(self, agent_id: str) -> Dict[str, Any]:
        # In remote mode, position is managed by the server after actions. If needed, env info can include positions.
        info = self.get_environment_info()
        position = (info.get("agent_positions") or {}).get(agent_id, 0)
        return {"position": position}

    def execute_action(self, agent_id: str, action: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        resp = requests.post(f"{self.base_url}/env/execute", json={"agent_id": agent_id, "action": action}, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_environment_info(self) -> Dict[str, Any]:
        resp = requests.get(f"{self.base_url}/env/info", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def send_message(self, sender: str, recipient: str, message: str) -> None:
        resp = requests.post(f"{self.base_url}/messages/send", json={"sender": sender, "recipient": recipient, "message": message}, timeout=10)
        resp.raise_for_status()

    def poll_messages(self, agent_id: str) -> List[Dict[str, Any]]:
        resp = requests.post(f"{self.base_url}/messages/poll", json={"agent_id": agent_id}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("messages", [])


# Factory function: convenient for creating different perception implementations
def create_perception(perception_type: str = "mock", **kwargs) -> PerceptionInterface:
    """
    Factory function for creating perception instances
    
    Args:
        perception_type: Perception type ("mock" or "xr")
        **kwargs: Arguments passed to perception class constructor
    
    Returns:
        Perception instance
    
    Examples:
        # Create mock perception
        perception = create_perception("mock", env=mock_env)
        
        # Create XR perception
        perception = create_perception("xr", xr_client=client, config={"host": "localhost"})
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
            step_sleep_seconds=kwargs.get("step_sleep_seconds", 0.3),
            messaging_base_url=kwargs.get("messaging_base_url") or os.getenv("ENV_SERVER_URL"),
        )
    elif perception_type == "remote":
        base_url = kwargs.get("base_url") or os.getenv("ENV_SERVER_URL")
        if not base_url:
            raise ValueError("Remote perception requires 'base_url' or ENV_SERVER_URL")
        return RemotePerception(base_url=base_url)
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
        "message_queue": [],
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

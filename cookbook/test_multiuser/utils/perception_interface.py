"""
Perception Interface Abstraction Layer

This module defines abstract interfaces for environment perception, enabling easy switching 
between different perception implementations:
- MockPerception: Simulated environment (for development and testing)
- XRPerception: Real XR application interface (to be integrated with actual XR software)
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


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

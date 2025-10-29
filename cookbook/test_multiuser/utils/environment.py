"""
Environment simulation utilities
"""
import random
from typing import List, Dict, Any


def create_environment(num_positions: int = 10, object_pool: List[str] = None) -> Dict[str, Any]:
    """
    Create simulated environment
    
    Args:
        num_positions: Number of positions in environment
        object_pool: Optional object pool, uses default objects if None
    
    Returns:
        Environment dictionary
    """
    if object_pool is None:
        object_pool = [
            "chair", "table", "lamp", "book", "cup", 
            "pen", "phone", "keyboard", "monitor", "mouse",
            "plant", "picture", "clock", "vase", "mirror",
            "cushion", "rug", "shelf", "drawer", "cabinet"
        ]
    
    # Randomly assign 1-3 objects to each position
    objects = {}
    for pos in range(num_positions):
        num_objects = random.randint(1, 3)
        objects[pos] = random.sample(object_pool, num_objects)
    
    return {
        "objects": objects,
        "num_positions": num_positions,
        "agent_positions": {},
        "message_queue": [],
        "message_history": [],
        "explored_by_all": set()
    }


def get_visible_objects(position: int, env: Dict[str, Any]) -> List[str]:
    """
    Get visible objects at current position
    
    Args:
        position: Current position index
        env: Environment dictionary
    
    Returns:
        List of objects
    """
    return env["objects"].get(position, [])


def execute_action(agent_id: str, action: str, env: Dict[str, Any]) -> int:
    """
    Execute action and update environment
    
    Args:
        agent_id: Agent identifier
        action: "forward" or "backward"
        env: Environment dictionary
    
    Returns:
        New position
    """
    current_pos = env["agent_positions"].get(agent_id, 0)
    
    if action == "forward":
        new_pos = min(current_pos + 1, env["num_positions"] - 1)
    elif action == "backward":
        new_pos = max(current_pos - 1, 0)
    else:
        new_pos = current_pos  # Invalid action, stay in place
    
    env["agent_positions"][agent_id] = new_pos
    
    # Update global exploration record
    visible = get_visible_objects(new_pos, env)
    env["explored_by_all"].update(visible)
    
    return new_pos


def add_message(env: Dict[str, Any], sender: str, recipient: str, message: str):
    """
    Add message between agents
    
    Args:
        env: Environment dictionary
        sender: Sender agent_id
        recipient: Recipient agent_id
        message: Message content
    """
    msg = {
        "sender": sender,
        "recipient": recipient,
        "message": message
    }
    env["message_queue"].append(msg)
    
    # Also save to history (never deleted)
    if "message_history" not in env:
        env["message_history"] = []
    env["message_history"].append(msg.copy())


def get_messages_for(env: Dict[str, Any], agent_id: str) -> List[Dict[str, str]]:
    """
    Get messages for specified agent (and remove from queue)
    
    Args:
        env: Environment dictionary
        agent_id: Agent identifier
    
    Returns:
        List of messages
    """
    messages = []
    remaining = []
    
    for msg in env["message_queue"]:
        # Deliver only messages not sent by the same agent
        if (msg["recipient"] == agent_id or msg["recipient"] == "all") and msg.get("sender") != agent_id:
            messages.append(msg)
        else:
            remaining.append(msg)
    
    env["message_queue"] = remaining
    return messages


if __name__ == "__main__":
    # Test environment
    print("Testing environment simulation...")
    
    # Create environment
    env = create_environment(num_positions=10)
    print(f"\nEnvironment created with {env['num_positions']} positions")
    
    # Display environment
    print("\nEnvironment layout:")
    for pos, objects in env["objects"].items():
        print(f"  Position {pos}: {objects}")
    
    # Initialize two agents
    env["agent_positions"]["agent1"] = 0
    env["agent_positions"]["agent2"] = 0
    
    # Simulate some actions
    print("\n--- Simulation ---")
    
    print("\nAgent1 at position 0, sees:", get_visible_objects(0, env))
    new_pos = execute_action("agent1", "forward", env)
    print(f"Agent1 moves forward to position {new_pos}")
    
    print("\nAgent2 at position 0, sees:", get_visible_objects(0, env))
    new_pos = execute_action("agent2", "forward", env)
    print(f"Agent2 moves forward to position {new_pos}")
    
    # Test messages
    print("\n--- Communication ---")
    add_message(env, "agent1", "agent2", "I found a chair at position 1")
    add_message(env, "agent2", "agent1", "I found a lamp at position 1")
    
    messages = get_messages_for(env, "agent2")
    print(f"\nAgent2 receives {len(messages)} messages:")
    for msg in messages:
        print(f"  From {msg['sender']}: {msg['message']}")
    
    print(f"\nTotal unique objects explored: {len(env['explored_by_all'])}")
    print(f"Objects: {env['explored_by_all']}")


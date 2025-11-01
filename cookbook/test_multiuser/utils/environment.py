"""
Environment simulation utilities
"""
import random
from typing import List, Dict, Any


def create_shared_memory() -> Dict[str, Any]:
    """
    Create shared memory structure for all agents to access and update
    
    This replaces the preset objects in global_env. Objects are dynamically
    discovered by agents through their observations (e.g., analyzing Unity screenshots).
    
    Returns:
        Shared memory dictionary with the following structure:
        - objects: Set of discovered objects (only increases, never decreases)
        - agent_positions: Dict mapping agent_id -> current position
        - message_mailboxes: Dict mapping agent_id -> list of messages (each agent has its own mailbox)
        - message_history: List of all messages (never deleted)
    """
    return {
        "objects": set(),  # All unique objects discovered across all positions (only increases)
        "agent_positions": {},
        "message_mailboxes": {},  # Dict: {agent_id: [msg1, msg2, ...]}
        "message_history": []
    }


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
        "message_mailboxes": {},  # Dict: {agent_id: [msg1, msg2, ...]}
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
    Add message between agents using mailbox system
    
    Each agent has its own mailbox (dict). When sending a message:
    - If recipient is a specific agent_id, put message in that agent's mailbox
    - If recipient is "all", put message in all agents' mailboxes (except sender)
    
    Args:
        env: Environment dictionary
        sender: Sender agent_id
        recipient: Recipient agent_id (can be specific agent or "all")
        message: Message content
    """
    msg = {
        "sender": sender,
        "recipient": recipient,
        "message": message
    }
    
    # Ensure message_mailboxes exists
    if "message_mailboxes" not in env:
        env["message_mailboxes"] = {}
    
    # Also save to history (never deleted)
    if "message_history" not in env:
        env["message_history"] = []
    env["message_history"].append(msg.copy())
    
    # Deliver to mailbox(es)
    if recipient == "all":
        # Send to all known agents except sender
        all_agents = set(env.get("agent_positions", {}).keys())
        all_agents.discard(sender)  # Remove sender (agents don't receive their own messages)
        
        for agent_id in all_agents:
            if agent_id not in env["message_mailboxes"]:
                env["message_mailboxes"][agent_id] = []
            env["message_mailboxes"][agent_id].append(msg.copy())
    else:
        # Send to specific agent (but not if it's the sender)
        if recipient != sender:
            if recipient not in env["message_mailboxes"]:
                env["message_mailboxes"][recipient] = []
            env["message_mailboxes"][recipient].append(msg.copy())


def get_messages_for(env: Dict[str, Any], agent_id: str) -> List[Dict[str, str]]:
    """
    Get messages for specified agent from their mailbox (and clear the mailbox)
    
    Each agent has its own mailbox. This function:
    1. Retrieves all messages from the agent's mailbox
    2. Filters out messages sent by the agent itself (safety check)
    3. Clears the mailbox after reading
    
    Args:
        env: Environment dictionary
        agent_id: Agent identifier
    
    Returns:
        List of messages
    """
    # Ensure message_mailboxes exists
    if "message_mailboxes" not in env:
        env["message_mailboxes"] = {}
    
    # Get agent's mailbox
    mailbox = env["message_mailboxes"].get(agent_id, [])
    
    # Filter out self-messages (shouldn't happen with mailbox system, but safety check)
    messages = [msg for msg in mailbox if msg.get("sender") != agent_id]
    
    # Clear the mailbox after reading
    env["message_mailboxes"][agent_id] = []
    
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
    
    # Test messages (mailbox system)
    print("\n--- Communication (Mailbox System) ---")
    # Initialize agent positions so they exist in the system
    env["agent_positions"]["agent1"] = 0
    env["agent_positions"]["agent2"] = 1
    
    add_message(env, "agent1", "agent2", "I found a chair at position 1")
    add_message(env, "agent2", "agent1", "I found a lamp at position 1")
    add_message(env, "agent1", "all", "I found a table at position 2")
    
    print(f"\nMailbox status before reading:")
    print(f"  Agent1 mailbox: {len(env['message_mailboxes'].get('agent1', []))} messages")
    print(f"  Agent2 mailbox: {len(env['message_mailboxes'].get('agent2', []))} messages")
    
    messages = get_messages_for(env, "agent2")
    print(f"\nAgent2 receives {len(messages)} messages:")
    for msg in messages:
        print(f"  From {msg['sender']}: {msg['message']}")
    
    messages = get_messages_for(env, "agent1")
    print(f"\nAgent1 receives {len(messages)} messages:")
    for msg in messages:
        print(f"  From {msg['sender']}: {msg['message']}")
    
    print(f"\nMailbox status after reading:")
    print(f"  Agent1 mailbox: {len(env['message_mailboxes'].get('agent1', []))} messages")
    print(f"  Agent2 mailbox: {len(env['message_mailboxes'].get('agent2', []))} messages")
    
    print(f"\nTotal unique objects explored: {len(env['explored_by_all'])}")
    print(f"Objects: {env['explored_by_all']}")


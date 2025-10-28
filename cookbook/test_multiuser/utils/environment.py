"""
环境模拟工具
"""
import random
from typing import List, Dict, Any


def create_environment(num_positions: int = 10, object_pool: List[str] = None) -> Dict[str, Any]:
    """
    创建模拟环境
    
    Args:
        num_positions: 环境位置数量
        object_pool: 可选的物体池，如果为None则使用默认物体
    
    Returns:
        环境字典
    """
    if object_pool is None:
        object_pool = [
            "chair", "table", "lamp", "book", "cup", 
            "pen", "phone", "keyboard", "monitor", "mouse",
            "plant", "picture", "clock", "vase", "mirror",
            "cushion", "rug", "shelf", "drawer", "cabinet"
        ]
    
    # 为每个位置随机分配1-3个物体
    objects = {}
    for pos in range(num_positions):
        num_objects = random.randint(1, 3)
        objects[pos] = random.sample(object_pool, num_objects)
    
    return {
        "objects": objects,
        "num_positions": num_positions,
        "agent_positions": {},
        "message_queue": [],
        "explored_by_all": set()
    }


def get_visible_objects(position: int, env: Dict[str, Any]) -> List[str]:
    """
    获取当前位置可见的物体
    
    Args:
        position: 当前位置索引
        env: 环境字典
    
    Returns:
        物体列表
    """
    return env["objects"].get(position, [])


def execute_action(agent_id: str, action: str, env: Dict[str, Any]) -> int:
    """
    执行动作并更新环境
    
    Args:
        agent_id: agent标识
        action: "forward" 或 "backward"
        env: 环境字典
    
    Returns:
        新位置
    """
    current_pos = env["agent_positions"].get(agent_id, 0)
    
    if action == "forward":
        new_pos = min(current_pos + 1, env["num_positions"] - 1)
    elif action == "backward":
        new_pos = max(current_pos - 1, 0)
    else:
        new_pos = current_pos  # 无效动作，保持不动
    
    env["agent_positions"][agent_id] = new_pos
    
    # 更新全局探索记录
    visible = get_visible_objects(new_pos, env)
    env["explored_by_all"].update(visible)
    
    return new_pos


def add_message(env: Dict[str, Any], sender: str, recipient: str, message: str):
    """
    添加agent间消息
    
    Args:
        env: 环境字典
        sender: 发送者agent_id
        recipient: 接收者agent_id
        message: 消息内容
    """
    env["message_queue"].append({
        "sender": sender,
        "recipient": recipient,
        "message": message
    })


def get_messages_for(env: Dict[str, Any], agent_id: str) -> List[Dict[str, str]]:
    """
    获取发给指定agent的消息（并从队列中移除）
    
    Args:
        env: 环境字典
        agent_id: agent标识
    
    Returns:
        消息列表
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
    # 测试环境
    print("Testing environment simulation...")
    
    # 创建环境
    env = create_environment(num_positions=10)
    print(f"\nEnvironment created with {env['num_positions']} positions")
    
    # 显示环境
    print("\nEnvironment layout:")
    for pos, objects in env["objects"].items():
        print(f"  Position {pos}: {objects}")
    
    # 初始化两个agent
    env["agent_positions"]["agent1"] = 0
    env["agent_positions"]["agent2"] = 0
    
    # 模拟一些动作
    print("\n--- Simulation ---")
    
    print("\nAgent1 at position 0, sees:", get_visible_objects(0, env))
    new_pos = execute_action("agent1", "forward", env)
    print(f"Agent1 moves forward to position {new_pos}")
    
    print("\nAgent2 at position 0, sees:", get_visible_objects(0, env))
    new_pos = execute_action("agent2", "forward", env)
    print(f"Agent2 moves forward to position {new_pos}")
    
    # 测试消息
    print("\n--- Communication ---")
    add_message(env, "agent1", "agent2", "I found a chair at position 1")
    add_message(env, "agent2", "agent1", "I found a lamp at position 1")
    
    messages = get_messages_for(env, "agent2")
    print(f"\nAgent2 receives {len(messages)} messages:")
    for msg in messages:
        print(f"  From {msg['sender']}: {msg['message']}")
    
    print(f"\nTotal unique objects explored: {len(env['explored_by_all'])}")
    print(f"Objects: {env['explored_by_all']}")


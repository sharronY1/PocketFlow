"""
Multi-Agent XR环境探索系统 - 主程序
"""
import threading
from utils import create_environment, create_memory
from flow import create_agent_flow
import time


def run_agent(agent_id: str, global_env: dict, max_steps: int = 20):
    """
    运行单个Agent的探索流程
    
    Args:
        agent_id: Agent标识
        global_env: 全局共享环境
        max_steps: 最大探索步数
    """
    print(f"\n{'='*60}")
    print(f"Starting {agent_id}...")
    print(f"{'='*60}\n")
    
    # 创建Agent私有的shared store
    agent_shared = {
        "agent_id": agent_id,
        "global_env": global_env,
        "position": 0,
        "step_count": 0,
        
        # 记忆系统
        "memory_index": create_memory(dimension=384),
        "memory_texts": [],
        
        # 当前状态
        "visible_objects": [],
        "retrieved_memories": [],
        "other_agent_messages": [],
        
        # 决策结果
        "action": None,
        "action_reason": "",
        "message_to_others": "",
        
        # 探索历史
        "explored_objects": set(),
        "action_history": []
    }
    
    # 初始化环境中的agent位置
    global_env["agent_positions"][agent_id] = 0
    
    # 创建并运行Flow
    flow = create_agent_flow()
    
    try:
        flow.run(agent_shared)
    except Exception as e:
        print(f"\n[{agent_id}] Error: {e}")
        import traceback
        traceback.print_exc()
    
    # 打印总结
    print(f"\n{'='*60}")
    print(f"{agent_id} Exploration Summary")
    print(f"{'='*60}")
    print(f"Total steps: {agent_shared['step_count']}")
    print(f"Final position: {agent_shared['position']}")
    print(f"Unique objects explored: {len(agent_shared['explored_objects'])}")
    print(f"Objects: {agent_shared['explored_objects']}")
    print(f"Memories stored: {len(agent_shared['memory_texts'])}")
    print(f"{'='*60}\n")


def main():
    """主程序入口"""
    print("\n" + "="*60)
    print("Multi-Agent XR Environment Exploration System")
    print("="*60)
    
    # 创建全局环境
    print("\n[System] Creating environment...")
    global_env = create_environment(num_positions=10)
    global_env["max_steps"] = 15  # 每个agent最多探索15步
    
    print(f"[System] Environment created with {global_env['num_positions']} positions")
    print("\n[System] Environment layout:")
    for pos in sorted(global_env["objects"].keys()):
        print(f"  Position {pos}: {global_env['objects'][pos]}")
    
    # 创建两个Agent线程
    print("\n[System] Starting 2 agents...")
    
    agent1_thread = threading.Thread(
        target=run_agent,
        args=("Agent1", global_env, 15),
        name="Agent1Thread"
    )
    
    agent2_thread = threading.Thread(
        target=run_agent,
        args=("Agent2", global_env, 15),
        name="Agent2Thread"
    )
    
    # 启动线程
    start_time = time.time()
    agent1_thread.start()
    agent2_thread.start()
    
    # 等待两个agent完成
    agent1_thread.join()
    agent2_thread.join()
    
    elapsed_time = time.time() - start_time
    
    # 打印整体总结
    print("\n" + "="*60)
    print("FINAL SYSTEM SUMMARY")
    print("="*60)
    print(f"Total execution time: {elapsed_time:.2f} seconds")
    print(f"Total unique objects explored by all agents: {len(global_env['explored_by_all'])}")
    print(f"Objects: {global_env['explored_by_all']}")
    print(f"Coverage: {len(global_env['explored_by_all'])} / {sum(len(objs) for objs in global_env['objects'].values())} objects")
    print(f"Final agent positions:")
    for agent_id, pos in global_env["agent_positions"].items():
        print(f"  {agent_id}: position {pos}")
    print("="*60)
    
    print("\n[System] Exploration completed!")


if __name__ == "__main__":
    main()


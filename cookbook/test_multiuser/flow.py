"""
Multi-Agent探索系统的Flow定义
"""
from pocketflow import Flow
from nodes import (
    PerceptionNode,
    RetrieveMemoryNode,
    CommunicationNode,
    DecisionNode,
    ExecutionNode,
    UpdateMemoryNode
)


def create_agent_flow():
    """
    创建单个Agent的探索Flow
    
    Flow结构：
    Perception -> RetrieveMemory -> Communication -> Decision -> Execution -> UpdateMemory
                                                                                 |
                                                                                 v
                                                              "continue" -> (循环回Perception)
                                                              "end" -> (结束)
    """
    # 创建节点
    perception = PerceptionNode()
    retrieve = RetrieveMemoryNode()
    communicate = CommunicationNode()
    decide = DecisionNode(max_retries=3)  # 决策节点允许重试
    execute = ExecutionNode()
    update = UpdateMemoryNode()
    
    # 连接节点
    perception >> retrieve >> communicate >> decide >> execute >> update
    
    # 更新记忆后的分支
    update - "continue" >> perception  # 继续探索，回到感知节点
    update - "end"      # 结束（没有后续节点）
    
    # 创建Flow
    flow = Flow(start=perception)
    
    return flow


if __name__ == "__main__":
    # 测试Flow创建
    print("Creating agent flow...")
    flow = create_agent_flow()
    print("Flow created successfully!")
    print("\nFlow structure:")
    print("  Perception -> RetrieveMemory -> Communication -> Decision -> Execution -> UpdateMemory")
    print("                                                                              |")
    print("                                                   'continue' -> (loop back) ")
    print("                                                   'end' -> (finish)")


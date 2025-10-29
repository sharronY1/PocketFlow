"""
Flow definition for Multi-Agent exploration system
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
    Create exploration flow for a single Agent
    
    Flow structure:
    Perception -> RetrieveMemory -> Communication -> Decision -> Execution -> UpdateMemory
                                                                                 |
                                                                                 v
                                                              "continue" -> (loop back to Perception)
                                                              "end" -> (finish)
    """
    # Create nodes
    perception = PerceptionNode()
    retrieve = RetrieveMemoryNode()
    communicate = CommunicationNode()
    decide = DecisionNode(max_retries=3)  # Decision node allows retries
    execute = ExecutionNode()
    update = UpdateMemoryNode()
    
    # Connect nodes
    perception >> retrieve >> communicate >> decide >> execute >> update
    
    # Branch after memory update
    update - "continue" >> perception  # Continue exploration, loop back to perception
    update - "end"      # End (no subsequent nodes)
    
    # Create Flow
    flow = Flow(start=perception)
    
    return flow


if __name__ == "__main__":
    # Test Flow creation
    print("Creating agent flow...")
    flow = create_agent_flow()
    print("Flow created successfully!")
    print("\nFlow structure:")
    print("  Perception -> RetrieveMemory -> Communication -> Decision -> Execution -> UpdateMemory")
    print("                                                                              |")
    print("                                                   'continue' -> (loop back) ")
    print("                                                   'end' -> (finish)")


"""
Flow definition for Multi-Agent exploration system
"""
from pocketflow import Flow
from nodes import (
    PerceptionNode,
    CommunicationNode,
    DecisionNode,
    ExecutionNode,
    UpdateMemoryNode,
    SharedMemoryRetrieveNode,
    SharedMemoryUpdateNode
)


def create_agent_flow():
    """
    Create exploration flow for a single Agent
    
    Flow structure:
    Perception -> SharedMemoryRetrieve -> Communication -> Decision -> Execution -> UpdateMemory -> SharedMemoryUpdate
                                                                                                          |
                                                                                                          v
                                                                                       "continue" -> (loop back to Perception)
                                                                                       "end" -> (finish)
    
    Memory retrieval and storage are handled by SharedMemoryRetrieveNode and SharedMemoryUpdateNode,
    which interact with the centralized shared memory server.
    """
    # Create nodes
    perception = PerceptionNode()
    shared_retrieve = SharedMemoryRetrieveNode()
    communicate = CommunicationNode()
    decide = DecisionNode(max_retries=3)  # Decision node allows retries
    execute = ExecutionNode()
    update = UpdateMemoryNode()
    shared_update = SharedMemoryUpdateNode()
    
    # Connect nodes
    # Perception → SharedMemoryRetrieve → Communication → Decision → Execution → UpdateMemory → SharedMemoryUpdate
    perception >> shared_retrieve >> communicate >> decide >> execute >> update
    
    # UpdateMemory branches:
    # - "continue" goes to SharedMemoryUpdate, which then loops back
    # - "end" goes to SharedMemoryUpdate, which then ends
    update - "continue" >> shared_update
    update - "end" >> shared_update
    
    # Branch after shared memory update
    shared_update - "continue" >> perception  # Continue exploration, loop back to perception
    shared_update - "end"      # End (no subsequent nodes)
    
    # Create Flow
    flow = Flow(start=perception)
    
    return flow


if __name__ == "__main__":
    # Test Flow creation
    print("Creating agent flow...")
    flow = create_agent_flow()
    print("Flow created successfully!")
    print("\nFlow structure:")
    print("  Perception → SharedMemoryRetrieve → Communication → Decision → Execution → UpdateMemory → SharedMemoryUpdate")
    print("                                                                                                |")
    print("                                                                         'continue' → (loop back)")
    print("                                                                         'end' → (finish)")


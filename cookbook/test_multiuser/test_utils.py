"""
测试工具函数
运行此脚本确保所有依赖正确安装
"""
import os

def test_environment():
    """测试环境模拟"""
    print("\n" + "="*60)
    print("Testing Environment Simulation")
    print("="*60)
    
    from utils.environment import create_environment, get_visible_objects, execute_action
    
    env = create_environment(num_positions=5)
    print(f"✓ Environment created with {env['num_positions']} positions")
    
    env["agent_positions"]["test_agent"] = 0
    visible = get_visible_objects(0, env)
    print(f"✓ Position 0 objects: {visible}")
    
    new_pos = execute_action("test_agent", "forward", env)
    print(f"✓ Agent moved to position: {new_pos}")


def test_embedding():
    """测试embedding"""
    print("\n" + "="*60)
    print("Testing Embedding")
    print("="*60)
    
    from utils.embedding import get_embedding
    
    text = "This is a test sentence"
    emb = get_embedding(text)
    print(f"✓ Embedding shape: {emb.shape}")
    print(f"✓ First 5 values: {emb[:5]}")


def test_memory():
    """测试FAISS记忆"""
    print("\n" + "="*60)
    print("Testing FAISS Memory")
    print("="*60)
    
    from utils.memory import create_memory, add_to_memory, search_memory
    from utils.embedding import get_embedding
    
    index = create_memory(dimension=384)
    memory_texts = []
    
    # Add memories
    texts = ["I saw a chair", "I saw a table", "I saw a lamp"]
    for text in texts:
        emb = get_embedding(text)
        add_to_memory(index, emb, text, memory_texts)
    
    print(f"✓ Added {index.ntotal} memories")
    
    # Search
    query = "furniture"
    query_emb = get_embedding(query)
    results = search_memory(index, query_emb, memory_texts, top_k=2)
    
    print(f"✓ Search results for '{query}':")
    for text, dist in results:
        print(f"  - {text} (distance: {dist:.3f})")


def test_llm():
    """测试LLM调用"""
    print("\n" + "="*60)
    print("Testing LLM Call")
    print("="*60)
    
    if not os.getenv("GEMINI_API_KEY"):
        print("⚠ GEMINI_API_KEY not set, skipping LLM test")
        print("  Set it with: $env:GEMINI_API_KEY='your-key' (Windows)")
        print("  or: export GEMINI_API_KEY='your-key' (Linux/Mac)")
        return
    
    from utils.call_llm import call_llm
    
    prompt = "Say 'Hello, PocketFlow!' in one sentence."
    response = call_llm(prompt)
    print(f"✓ LLM response: {response[:100]}...")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("UTILITY FUNCTIONS TEST SUITE")
    print("="*60)
    
    try:
        test_environment()
        print("\n✓ Environment test passed!")
    except Exception as e:
        print(f"\n✗ Environment test failed: {e}")
    
    try:
        test_embedding()
        print("\n✓ Embedding test passed!")
    except Exception as e:
        print(f"\n✗ Embedding test failed: {e}")
        print("  Run: pip install sentence-transformers")
    
    try:
        test_memory()
        print("\n✓ Memory test passed!")
    except Exception as e:
        print(f"\n✗ Memory test failed: {e}")
        print("  Run: pip install faiss-cpu")
    
    try:
        test_llm()
        print("\n✓ LLM test passed!")
    except Exception as e:
        print(f"\n✗ LLM test failed: {e}")
        print("  Make sure GEMINI_API_KEY is set")
    
    print("\n" + "="*60)
    print("TEST SUITE COMPLETED")
    print("="*60)


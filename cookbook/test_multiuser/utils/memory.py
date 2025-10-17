"""
FAISS记忆管理工具
"""
import faiss
import numpy as np
from typing import List, Tuple


def create_memory(dimension: int = 384):
    """
    创建FAISS索引
    
    Args:
        dimension: 向量维度（默认384，匹配all-MiniLM-L6-v2）
    
    Returns:
        FAISS索引对象
    """
    # 使用L2距离的简单索引
    index = faiss.IndexFlatL2(dimension)
    return index


def add_to_memory(index: faiss.Index, embedding: np.ndarray, text: str, memory_texts: List[str]):
    """
    添加记忆到FAISS索引
    
    Args:
        index: FAISS索引
        embedding: 向量 (1D array)
        text: 对应的文本
        memory_texts: 文本列表（会被修改，添加新文本）
    """
    # FAISS需要2D数组
    if embedding.ndim == 1:
        embedding = embedding.reshape(1, -1)
    
    # 添加到索引
    index.add(embedding.astype('float32'))
    
    # 添加到文本列表
    memory_texts.append(text)


def search_memory(index: faiss.Index, query_embedding: np.ndarray, memory_texts: List[str], top_k: int = 3) -> List[Tuple[str, float]]:
    """
    从FAISS检索相关记忆
    
    Args:
        index: FAISS索引
        query_embedding: 查询向量
        memory_texts: 文本列表
        top_k: 返回top-k结果
    
    Returns:
        [(text, distance), ...] 按距离排序
    """
    # 如果索引为空，返回空列表
    if index.ntotal == 0:
        return []
    
    # FAISS需要2D数组
    if query_embedding.ndim == 1:
        query_embedding = query_embedding.reshape(1, -1)
    
    # 搜索
    k = min(top_k, index.ntotal)  # 不能超过索引中的总数
    distances, indices = index.search(query_embedding.astype('float32'), k)
    
    # 构造结果
    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx < len(memory_texts):  # 确保索引有效
            results.append((memory_texts[idx], float(dist)))
    
    return results


if __name__ == "__main__":
    # 测试记忆系统
    print("Testing FAISS memory system...")
    
    from embedding import get_embedding, get_embeddings_batch
    
    # 创建索引
    index = create_memory(dimension=384)
    memory_texts = []
    
    # 添加一些记忆
    memories = [
        "At position 0, I saw chair and table. Decided to go forward.",
        "At position 1, I saw lamp and book. Decided to go forward.",
        "At position 2, I saw cup and pen. Decided to go backward.",
        "At position 3, I saw phone and keyboard. Decided to go forward.",
    ]
    
    print(f"\nAdding {len(memories)} memories...")
    embeddings = get_embeddings_batch(memories)
    for emb, text in zip(embeddings, memories):
        add_to_memory(index, emb, text, memory_texts)
    
    print(f"Total memories: {index.ntotal}")
    
    # 搜索测试
    queries = [
        "What objects are at position 0?",
        "Where did I see a lamp?",
        "When did I go backward?"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        query_emb = get_embedding(query)
        results = search_memory(index, query_emb, memory_texts, top_k=2)
        
        for i, (text, dist) in enumerate(results, 1):
            print(f"  {i}. (distance={dist:.3f}) {text}")


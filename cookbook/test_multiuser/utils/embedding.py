"""
文本Embedding工具 - 使用sentence-transformers
"""
from sentence_transformers import SentenceTransformer
import numpy as np

# 全局模型实例（避免重复加载）
_model = None


def get_embedding_model():
    """获取或初始化embedding模型"""
    global _model
    if _model is None:
        # 使用轻量级模型：all-MiniLM-L6-v2 (80MB, 快速)
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model


def get_embedding(text: str) -> np.ndarray:
    """
    获取文本的embedding向量
    
    Args:
        text: 输入文本
    
    Returns:
        embedding向量 (384维)
    """
    model = get_embedding_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding


def get_embeddings_batch(texts: list) -> np.ndarray:
    """
    批量获取文本embeddings
    
    Args:
        texts: 文本列表
    
    Returns:
        embeddings矩阵，shape (len(texts), 384)
    """
    model = get_embedding_model()
    embeddings = model.encode(texts, convert_to_numpy=True)
    return embeddings


if __name__ == "__main__":
    # 测试embedding
    print("Testing embedding...")
    
    test_texts = [
        "I saw a chair and table at position 0",
        "I saw a lamp and book at position 5",
        "What objects are near position 0?"
    ]
    
    # 单个文本
    emb = get_embedding(test_texts[0])
    print(f"Single embedding shape: {emb.shape}")
    print(f"First 10 values: {emb[:10]}")
    
    # 批量文本
    embs = get_embeddings_batch(test_texts)
    print(f"\nBatch embeddings shape: {embs.shape}")
    
    # 计算相似度
    from numpy.linalg import norm
    
    # 文本0和文本1的相似度
    sim_01 = np.dot(embs[0], embs[1]) / (norm(embs[0]) * norm(embs[1]))
    print(f"Similarity between text 0 and 1: {sim_01:.4f}")
    
    # 文本0和查询的相似度
    sim_02 = np.dot(embs[0], embs[2]) / (norm(embs[0]) * norm(embs[2]))
    print(f"Similarity between text 0 and query: {sim_02:.4f}")


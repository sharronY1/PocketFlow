"""
Text Embedding utilities - Uses sentence-transformers (can be disabled via env var for local verification)
"""
import os
import numpy as np

# Global model instance (avoid repeated loading)
_model = None


def get_embedding_model():
    """Get or initialize embedding model"""
    global _model
    if _model is None:
        if os.getenv("DISABLE_EMBEDDING"):
            class _FakeModel:
                def encode(self, texts, convert_to_numpy=True):
                    def encode_one(t: str):
                        rng = np.random.default_rng(abs(hash(t)) % (2**32))
                        vec = rng.standard_normal(384).astype(np.float32)
                        # normalize
                        vec /= (np.linalg.norm(vec) + 1e-12)
                        return vec
                    if isinstance(texts, (list, tuple)):
                        return np.stack([encode_one(t) for t in texts], axis=0)
                    return encode_one(texts)
            _model = _FakeModel()
        else:
            from sentence_transformers import SentenceTransformer  # lazy import
            # Use lightweight model: all-MiniLM-L6-v2 (80MB, fast)
            _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model


def get_embedding(text: str) -> np.ndarray:
    """
    Get embedding vector for text
    
    Args:
        text: Input text
    
    Returns:
        Embedding vector (384 dimensions)
    """
    model = get_embedding_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding


def get_embeddings_batch(texts: list) -> np.ndarray:
    """
    Get embeddings for multiple texts in batch
    
    Args:
        texts: List of texts
    
    Returns:
        Embeddings matrix, shape (len(texts), 384)
    """
    model = get_embedding_model()
    embeddings = model.encode(texts, convert_to_numpy=True)
    return embeddings


if __name__ == "__main__":
    # Test embedding
    print("Testing embedding...")
    
    test_texts = [
        "I saw a chair and table at position 0",
        "I saw a lamp and book at position 5",
        "What objects are near position 0?"
    ]
    
    # Single text
    emb = get_embedding(test_texts[0])
    print(f"Single embedding shape: {emb.shape}")
    print(f"First 10 values: {emb[:10]}")
    
    # Batch texts
    embs = get_embeddings_batch(test_texts)
    print(f"\nBatch embeddings shape: {embs.shape}")
    
    # Calculate similarity
    from numpy.linalg import norm
    
    # Similarity between text 0 and text 1
    sim_01 = np.dot(embs[0], embs[1]) / (norm(embs[0]) * norm(embs[1]))
    print(f"Similarity between text 0 and 1: {sim_01:.4f}")
    
    # Similarity between text 0 and query
    sim_02 = np.dot(embs[0], embs[2]) / (norm(embs[0]) * norm(embs[2]))
    print(f"Similarity between text 0 and query: {sim_02:.4f}")


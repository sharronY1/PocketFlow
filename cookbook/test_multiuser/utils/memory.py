"""
FAISS memory management utilities
"""
import faiss
import numpy as np
from typing import List, Tuple


def create_memory(dimension: int = 384):
    """
    Create FAISS index
    
    Args:
        dimension: Vector dimension (default 384, matches all-MiniLM-L6-v2)
    
    Returns:
        FAISS index object
    """
    # Use simple index with L2 distance
    index = faiss.IndexFlatL2(dimension)
    return index


def add_to_memory(index: faiss.Index, embedding: np.ndarray, text: str, memory_texts: List[str]):
    """
    Add memory to FAISS index
    
    Args:
        index: FAISS index
        embedding: Vector (1D array)
        text: Corresponding text
        memory_texts: Text list (will be modified, new text added)
    """
    # FAISS requires 2D array
    if embedding.ndim == 1:
        embedding = embedding.reshape(1, -1)
    
    # Add to index
    index.add(embedding.astype('float32'))
    
    # Add to text list
    memory_texts.append(text)


def search_memory(index: faiss.Index, query_embedding: np.ndarray, memory_texts: List[str], top_k: int = 3) -> List[Tuple[str, float]]:
    """
    Retrieve relevant memories from FAISS
    
    Args:
        index: FAISS index
        query_embedding: Query vector
        memory_texts: Text list
        top_k: Return top-k results
    
    Returns:
        [(text, distance), ...] sorted by distance
    """
    # If index is empty, return empty list
    if index.ntotal == 0:
        return []
    
    # FAISS requires 2D array
    if query_embedding.ndim == 1:
        query_embedding = query_embedding.reshape(1, -1)
    
    # Search
    k = min(top_k, index.ntotal)  # Cannot exceed total number in index
    distances, indices = index.search(query_embedding.astype('float32'), k)
    
    # Construct results
    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx < len(memory_texts):  # Ensure valid index
            results.append((memory_texts[idx], float(dist)))
    
    return results


if __name__ == "__main__":
    # Test memory system
    print("Testing FAISS memory system...")
    
    from embedding import get_embedding, get_embeddings_batch
    
    # Create index
    index = create_memory(dimension=384)
    memory_texts = []
    
    # Add some memories
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
    
    # Search test
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


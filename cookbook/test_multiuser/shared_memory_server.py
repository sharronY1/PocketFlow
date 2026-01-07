"""
Shared Memory Server for Multi-Agent System

A centralized FastAPI server that hosts the shared memory (FAISS indices) for distributed agents.
Provides endpoints for:
- Searching entities by visual and description features
- Adding new entities
- Updating existing entities
- Retrieving entity information

Uses dual FAISS indices (visual + description) with configurable fusion weights.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import threading
import numpy as np
import faiss
import uuid
import json
from datetime import datetime

from utils.shared_memory_types import (
    SharedMemoryEntity,
    SharedMemoryConfig,
    NumpyJSONEncoder
)
from utils.config_loader import get_config_value

app = FastAPI(title="Shared Memory Server", version="1.0.0")

# ========== Global State ==========
# Load configuration from config file with defaults
def load_server_config() -> SharedMemoryConfig:
    """Load configuration from config.json shared_memory section."""
    return SharedMemoryConfig(
        visual_feature_dim=get_config_value("shared_memory.visual_feature_dim", 512),
        description_embedding_dim=get_config_value("shared_memory.description_embedding_dim", 384),
        visual_similarity_threshold=get_config_value("shared_memory.visual_similarity_threshold", 0.7),
        description_similarity_threshold=get_config_value("shared_memory.description_similarity_threshold", 0.7),
        same_object_threshold=get_config_value("shared_memory.same_object_threshold", 0.92),
        similarity_fusion_alpha=get_config_value("shared_memory.similarity_fusion_alpha", 0.6),
        feature_aggregation_weight=get_config_value("shared_memory.feature_aggregation_weight", 0.8),
        top_k_search=get_config_value("shared_memory.top_k_search", 10),
        server_host=get_config_value("shared_memory.server_host", "0.0.0.0"),
        server_port=get_config_value("shared_memory.server_port", 8001)
    )

config = load_server_config()

# FAISS indices
visual_index: Optional[faiss.Index] = None  # For visual_features
description_index: Optional[faiss.Index] = None  # For description_embedding

# Entity storage (maps entity_id -> SharedMemoryEntity)
entities: Dict[str, SharedMemoryEntity] = {}

# ID mapping for FAISS indices (FAISS uses sequential integer IDs)
# Maps FAISS index position -> entity_id
visual_id_map: List[str] = []
description_id_map: List[str] = []

# Global lock for thread-safe access
lock = threading.Lock()


# ========== Pydantic Models ==========
class SearchRequest(BaseModel):
    """Request model for searching entities."""
    visual_features: Optional[List[float]] = None
    description_embedding: Optional[List[float]] = None
    top_k: int = 10
    agent_id: str = ""


class SearchResult(BaseModel):
    """Result model for a single search match."""
    entity_id: str
    entity_type: str
    description_text: str
    visual_similarity: float
    description_similarity: float
    combined_score: float
    meta_info: Dict[str, Any]
    inferred_properties: Dict[str, Any]


class SearchResponse(BaseModel):
    """Response model for search results."""
    results: List[SearchResult]
    match_found: bool
    is_same_object: bool  # True if top result exceeds same_object_threshold
    top_entity_id: Optional[str] = None


class AddEntityRequest(BaseModel):
    """Request model for adding a new entity."""
    entity_type: str
    visual_features: Optional[List[float]] = None
    description_embedding: Optional[List[float]] = None
    description_text: str = ""
    discovered_by_agent: str
    current_step: int
    relative_position: str = ""
    region: str = ""
    category_confidence: float = 0.8


class AddEntityResponse(BaseModel):
    """Response model for add entity."""
    entity_id: str
    status: str


class UpdateEntityRequest(BaseModel):
    """Request model for updating an existing entity."""
    entity_id: str
    agent_id: str
    current_step: int
    new_visual_features: Optional[List[float]] = None
    new_description_embedding: Optional[List[float]] = None


class UpdateEntityResponse(BaseModel):
    """Response model for update entity."""
    entity_id: str
    status: str
    visit_count: int
    discovered_by_agents: List[str]


class GetEntityRequest(BaseModel):
    """Request model for getting entity by ID."""
    entity_id: str


class ConfigUpdateRequest(BaseModel):
    """Request model for updating configuration."""
    visual_similarity_threshold: Optional[float] = None
    description_similarity_threshold: Optional[float] = None
    same_object_threshold: Optional[float] = None
    similarity_fusion_alpha: Optional[float] = None
    feature_aggregation_weight: Optional[float] = None
    top_k_search: Optional[int] = None


# ========== Helper Functions ==========
def initialize_indices():
    """Initialize FAISS indices."""
    global visual_index, description_index
    
    # Use IndexFlatIP for cosine similarity (inner product on normalized vectors)
    visual_index = faiss.IndexFlatIP(config.visual_feature_dim)
    description_index = faiss.IndexFlatIP(config.description_embedding_dim)
    
    print(f"[SharedMemory] Initialized FAISS indices:")
    print(f"  - Visual index: {config.visual_feature_dim} dimensions")
    print(f"  - Description index: {config.description_embedding_dim} dimensions")


def compute_combined_score(visual_sim: float, desc_sim: float) -> float:
    """Compute weighted combined similarity score."""
    alpha = config.similarity_fusion_alpha
    return alpha * visual_sim + (1 - alpha) * desc_sim


def search_visual_index(features: np.ndarray, top_k: int) -> List[tuple]:
    """
    Search visual index.
    
    Returns: List of (entity_id, similarity) tuples
    """
    if visual_index is None or visual_index.ntotal == 0:
        return []
    
    features = features.reshape(1, -1).astype('float32')
    k = min(top_k, visual_index.ntotal)
    
    # FAISS IndexFlatIP returns inner product (similarity for normalized vectors)
    similarities, indices = visual_index.search(features, k)
    
    results = []
    for sim, idx in zip(similarities[0], indices[0]):
        if idx >= 0 and idx < len(visual_id_map):
            entity_id = visual_id_map[idx]
            results.append((entity_id, float(sim)))
    
    return results


def search_description_index(features: np.ndarray, top_k: int) -> List[tuple]:
    """
    Search description index.
    
    Returns: List of (entity_id, similarity) tuples
    """
    if description_index is None or description_index.ntotal == 0:
        return []
    
    features = features.reshape(1, -1).astype('float32')
    k = min(top_k, description_index.ntotal)
    
    similarities, indices = description_index.search(features, k)
    
    results = []
    for sim, idx in zip(similarities[0], indices[0]):
        if idx >= 0 and idx < len(description_id_map):
            entity_id = description_id_map[idx]
            results.append((entity_id, float(sim)))
    
    return results


def add_to_visual_index(entity_id: str, features: np.ndarray):
    """Add features to visual index."""
    global visual_index, visual_id_map
    
    features = features.reshape(1, -1).astype('float32')
    visual_index.add(features)
    visual_id_map.append(entity_id)


def add_to_description_index(entity_id: str, features: np.ndarray):
    """Add features to description index."""
    global description_index, description_id_map
    
    features = features.reshape(1, -1).astype('float32')
    description_index.add(features)
    description_id_map.append(entity_id)


# ========== API Endpoints ==========
@app.on_event("startup")
async def startup_event():
    """Initialize indices on server startup."""
    initialize_indices()


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "running",
        "service": "Shared Memory Server",
        "total_entities": len(entities),
        "visual_index_size": visual_index.ntotal if visual_index else 0,
        "description_index_size": description_index.ntotal if description_index else 0,
        "config": config.to_dict()
    }


@app.post("/search", response_model=SearchResponse)
async def search_entities(request: SearchRequest):
    """
    Search for matching entities using dual-index approach.
    
    1. Search both visual and description indices
    2. Compute combined scores using weighted fusion
    3. Return matches above threshold
    """
    with lock:
        visual_results = {}
        desc_results = {}
        
        # Search visual index if features provided
        if request.visual_features:
            visual_features = np.array(request.visual_features, dtype=np.float32)
            for entity_id, sim in search_visual_index(visual_features, request.top_k):
                visual_results[entity_id] = sim
        
        # Search description index if features provided
        if request.description_embedding:
            desc_features = np.array(request.description_embedding, dtype=np.float32)
            for entity_id, sim in search_description_index(desc_features, request.top_k):
                desc_results[entity_id] = sim
        
        # Combine results
        all_entity_ids = set(visual_results.keys()) | set(desc_results.keys())
        combined_results = []
        
        for entity_id in all_entity_ids:
            visual_sim = visual_results.get(entity_id, 0.0)
            desc_sim = desc_results.get(entity_id, 0.0)
            
            # Check thresholds - both must pass (AND condition)
            # But we use combined score for ranking
            visual_pass = visual_sim >= config.visual_similarity_threshold or not request.visual_features
            desc_pass = desc_sim >= config.description_similarity_threshold or not request.description_embedding
            
            if visual_pass and desc_pass:
                combined_score = compute_combined_score(visual_sim, desc_sim)
                entity = entities.get(entity_id)
                
                if entity:
                    combined_results.append({
                        "entity_id": entity_id,
                        "entity_type": entity.entity_type,
                        "description_text": entity.description_text,
                        "visual_similarity": visual_sim,
                        "description_similarity": desc_sim,
                        "combined_score": combined_score,
                        "meta_info": {
                            "created_at": entity.created_at,
                            "last_updated": entity.last_updated,
                            "exploration_priority": entity.exploration_priority,
                            "visit_count": entity.visit_count
                        },
                        "inferred_properties": entity.inferred_properties
                    })
        
        # Sort by combined score
        combined_results.sort(key=lambda x: x["combined_score"], reverse=True)
        
        # Determine match status
        match_found = len(combined_results) > 0
        is_same_object = False
        top_entity_id = None
        
        if match_found:
            top_result = combined_results[0]
            top_entity_id = top_result["entity_id"]
            is_same_object = top_result["combined_score"] >= config.same_object_threshold
        
        return SearchResponse(
            results=[SearchResult(**r) for r in combined_results[:request.top_k]],
            match_found=match_found,
            is_same_object=is_same_object,
            top_entity_id=top_entity_id
        )


@app.post("/entities/add", response_model=AddEntityResponse)
async def add_entity(request: AddEntityRequest):
    """Add a new entity to the shared memory."""
    with lock:
        # Create visual features array if provided
        visual_features = None
        if request.visual_features:
            visual_features = np.array(request.visual_features, dtype=np.float32)
        
        # Create description embedding array if provided
        description_embedding = None
        if request.description_embedding:
            description_embedding = np.array(request.description_embedding, dtype=np.float32)
        
        # Create new entity
        entity = SharedMemoryEntity.create_new(
            entity_type=request.entity_type,
            visual_features=visual_features,
            description_embedding=description_embedding,
            description_text=request.description_text,
            discovered_by_agent=request.discovered_by_agent,
            current_step=request.current_step,
            relative_position=request.relative_position,
            region=request.region,
            category_confidence=request.category_confidence
        )
        
        # Store entity
        entities[entity.entity_id] = entity
        
        # Add to FAISS indices
        if visual_features is not None:
            add_to_visual_index(entity.entity_id, visual_features)
        
        if description_embedding is not None:
            add_to_description_index(entity.entity_id, description_embedding)
        
        print(f"[SharedMemory] Added entity {entity.entity_id} ({entity.entity_type}) by {request.discovered_by_agent}")
        
        return AddEntityResponse(
            entity_id=entity.entity_id,
            status="created"
        )


@app.post("/entities/update", response_model=UpdateEntityResponse)
async def update_entity(request: UpdateEntityRequest):
    """Update an existing entity (called when same object is revisited)."""
    with lock:
        entity = entities.get(request.entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail=f"Entity {request.entity_id} not found")
        
        # Prepare new features
        new_visual = None
        if request.new_visual_features:
            new_visual = np.array(request.new_visual_features, dtype=np.float32)
        
        new_desc = None
        if request.new_description_embedding:
            new_desc = np.array(request.new_description_embedding, dtype=np.float32)
        
        # Update entity
        entity.update_on_revisit(
            agent_id=request.agent_id,
            current_step=request.current_step,
            new_visual_features=new_visual,
            new_description_embedding=new_desc,
            feature_aggregation_weight=config.feature_aggregation_weight
        )
        
        print(f"[SharedMemory] Updated entity {entity.entity_id} by {request.agent_id}, visit_count={entity.visit_count}")
        
        return UpdateEntityResponse(
            entity_id=entity.entity_id,
            status="updated",
            visit_count=entity.visit_count,
            discovered_by_agents=entity.inferred_properties.get("discovered_by_agents", [])
        )


@app.post("/entities/get")
async def get_entity(request: GetEntityRequest):
    """Get entity by ID."""
    with lock:
        entity = entities.get(request.entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail=f"Entity {request.entity_id} not found")
        
        return entity.to_dict()


@app.get("/entities/list")
async def list_entities(limit: int = 100, offset: int = 0):
    """List all entities (paginated)."""
    with lock:
        entity_list = list(entities.values())
        total = len(entity_list)
        
        # Sort by last_updated (most recent first)
        entity_list.sort(key=lambda e: e.last_updated, reverse=True)
        
        # Paginate
        paginated = entity_list[offset:offset + limit]
        
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "entities": [e.get_meta_and_properties() for e in paginated]
        }


@app.get("/entities/by_agent/{agent_id}")
async def get_entities_by_agent(agent_id: str):
    """Get all entities discovered by a specific agent."""
    with lock:
        agent_entities = [
            e.get_meta_and_properties()
            for e in entities.values()
            if agent_id in e.inferred_properties.get("discovered_by_agents", [])
        ]
        
        return {
            "agent_id": agent_id,
            "count": len(agent_entities),
            "entities": agent_entities
        }


@app.post("/config/update")
async def update_config(request: ConfigUpdateRequest):
    """Update server configuration."""
    global config
    
    with lock:
        if request.visual_similarity_threshold is not None:
            config.visual_similarity_threshold = request.visual_similarity_threshold
        if request.description_similarity_threshold is not None:
            config.description_similarity_threshold = request.description_similarity_threshold
        if request.same_object_threshold is not None:
            config.same_object_threshold = request.same_object_threshold
        if request.similarity_fusion_alpha is not None:
            config.similarity_fusion_alpha = request.similarity_fusion_alpha
        if request.feature_aggregation_weight is not None:
            config.feature_aggregation_weight = request.feature_aggregation_weight
        if request.top_k_search is not None:
            config.top_k_search = request.top_k_search
        
        return {"status": "updated", "config": config.to_dict()}


@app.get("/config")
async def get_config():
    """Get current configuration."""
    return config.to_dict()


@app.delete("/reset")
async def reset_memory():
    """Reset all memory (for testing/development)."""
    global entities, visual_id_map, description_id_map
    
    with lock:
        entities.clear()
        visual_id_map.clear()
        description_id_map.clear()
        initialize_indices()
        
        return {"status": "reset", "message": "All memory cleared"}


@app.get("/stats")
async def get_stats():
    """Get memory statistics."""
    with lock:
        # Calculate entity type distribution
        type_counts = {}
        for entity in entities.values():
            t = entity.entity_type
            type_counts[t] = type_counts.get(t, 0) + 1
        
        # Calculate agent discovery stats
        agent_counts = {}
        for entity in entities.values():
            for agent in entity.inferred_properties.get("discovered_by_agents", []):
                agent_counts[agent] = agent_counts.get(agent, 0) + 1
        
        return {
            "total_entities": len(entities),
            "visual_index_size": visual_index.ntotal if visual_index else 0,
            "description_index_size": description_index.ntotal if description_index else 0,
            "entity_types": type_counts,
            "discoveries_by_agent": agent_counts,
            "config": config.to_dict()
        }


if __name__ == "__main__":
    import uvicorn
    import os
    
    # Priority: environment variable > config file > default
    host = os.getenv("HOST", config.server_host)
    port = int(os.getenv("SHARED_MEMORY_PORT", str(config.server_port)))
    
    print(f"Starting Shared Memory Server on {host}:{port}")
    print(f"API docs available at http://{host}:{port}/docs")
    print(f"Configuration: {config.to_dict()}")
    
    uvicorn.run(app, host=host, port=port)


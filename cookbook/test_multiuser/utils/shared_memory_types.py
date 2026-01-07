"""
Shared Memory Entity Types and Data Structures

This module defines the data structures for the distributed shared memory system
that stores discovered objects/entities with multimodal features.
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Set
import numpy as np
import uuid
from datetime import datetime
import json


@dataclass
class SharedMemoryEntity:
    """
    Represents an entity (object/region) in the shared memory.
    
    Contains:
    - Identity: entity_id, entity_type
    - Multimodal features: visual_features (CLIP), description_embedding (text)
    - Spatial info: approximate location and observation context
    - Inferred properties: confidence, discovered_by_agents, tags
    - Meta information: timestamps, priority, visit count
    """
    
    # ========== Identity ==========
    entity_id: str  # UUID
    entity_type: str  # Category: "chest", "door", "npc", "wall", "vegetation", etc.
    
    # ========== Multimodal Features ==========
    # Visual features from CLIP model (typically 512 or 768 dimensions)
    visual_features: Optional[np.ndarray] = None
    # Text description embedding (384 dimensions, from sentence-transformers)
    description_embedding: Optional[np.ndarray] = None
    # Original text description (for debugging and display)
    description_text: str = ""
    
    # ========== Spatial Information ==========
    spatial_info: Dict[str, Any] = field(default_factory=lambda: {
        "region": "",  # Scene region identifier
        "relative_position": "",  # e.g., "front-near", "left-mid"
        "observed_from": []  # List of (agent_id, position) tuples
    })
    
    # ========== Inferred Properties ==========
    inferred_properties: Dict[str, Any] = field(default_factory=lambda: {
        "category_confidence": 0.0,
        "discovered_by_agents": [],  # List of agent IDs
        "tags": []  # e.g., ["interactable", "container", "static"]
    })
    
    # ========== Meta Information ==========
    created_at: int = 0  # Step when first discovered
    last_updated: int = 0  # Step when last seen
    exploration_priority: float = 1.0  # Weight for exploration planning (higher = more interesting)
    visit_count: int = 0  # Total visit count across all agents
    observation_count: int = 0  # Number of times this entity has been observed
    
    @classmethod
    def create_new(
        cls,
        entity_type: str,
        visual_features: Optional[np.ndarray],
        description_embedding: Optional[np.ndarray],
        description_text: str,
        discovered_by_agent: str,
        current_step: int,
        relative_position: str = "",
        region: str = "",
        category_confidence: float = 0.8
    ) -> "SharedMemoryEntity":
        """Factory method to create a new entity with proper initialization."""
        entity_id = str(uuid.uuid4())
        
        return cls(
            entity_id=entity_id,
            entity_type=entity_type,
            visual_features=visual_features,
            description_embedding=description_embedding,
            description_text=description_text,
            spatial_info={
                "region": region,
                "relative_position": relative_position,
                "observed_from": [(discovered_by_agent, current_step)]
            },
            inferred_properties={
                "category_confidence": category_confidence,
                "discovered_by_agents": [discovered_by_agent],
                "tags": []
            },
            created_at=current_step,
            last_updated=current_step,
            exploration_priority=1.0,
            visit_count=1,
            observation_count=1
        )
    
    def update_on_revisit(
        self,
        agent_id: str,
        current_step: int,
        new_visual_features: Optional[np.ndarray] = None,
        new_description_embedding: Optional[np.ndarray] = None,
        feature_aggregation_weight: float = 0.8
    ):
        """
        Update entity when revisited by an agent.
        
        Args:
            agent_id: The agent that observed this entity
            current_step: Current step number
            new_visual_features: New visual features (optional, for aggregation)
            new_description_embedding: New description embedding (optional)
            feature_aggregation_weight: Weight for existing features (0.8 = 80% old + 20% new)
        """
        # Update meta information
        self.last_updated = current_step
        self.visit_count += 1
        self.observation_count += 1
        
        # Add agent to discovered_by_agents if not already present
        if agent_id not in self.inferred_properties["discovered_by_agents"]:
            self.inferred_properties["discovered_by_agents"].append(agent_id)
        
        # Add observation record
        self.spatial_info["observed_from"].append((agent_id, current_step))
        
        # Aggregate visual features using moving average
        if new_visual_features is not None and self.visual_features is not None:
            self.visual_features = (
                feature_aggregation_weight * self.visual_features +
                (1 - feature_aggregation_weight) * new_visual_features
            )
            # Re-normalize
            norm = np.linalg.norm(self.visual_features)
            if norm > 0:
                self.visual_features = self.visual_features / norm
        
        # Aggregate description embedding similarly
        if new_description_embedding is not None and self.description_embedding is not None:
            self.description_embedding = (
                feature_aggregation_weight * self.description_embedding +
                (1 - feature_aggregation_weight) * new_description_embedding
            )
            norm = np.linalg.norm(self.description_embedding)
            if norm > 0:
                self.description_embedding = self.description_embedding / norm
        
        # Decrease exploration priority slightly (already visited)
        self.exploration_priority = max(0.1, self.exploration_priority * 0.95)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "visual_features": self.visual_features.tolist() if self.visual_features is not None else None,
            "description_embedding": self.description_embedding.tolist() if self.description_embedding is not None else None,
            "description_text": self.description_text,
            "spatial_info": self.spatial_info,
            "inferred_properties": self.inferred_properties,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "exploration_priority": self.exploration_priority,
            "visit_count": self.visit_count,
            "observation_count": self.observation_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SharedMemoryEntity":
        """Create entity from dictionary."""
        return cls(
            entity_id=data["entity_id"],
            entity_type=data["entity_type"],
            visual_features=np.array(data["visual_features"]) if data.get("visual_features") else None,
            description_embedding=np.array(data["description_embedding"]) if data.get("description_embedding") else None,
            description_text=data.get("description_text", ""),
            spatial_info=data.get("spatial_info", {}),
            inferred_properties=data.get("inferred_properties", {}),
            created_at=data.get("created_at", 0),
            last_updated=data.get("last_updated", 0),
            exploration_priority=data.get("exploration_priority", 1.0),
            visit_count=data.get("visit_count", 0),
            observation_count=data.get("observation_count", 0)
        )
    
    def get_meta_and_properties(self) -> Dict[str, Any]:
        """Get meta information and inferred properties for retrieval results."""
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "description_text": self.description_text,
            "spatial_info": self.spatial_info,
            "inferred_properties": self.inferred_properties,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "exploration_priority": self.exploration_priority,
            "visit_count": self.visit_count
        }


@dataclass  
class SharedMemoryConfig:
    """Configuration for the shared memory system."""
    
    # Vector dimensions
    visual_feature_dim: int = 512  # CLIP ViT-B/32 dimension
    description_embedding_dim: int = 384  # all-MiniLM-L6-v2 dimension
    
    # Similarity thresholds
    visual_similarity_threshold: float = 0.7  # Minimum visual similarity for match
    description_similarity_threshold: float = 0.7  # Minimum description similarity for match
    same_object_threshold: float = 0.92  # Threshold to consider as same object (vs similar but different)
    
    # Fusion weights
    similarity_fusion_alpha: float = 0.6  # Weight for visual similarity (1-alpha for description)
    
    # Feature aggregation
    feature_aggregation_weight: float = 0.8  # Weight for existing features when aggregating
    
    # Search parameters
    top_k_search: int = 10  # Number of candidates to retrieve from each index
    
    # Server settings
    server_host: str = "0.0.0.0"
    server_port: int = 8001
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SharedMemoryConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class NumpyJSONEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy arrays."""
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        return super().default(obj)


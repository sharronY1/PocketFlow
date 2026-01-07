"""
Shared Memory Client

Client library for agents to interact with the centralized Shared Memory Server.
Provides methods for searching, adding, and updating entities in the shared memory.
"""
import os
import requests
import numpy as np
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

try:
    from .config_loader import get_config_value
except ImportError:
    def get_config_value(key: str, default: Any = None) -> Any:
        return default


@dataclass
class SearchMatch:
    """Represents a matched entity from search results."""
    entity_id: str
    entity_type: str
    description_text: str
    visual_similarity: float
    description_similarity: float
    combined_score: float
    meta_info: Dict[str, Any]
    inferred_properties: Dict[str, Any]


@dataclass
class SearchResult:
    """Result of a shared memory search."""
    matches: List[SearchMatch]
    match_found: bool
    is_same_object: bool
    top_entity_id: Optional[str]


class SharedMemoryClient:
    """
    Client for interacting with the Shared Memory Server.
    
    Usage:
        client = SharedMemoryClient()
        
        # Search for entities
        result = client.search(
            visual_features=clip_features,
            description_embedding=text_embedding
        )
        
        if result.is_same_object:
            # Update existing entity
            client.update_entity(result.top_entity_id, agent_id, step)
        else:
            # Add new entity
            client.add_entity(...)
    """
    
    def __init__(
        self,
        server_url: Optional[str] = None,
        timeout: float = 10.0
    ):
        """
        Initialize the client.
        
        Args:
            server_url: URL of the shared memory server. If not provided,
                        reads from config or defaults to http://localhost:8001
            timeout: Request timeout in seconds
        """
        self.server_url = (
            server_url or 
            get_config_value("shared_memory.server_url") or
            os.getenv("SHARED_MEMORY_SERVER_URL") or
            "http://localhost:8001"
        )
        self.timeout = timeout
        
        # Remove trailing slash
        if self.server_url.endswith("/"):
            self.server_url = self.server_url[:-1]
    
    def _post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make POST request to server."""
        url = f"{self.server_url}{endpoint}"
        try:
            response = requests.post(url, json=data, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"[SharedMemoryClient] Error in POST {endpoint}: {e}")
            raise
    
    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make GET request to server."""
        url = f"{self.server_url}{endpoint}"
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"[SharedMemoryClient] Error in GET {endpoint}: {e}")
            raise
    
    def is_available(self) -> bool:
        """Check if the shared memory server is available."""
        try:
            response = self._get("/")
            return response.get("status") == "running"
        except Exception:
            return False
    
    def search(
        self,
        visual_features: Optional[np.ndarray] = None,
        description_embedding: Optional[np.ndarray] = None,
        top_k: int = 10,
        agent_id: str = ""
    ) -> SearchResult:
        """
        Search for matching entities in shared memory.
        
        Args:
            visual_features: CLIP visual features (512-dim)
            description_embedding: Text description embedding (384-dim)
            top_k: Maximum number of results to return
            agent_id: ID of the searching agent
        
        Returns:
            SearchResult with matches and match status
        """
        data = {
            "top_k": top_k,
            "agent_id": agent_id
        }
        
        if visual_features is not None:
            data["visual_features"] = visual_features.tolist()
        
        if description_embedding is not None:
            data["description_embedding"] = description_embedding.tolist()
        
        try:
            response = self._post("/search", data)
            
            matches = [
                SearchMatch(
                    entity_id=r["entity_id"],
                    entity_type=r["entity_type"],
                    description_text=r["description_text"],
                    visual_similarity=r["visual_similarity"],
                    description_similarity=r["description_similarity"],
                    combined_score=r["combined_score"],
                    meta_info=r["meta_info"],
                    inferred_properties=r["inferred_properties"]
                )
                for r in response.get("results", [])
            ]
            
            return SearchResult(
                matches=matches,
                match_found=response.get("match_found", False),
                is_same_object=response.get("is_same_object", False),
                top_entity_id=response.get("top_entity_id")
            )
        except Exception as e:
            print(f"[SharedMemoryClient] Search failed: {e}")
            return SearchResult(
                matches=[],
                match_found=False,
                is_same_object=False,
                top_entity_id=None
            )
    
    def add_entity(
        self,
        entity_type: str,
        visual_features: Optional[np.ndarray] = None,
        description_embedding: Optional[np.ndarray] = None,
        description_text: str = "",
        discovered_by_agent: str = "",
        current_step: int = 0,
        relative_position: str = "",
        region: str = "",
        category_confidence: float = 0.8
    ) -> Optional[str]:
        """
        Add a new entity to shared memory.
        
        Args:
            entity_type: Type/category of the entity
            visual_features: CLIP visual features
            description_embedding: Text embedding
            description_text: Original text description
            discovered_by_agent: ID of the discovering agent
            current_step: Current step number
            relative_position: Position relative to observer
            region: Scene region identifier
            category_confidence: Confidence in the entity type
        
        Returns:
            entity_id of the created entity, or None if failed
        """
        data = {
            "entity_type": entity_type,
            "description_text": description_text,
            "discovered_by_agent": discovered_by_agent,
            "current_step": current_step,
            "relative_position": relative_position,
            "region": region,
            "category_confidence": category_confidence
        }
        
        if visual_features is not None:
            data["visual_features"] = visual_features.tolist()
        
        if description_embedding is not None:
            data["description_embedding"] = description_embedding.tolist()
        
        try:
            response = self._post("/entities/add", data)
            return response.get("entity_id")
        except Exception as e:
            print(f"[SharedMemoryClient] Add entity failed: {e}")
            return None
    
    def update_entity(
        self,
        entity_id: str,
        agent_id: str,
        current_step: int,
        new_visual_features: Optional[np.ndarray] = None,
        new_description_embedding: Optional[np.ndarray] = None
    ) -> bool:
        """
        Update an existing entity (called when revisiting).
        
        Args:
            entity_id: ID of the entity to update
            agent_id: ID of the agent making the update
            current_step: Current step number
            new_visual_features: New visual features (optional, for aggregation)
            new_description_embedding: New description embedding (optional)
        
        Returns:
            True if update was successful
        """
        data = {
            "entity_id": entity_id,
            "agent_id": agent_id,
            "current_step": current_step
        }
        
        if new_visual_features is not None:
            data["new_visual_features"] = new_visual_features.tolist()
        
        if new_description_embedding is not None:
            data["new_description_embedding"] = new_description_embedding.tolist()
        
        try:
            response = self._post("/entities/update", data)
            return response.get("status") == "updated"
        except Exception as e:
            print(f"[SharedMemoryClient] Update entity failed: {e}")
            return False
    
    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get entity by ID."""
        try:
            response = self._post("/entities/get", {"entity_id": entity_id})
            return response
        except Exception as e:
            print(f"[SharedMemoryClient] Get entity failed: {e}")
            return None
    
    def list_entities(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List all entities (paginated)."""
        try:
            response = self._get("/entities/list", {"limit": limit, "offset": offset})
            return response.get("entities", [])
        except Exception as e:
            print(f"[SharedMemoryClient] List entities failed: {e}")
            return []
    
    def get_entities_by_agent(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get all entities discovered by a specific agent."""
        try:
            response = self._get(f"/entities/by_agent/{agent_id}")
            return response.get("entities", [])
        except Exception as e:
            print(f"[SharedMemoryClient] Get entities by agent failed: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        try:
            return self._get("/stats")
        except Exception as e:
            print(f"[SharedMemoryClient] Get stats failed: {e}")
            return {}
    
    def update_config(
        self,
        visual_similarity_threshold: Optional[float] = None,
        description_similarity_threshold: Optional[float] = None,
        same_object_threshold: Optional[float] = None,
        similarity_fusion_alpha: Optional[float] = None,
        feature_aggregation_weight: Optional[float] = None,
        top_k_search: Optional[int] = None
    ) -> bool:
        """Update server configuration."""
        data = {}
        if visual_similarity_threshold is not None:
            data["visual_similarity_threshold"] = visual_similarity_threshold
        if description_similarity_threshold is not None:
            data["description_similarity_threshold"] = description_similarity_threshold
        if same_object_threshold is not None:
            data["same_object_threshold"] = same_object_threshold
        if similarity_fusion_alpha is not None:
            data["similarity_fusion_alpha"] = similarity_fusion_alpha
        if feature_aggregation_weight is not None:
            data["feature_aggregation_weight"] = feature_aggregation_weight
        if top_k_search is not None:
            data["top_k_search"] = top_k_search
        
        try:
            response = self._post("/config/update", data)
            return response.get("status") == "updated"
        except Exception as e:
            print(f"[SharedMemoryClient] Update config failed: {e}")
            return False
    
    def reset(self) -> bool:
        """Reset all shared memory (for testing)."""
        try:
            response = requests.delete(f"{self.server_url}/reset", timeout=self.timeout)
            response.raise_for_status()
            return response.json().get("status") == "reset"
        except Exception as e:
            print(f"[SharedMemoryClient] Reset failed: {e}")
            return False


def get_shared_memory_client(server_url: Optional[str] = None) -> SharedMemoryClient:
    """
    Factory function to get a SharedMemoryClient instance.
    
    Reads server URL from config if not provided.
    """
    return SharedMemoryClient(server_url=server_url)


# ========== High-Level Helper Functions ==========
def search_and_update_or_add(
    client: SharedMemoryClient,
    entity_type: str,
    visual_features: Optional[np.ndarray],
    description_embedding: Optional[np.ndarray],
    description_text: str,
    agent_id: str,
    current_step: int,
    relative_position: str = "",
    region: str = ""
) -> Tuple[str, bool, Optional[Dict[str, Any]]]:
    """
    High-level function implementing the retrieve-match-update/add flow.
    
    Flow:
    1. Search shared memory with features
    2. If same object found -> update entity
    3. If different object or not found -> add new entity
    
    Args:
        client: SharedMemoryClient instance
        entity_type: Type of the observed entity
        visual_features: CLIP visual features
        description_embedding: Text embedding
        description_text: Original description
        agent_id: ID of the agent
        current_step: Current step number
        relative_position: Position relative to observer
        region: Scene region
    
    Returns:
        Tuple of (entity_id, is_existing, retrieved_info)
        - entity_id: ID of the matched/created entity
        - is_existing: True if matched existing entity
        - retrieved_info: Meta info and properties if matched, None if new
    """
    # Search for matching entities
    search_result = client.search(
        visual_features=visual_features,
        description_embedding=description_embedding,
        agent_id=agent_id
    )
    
    if search_result.is_same_object and search_result.top_entity_id:
        # Same object found -> Update
        entity_id = search_result.top_entity_id
        client.update_entity(
            entity_id=entity_id,
            agent_id=agent_id,
            current_step=current_step,
            new_visual_features=visual_features,
            new_description_embedding=description_embedding
        )
        
        # Get the matched entity's info
        top_match = search_result.matches[0] if search_result.matches else None
        retrieved_info = None
        if top_match:
            retrieved_info = {
                "entity_id": top_match.entity_id,
                "entity_type": top_match.entity_type,
                "description_text": top_match.description_text,
                "visual_similarity": top_match.visual_similarity,
                "description_similarity": top_match.description_similarity,
                "combined_score": top_match.combined_score,
                **top_match.meta_info,
                **top_match.inferred_properties
            }
        
        return entity_id, True, retrieved_info
    
    else:
        # Not found or different object -> Add new
        entity_id = client.add_entity(
            entity_type=entity_type,
            visual_features=visual_features,
            description_embedding=description_embedding,
            description_text=description_text,
            discovered_by_agent=agent_id,
            current_step=current_step,
            relative_position=relative_position,
            region=region
        )
        
        return entity_id, False, None


if __name__ == "__main__":
    # Test the client
    print("Testing SharedMemoryClient...")
    
    client = SharedMemoryClient()
    
    if client.is_available():
        print("Server is available!")
        
        # Get stats
        stats = client.get_stats()
        print(f"Stats: {stats}")
        
        # Test adding an entity
        fake_visual = np.random.randn(512).astype(np.float32)
        fake_visual = fake_visual / np.linalg.norm(fake_visual)
        
        fake_desc = np.random.randn(384).astype(np.float32)
        fake_desc = fake_desc / np.linalg.norm(fake_desc)
        
        entity_id = client.add_entity(
            entity_type="test_object",
            visual_features=fake_visual,
            description_embedding=fake_desc,
            description_text="A test object for debugging",
            discovered_by_agent="test_agent",
            current_step=1
        )
        
        if entity_id:
            print(f"Added entity: {entity_id}")
            
            # Test search
            result = client.search(
                visual_features=fake_visual,
                description_embedding=fake_desc
            )
            print(f"Search result: match_found={result.match_found}, is_same={result.is_same_object}")
            
            if result.matches:
                print(f"Top match: {result.matches[0].entity_id}")
    else:
        print("Server is not available. Start the server with:")
        print("  python shared_memory_server.py")


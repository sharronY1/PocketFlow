"""
Utility functions for multi-agent exploration
"""
from .call_llm import call_llm
from .embedding import get_embedding, get_embeddings_batch
from .environment import (
    create_environment,
    add_message,
    get_messages_for
)
from .perception_interface import (
    PerceptionInterface,
    MockPerception,
    XRPerception,
    create_perception
)
from .config_loader import (
    load_config,
    get_config_value,
    sync_unity_config
)
# Shared memory system
from .clip_features import (
    extract_visual_features,
    extract_visual_features_batch,
    compute_visual_similarity,
    get_clip_dimension
)
from .shared_memory_client import (
    SharedMemoryClient,
    get_shared_memory_client,
    search_and_update_or_add,
    SearchResult,
    SearchMatch
)
from .shared_memory_types import (
    SharedMemoryEntity,
    SharedMemoryConfig
)

__all__ = [
    'call_llm',
    'get_embedding',
    'get_embeddings_batch',
    'create_environment',
    'add_message',
    'get_messages_for',
    'PerceptionInterface',
    'MockPerception',
    'XRPerception',
    'create_perception',
    'load_config',
    'get_config_value',
    'sync_unity_config',
    # Shared memory system
    'extract_visual_features',
    'extract_visual_features_batch',
    'compute_visual_similarity',
    'get_clip_dimension',
    'SharedMemoryClient',
    'get_shared_memory_client',
    'search_and_update_or_add',
    'SearchResult',
    'SearchMatch',
    'SharedMemoryEntity',
    'SharedMemoryConfig',
]

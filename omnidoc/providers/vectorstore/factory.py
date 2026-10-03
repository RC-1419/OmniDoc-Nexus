from functools import lru_cache

from omnidoc.core.config import get_settings
from omnidoc.providers.vectorstore.base import VectorStore
from omnidoc.providers.vectorstore.pinecone_store import PineconeStore


@lru_cache
def get_vector_store() -> VectorStore:
    s = get_settings()
    return PineconeStore(s.pinecone_api_key, s.pinecone_index, s.embedding_dim,
                         s.pinecone_region, s.pinecone_namespace_mode)

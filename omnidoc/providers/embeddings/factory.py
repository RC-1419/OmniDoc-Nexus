from functools import lru_cache

from omnidoc.core.config import get_settings
from omnidoc.providers.embeddings.base import Embedder
from omnidoc.providers.embeddings.fastembed_embedder import FastEmbedder


@lru_cache
def get_embedder() -> Embedder:
    return FastEmbedder(get_settings().embedding_model)

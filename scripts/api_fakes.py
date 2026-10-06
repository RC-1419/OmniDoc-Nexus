"""In-memory stand-ins used only by scripts/try_api.py, so the API test needs no model download and no Pinecone."""
import hashlib
import math
import re

from omnidoc.providers.embeddings.base import Embedder
from omnidoc.providers.vectorstore.base import Match, VectorItem, VectorStore

DIM = 64


def _vector(text: str) -> list[float]:
    v = [0.0] * DIM
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        v[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM] += 1.0
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


class FakeEmbedder(Embedder):
    def embed_documents(self, texts):
        return [_vector(t) for t in texts]

    def embed_query(self, text):
        return _vector(text)


class FakeVectorStore(VectorStore):
    """Behaves like the real store: every query is limited to the caller's user_id, plus any filters."""

    def __init__(self):
        self.items: dict[str, tuple[list[float], dict]] = {}

    def upsert(self, user_id, items: list[VectorItem]):
        for item in items:
            meta = {k: v for k, v in item.metadata.items() if v is not None}
            meta["user_id"] = int(user_id)
            self.items[item.id] = (item.vector, meta)

    def query(self, user_id, vector, top_k=5, filters=None):
        wanted = {k: v for k, v in (filters or {}).items() if v is not None}
        wanted["user_id"] = int(user_id)
        scored = [(sum(a * b for a, b in zip(vector, vec)), item_id, meta)
                  for item_id, (vec, meta) in self.items.items()
                  if all(meta.get(k) == v for k, v in wanted.items())]
        scored.sort(key=lambda s: (-s[0], s[1]))
        return [Match(item_id, score, meta) for score, item_id, meta in scored[:top_k]]

    def delete(self, user_id, ids):
        for item_id in ids:
            entry = self.items.get(item_id)
            if entry and entry[1]["user_id"] == int(user_id):
                del self.items[item_id]

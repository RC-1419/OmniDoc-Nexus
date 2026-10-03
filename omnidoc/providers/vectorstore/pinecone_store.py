from omnidoc.providers.vectorstore.base import Match, VectorItem, VectorStore


def namespace_for(mode: str, user_id: int) -> str:
    return f"user-{int(user_id)}" if mode == "user" else "shared"


def build_filter(user_id: int, filters: dict | None) -> dict:
    flt = {k: {"$eq": v} for k, v in (filters or {}).items() if v is not None}
    # set last, so a caller can never override it
    flt["user_id"] = {"$eq": int(user_id)}
    return flt


def build_metadata(user_id: int, metadata: dict | None) -> dict:
    meta = {k: v for k, v in (metadata or {}).items() if v is not None}
    # always stamped by the store, never trusted from the caller
    meta["user_id"] = int(user_id)
    return meta


class PineconeStore(VectorStore):
    """Stores only vectors, ids and small filter fields. Document text stays encrypted in Postgres.

    namespace_mode "shared": one namespace, every query filtered by user_id (works on the free plan).
    namespace_mode "user":   one namespace per user (strongest separation; needs a plan with enough namespaces).
    """

    def __init__(self, api_key: str, index_name: str, dim: int, region: str, namespace_mode: str = "shared"):
        if not api_key:
            raise RuntimeError("PINECONE_API_KEY is not set in .env")
        from pinecone import Pinecone, ServerlessSpec

        pc = Pinecone(api_key=api_key)
        if index_name not in pc.list_indexes().names():
            pc.create_index(name=index_name, dimension=dim, metric="cosine",
                            spec=ServerlessSpec(cloud="aws", region=region))
        existing = pc.describe_index(index_name).dimension
        if existing != dim:
            raise RuntimeError(
                f"Index '{index_name}' has dimension {existing}, but the embedding model needs {dim}")
        self.index = pc.Index(index_name)
        self.mode = namespace_mode

    def upsert(self, user_id, items):
        ns = namespace_for(self.mode, user_id)
        # Pinecone recommends at most 100 vectors per request
        for i in range(0, len(items), 100):
            batch = [{"id": it.id, "values": it.vector, "metadata": build_metadata(user_id, it.metadata)}
                     for it in items[i:i + 100]]
            self.index.upsert(vectors=batch, namespace=ns)

    def query(self, user_id, vector, top_k=5, filters=None):
        res = self.index.query(vector=vector, top_k=top_k, namespace=namespace_for(self.mode, user_id),
                               filter=build_filter(user_id, filters), include_metadata=True)
        return [Match(m.id, m.score, dict(m.metadata or {})) for m in res.matches]

    def delete(self, user_id, ids):
        ns = namespace_for(self.mode, user_id)
        for i in range(0, len(ids), 1000):  # Pinecone allows at most 1000 ids per delete
            self.index.delete(ids=ids[i:i + 1000], namespace=ns)

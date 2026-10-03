import uuid
from dataclasses import dataclass

from sqlalchemy import select

from omnidoc.core import crypto
from omnidoc.db.models import Chunk
from omnidoc.providers.embeddings.base import Embedder
from omnidoc.providers.vectorstore.base import VectorItem, VectorStore


@dataclass
class Hit:
    chunk_id: str
    document_id: int
    doc_type: str | None
    person_id: int | None
    score: float
    text: str


def index_chunks(db, *, user_id: int, document_id: int, person_id: int, doc_type: str,
                 chunks: list[str], embedder: Embedder, store: VectorStore) -> int:
    """Encrypt each chunk into Postgres and put its vector in the vector store."""
    if not chunks:
        return 0
    rows = [Chunk(id=uuid.uuid4().hex, user_id=user_id, document_id=document_id,
                  text_enc=crypto.encrypt_text(user_id, text)) for text in chunks]
    vectors = embedder.embed_documents(chunks)
    meta = {"document_id": document_id,
            "person_id": person_id, "doc_type": doc_type}
    try:
        db.add_all(rows)
        db.flush()
        store.upsert(user_id, [VectorItem(r.id, v, dict(meta))
                     for r, v in zip(rows, vectors)])
        db.commit()
    except Exception:
        db.rollback()  # leftover vectors without a row are ignored by search()
        raise
    return len(rows)


def search(db, *, user_id: int, query: str, embedder: Embedder, store: VectorStore,
           top_k: int = 5, filters: dict | None = None) -> list[Hit]:
    """Find the user's own chunks. Isolation is enforced twice: the vector search is filtered
    by user_id, and the text lookup in Postgres is filtered by user_id again."""
    matches = store.query(user_id, embedder.embed_query(query), top_k, filters)
    if not matches:
        return []
    rows = db.scalars(select(Chunk).where(Chunk.user_id == user_id,
                                          Chunk.id.in_([m.id for m in matches]))).all()
    by_id = {r.id: r for r in rows}
    hits = []
    for m in matches:
        row = by_id.get(m.id)
        if row is None:  # not this user's chunk, or an orphan vector: drop it silently
            continue
        hits.append(Hit(m.id, row.document_id, m.metadata.get("doc_type"), m.metadata.get("person_id"),
                        m.score, crypto.decrypt_text(user_id, row.text_enc)))
    return hits

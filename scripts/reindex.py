"""Rebuild the search index (Pinecone) from the database.

Use it when the index was lost or emptied, you switched to a new index, or you changed the embedding model.
It never changes the database. For every stored chunk it decrypts the text, makes a fresh vector and writes it
to the vector store under the SAME chunk id, so running it twice is harmless.

  python -m scripts.reindex --dry-run          # show what would be done, change nothing
  python -m scripts.reindex                    # everyone
  python -m scripts.reindex --user 3           # one account only

On the server:  docker compose exec api python -m scripts.reindex --dry-run

If you changed the embedding model to one with a different vector size (EMBEDDING_DIM), point PINECONE_INDEX at a
NEW empty index first: an existing index cannot change its size. Old vectors that no longer have a database row
are ignored by search, so they do no harm; delete the old index in the Pinecone console when you are done.
"""
import argparse
import sys

from sqlalchemy import select

from omnidoc.core import crypto
from omnidoc.db.models import Chunk, Document
from omnidoc.db.session import SessionLocal
from omnidoc.providers.embeddings.factory import get_embedder
from omnidoc.providers.vectorstore.base import VectorItem
from omnidoc.providers.vectorstore.factory import get_vector_store

BATCH = 64  # chunks embedded and written per round (keeps memory small)


def user_ids(db, only: int | None) -> list[int]:
    ids = sorted(set(db.scalars(select(Chunk.user_id))))
    return [only] if only is not None and only in ids else ([] if only is not None else ids)


def reindex_user(db, user_id: int, embedder, store, dry_run: bool) -> tuple[int, int]:
    """Returns (chunks written, chunks skipped)."""
    # What the vector store keeps next to each vector (never any text): the document, person and type.
    docs = {d.id: d for d in db.scalars(
        select(Document).where(Document.user_id == user_id))}
    rows = list(db.scalars(select(Chunk).where(
        Chunk.user_id == user_id).order_by(Chunk.id)))
    done = skipped = 0
    for i in range(0, len(rows), BATCH):
        part = rows[i:i + BATCH]
        texts, items_meta = [], []
        for r in part:
            doc = docs.get(r.document_id)
            if doc is None:  # chunk without a document of this user: leave it out
                skipped += 1
                continue
            try:
                texts.append(crypto.decrypt_text(user_id, r.text_enc))
            except Exception:  # wrong or missing key for this row: report it, keep going
                skipped += 1
                continue
            items_meta.append(
                (r.id, {"document_id": doc.id, "person_id": doc.person_id, "doc_type": doc.doc_type}))
        if not texts or dry_run:
            done += len(texts)
            continue
        vectors = embedder.embed_documents(texts)
        store.upsert(user_id, [VectorItem(cid, vec, meta)
                     for (cid, meta), vec in zip(items_meta, vectors)])
        done += len(texts)
    return done, skipped


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Rebuild the search index from the database.")
    ap.add_argument("--user", type=int, help="only this account id")
    ap.add_argument("--dry-run", action="store_true",
                    help="count only; embed and write nothing")
    args = ap.parse_args()

    embedder = None if args.dry_run else get_embedder()
    # also checks the index size matches the model
    store = None if args.dry_run else get_vector_store()
    total = total_skipped = 0
    with SessionLocal() as db:
        ids = user_ids(db, args.user)
        if not ids:
            print(
                "Nothing to index." if args.user is None else f"Account {args.user} has no stored chunks.")
            return 0
        for uid in ids:
            n, s = reindex_user(db, uid, embedder, store, args.dry_run)
            total += n
            total_skipped += s
            print(f"account {uid}: {n} chunks {'counted' if args.dry_run else 'indexed'}"
                  + (f", {s} skipped" if s else ""))
    print(f"{'DRY RUN - nothing written. ' if args.dry_run else ''}"
          f"Total: {total} chunks, {total_skipped} skipped, {len(ids)} account(s).")
    return 1 if total_skipped else 0


if __name__ == "__main__":
    sys.exit(main())

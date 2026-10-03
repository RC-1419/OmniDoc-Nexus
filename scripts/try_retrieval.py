import time
import uuid

from sqlalchemy import delete, select

from omnidoc.core import crypto
from omnidoc.db.models import Chunk, Document, Person, User
from omnidoc.db.session import SessionLocal, init_db
from omnidoc.providers.embeddings.factory import get_embedder
from omnidoc.providers.vectorstore.factory import get_vector_store
from omnidoc.services.auth import register_user
from omnidoc.services.retrieval import index_chunks, search

init_db()
embedder, store = get_embedder(), get_vector_store()
tag = uuid.uuid4().hex[:6]
created_users = []


def make_user(db, name):
    user = register_user(db, f"test_{name}_{tag}", "TestPass12345")
    created_users.append(user.id)
    return user, db.scalar(select(Person).where(Person.user_id == user.id))


def add_doc(db, user, person, doc_type, chunks):
    doc = Document(user_id=user.id, person_id=person.id, doc_type=doc_type,
                   filename="fake", mime="text/plain", storage_key="0" * 32)
    db.add(doc)
    db.flush()
    index_chunks(db, user_id=user.id, document_id=doc.id, person_id=person.id, doc_type=doc_type,
                 chunks=chunks, embedder=embedder, store=store)


def ask(user, question, filters=None, wait=False):
    """Pinecone is eventually consistent: new vectors can take a few seconds to appear."""
    end = time.time() + (60 if wait else 0)
    while True:
        with SessionLocal() as db:
            hits = search(db, user_id=user.id, query=question,
                          embedder=embedder, store=store, filters=filters)
        if hits or time.time() >= end:
            return hits
        time.sleep(3)


try:
    with SessionLocal() as db:
        alice, alice_p = make_user(db, "alice")
        bob, bob_p = make_user(db, "bob")
        add_doc(db, alice, alice_p, "aadhaar", [
                "Aadhaar card. Name Alice Sharma. Aadhaar number 2345 6789 0123. Address Lucknow."])
        add_doc(db, alice, alice_p, "bill", [
                "Electricity bill for March. Amount due 1450 rupees. Consumer number 998877."])
        add_doc(db, bob, bob_p, "pan", [
                "PAN card. Permanent Account Number ABCPE1234F. Name Bob Verma. Date of birth 12/05/1990."])
    print("indexed fake documents for two throwaway users")

    hits = ask(alice, "What is my Aadhaar number?", wait=True)
    assert hits, "no results after 60s: check PINECONE_API_KEY, index name and region"
    assert hits[0].doc_type == "aadhaar" and "Aadhaar" in hits[0].text, hits[0]
    print("1. semantic search ranks the right document first OK")

    hits = ask(alice, "Bob Verma PAN number ABCPE1234F")
    assert all("Bob" not in h.text and "ABCPE" not in h.text for h in hits)
    print("2. Alice cannot find Bob's document OK")

    ask(bob, "PAN number", wait=True)
    hits = ask(bob, "Alice Sharma Aadhaar number 2345 6789 0123")
    assert all("Alice" not in h.text and "Aadhaar" not in h.text for h in hits)
    print("3. Bob cannot find Alice's document OK")

    hits = ask(alice, "amount due", filters={"doc_type": "bill"})
    assert hits and all(h.doc_type == "bill" for h in hits)
    print("4. filtering by document type OK")

    with SessionLocal() as db:
        bob_ids = [c.id for c in db.scalars(
            select(Chunk).where(Chunk.user_id == bob.id))]
        assert bob_ids and db.scalars(select(Chunk).where(
            Chunk.user_id == alice.id, Chunk.id.in_(bob_ids))).all() == []
        row = db.scalar(select(Chunk).where(Chunk.user_id == bob.id))
        assert "ABCPE" not in row.text_enc and "PAN" not in row.text_enc
        try:
            crypto.decrypt_text(alice.id, row.text_enc)
            raise SystemExit("LEAK: Alice's key opened Bob's text")
        except crypto.InvalidToken:
            pass
    print("5. database guard, encrypted text and per-user keys OK")
finally:
    with SessionLocal() as db:
        ids = {uid: [c.id for c in db.scalars(select(Chunk).where(
            Chunk.user_id == uid))] for uid in created_users}
        for uid, chunk_ids in ids.items():
            if chunk_ids:
                store.delete(uid, chunk_ids)
        if created_users:
            db.execute(delete(User).where(User.id.in_(created_users)))
            db.commit()
    print("cleaned up test users and vectors")

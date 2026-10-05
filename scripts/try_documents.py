import shutil
import time
import uuid
from pathlib import Path

from sqlalchemy import delete, select

from omnidoc.core.config import get_settings
from omnidoc.db.models import Chunk, Document, User
from omnidoc.db.session import SessionLocal, init_db
from omnidoc.ingestion.extract import UnsupportedFileType
from omnidoc.ingestion.fields import verhoeff_check_digit
from omnidoc.providers.embeddings.factory import get_embedder
from omnidoc.providers.storage.factory import get_file_store
from omnidoc.providers.vectorstore.factory import get_vector_store
from omnidoc.services import documents as docs
from omnidoc.services.auth import register_user
from omnidoc.services.errors import NotFound
from omnidoc.services.people import add_person
from omnidoc.services.retrieval import search

init_db()
files, embedder, store = get_file_store(), get_embedder(), get_vector_store()
vault = Path(get_settings().vault_dir)
tag = uuid.uuid4().hex[:6]
created = []


def make_pdf(lines):
    """A tiny PDF with a real text layer, so this test needs no scanner or OCR for the text cases."""
    content = "BT /F1 12 Tf 50 750 Td 14 TL " + \
        " ".join(f"({l}) Tj T*" for l in lines) + " ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    return out + f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()


def fake_aadhaar(tail):
    base = "2" + tail  # 11 digits
    n = base + verhoeff_check_digit(base)
    return f"{n[:4]} {n[4:8]} {n[8:]}"


def aadhaar_pdf(number, name="Test Person"):
    return make_pdf(["Government of India", f"Aadhaar number {number}", f"Name {name} Address Lucknow Uttar Pradesh"])


def pan_pdf(name):
    return make_pdf(["INCOME TAX DEPARTMENT", "Permanent Account Number ABCPE1234F", f"Name {name}"])


def add(db, user, filename, data, **kw):
    return docs.add_document(db, user_id=user.id, filename=filename, data=data, files=files,
                             embedder=embedder, store=store, **kw)


def expect_not_found(label, fn):
    try:
        fn()
    except NotFound:
        return
    raise SystemExit(f"LEAK: {label} was allowed")


def ask(user, question):
    """Pinecone is eventually consistent: new vectors can take a few seconds to appear."""
    end = time.time() + 60
    while True:
        with SessionLocal() as db:
            hits = search(db, user_id=user.id, query=question,
                          embedder=embedder, store=store)
        if hits or time.time() > end:
            return hits
        time.sleep(3)


try:
    with SessionLocal() as db:
        alice = register_user(db, f"test_alice_{tag}", "TestPass12345")
        bob = register_user(db, f"test_bob_{tag}", "TestPass12345")
        created += [alice.id, bob.id]

        n1, n2 = fake_aadhaar("3456789012"), fake_aadhaar("9876543210")
        pdf1 = aadhaar_pdf(n1)
        r1 = add(db, alice, "aadhaar.pdf", pdf1)
        assert r1.doc_type == "aadhaar" and r1.fields_found == [
            "aadhaar_number"] and not r1.warnings, r1
        print("1. upload is read, classified as aadhaar, number found OK")

        assert docs.get_fields(db, alice.id, r1.document_id) == {
            "aadhaar_number": n1}
        doc, data = docs.read_file(db, alice.id, r1.document_id, files)
        assert data == pdf1
        raw = next((vault / f"user-{alice.id}").glob("*.bin")).read_bytes()
        assert b"Aadhaar" not in raw and b"%PDF" not in raw
        stored = db.scalar(select(Document.fields_enc).where(
            Document.id == r1.document_id))
        assert n1.replace(
            " ", "") not in stored and "aadhaar" not in stored.lower()
        print("2. number returned from the database, file returned intact, both encrypted at rest OK")

        old_key = doc.storage_key
        r2 = add(db, alice, "aadhaar_new.pdf", aadhaar_pdf(n2))
        assert r2.replaced == 1 and [
            d.doc_type for d in docs.list_documents(db, alice.id)] == ["aadhaar"]
        assert docs.get_fields(db, alice.id, r2.document_id) == {
            "aadhaar_number": n2}
        try:
            files.load(alice.id, old_key)
            raise SystemExit("old file still exists")
        except FileNotFoundError:
            pass
        print("3. uploading again replaces the old document and removes its file OK")

        mum = add_person(db, alice.id, "Test Mum", "mother")
        r3 = add(db, alice, "mum_pan.pdf", pan_pdf(
            "Test Mum"), person_id=mum.id)
        assert r3.doc_type == "pan" and len(
            docs.list_documents(db, alice.id)) == 2
        assert docs.find_documents(db, alice.id, person_id=mum.id, doc_type="PAN card")[
            0].id == r3.document_id
        print("4. a family member's document is stored under that person OK")

        r_bob = add(db, bob, "bob_pan.pdf", pan_pdf("Test Bob"))
        expect_not_found("Bob reading Alice's file", lambda: docs.read_file(
            db, bob.id, r2.document_id, files))
        expect_not_found("Bob reading Alice's numbers",
                         lambda: docs.get_fields(db, bob.id, r2.document_id))
        expect_not_found("Bob editing Alice's numbers", lambda: docs.set_field(
            db, bob.id, r2.document_id, "aadhaar_number", n1))
        expect_not_found("Bob deleting Alice's document", lambda: docs.delete_document(
            db, bob.id, r2.document_id, files, store))
        expect_not_found("Bob filing a document under Alice's family member", lambda: add(
            db, bob, "x.pdf", pan_pdf("x"), person_id=mum.id))
        assert [d.id for d in docs.list_documents(db, bob.id)] == [
            r_bob.document_id]
        assert docs.find_documents(db, bob.id, doc_type="aadhaar") == []
        print("5. Bob cannot read, change, delete or list anything of Alice's OK")

        alice_ids = {r2.document_id, r3.document_id}
        hits = ask(alice, "Aadhaar number")
        assert hits and hits[0].document_id == r2.document_id and all(
            h.document_id in alice_ids for h in hits)
        bob_hits = ask(bob, "Aadhaar number address Lucknow")
        assert all(h.document_id == r_bob.document_id for h in bob_hits)
        print("6. search returns each user's own documents only OK")

        r4 = add(db, alice, "blank.pdf", make_pdf([]), doc_type="pan")
        assert r4.warnings and "No readable text" in r4.warnings[0], r4
        try:
            docs.set_field(db, alice.id, r4.document_id,
                           "pan_number", "NOT-A-PAN")
            raise SystemExit("accepted a bad PAN")
        except ValueError:
            pass
        docs.set_field(db, alice.id, r4.document_id,
                       "pan_number", "abcpe1234f")
        assert docs.get_fields(db, alice.id, r4.document_id) == {
            "pan_number": "ABCPE1234F"}
        print("7. unreadable file is stored with a warning, and a number can be typed in (validated) OK")

        try:
            add(db, alice, "notes.txt", b"just some text")
            raise SystemExit("accepted a .txt file")
        except UnsupportedFileType:
            pass
        print("8. unsupported file types are rejected OK")

        key4 = docs._owned_document(db, alice.id, r4.document_id).storage_key
        docs.delete_document(db, alice.id, r4.document_id, files, store)
        assert not (vault / f"user-{alice.id}" / f"{key4}.bin").exists()
        assert db.scalars(select(Chunk).where(
            Chunk.document_id == r4.document_id)).first() is None
        assert r4.document_id not in [
            d.id for d in docs.list_documents(db, alice.id)]
        print("9. delete removes the file, chunks, vectors and the record OK")
finally:
    with SessionLocal() as db:
        for uid in created:
            ids = list(db.scalars(select(Chunk.id).where(Chunk.user_id == uid)))
            if ids:
                store.delete(uid, ids)
            shutil.rmtree(vault / f"user-{uid}", ignore_errors=True)
        if created:
            db.execute(delete(User).where(User.id.in_(created)))
            db.commit()
    print("cleaned up test users, files and vectors")

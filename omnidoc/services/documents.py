import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select

from omnidoc.core import crypto
from omnidoc.core.config import get_settings
from omnidoc.db.models import Chunk, Document, Person
from omnidoc.ingestion.fields import normalize_field
from omnidoc.ingestion.pipeline import process_document
from omnidoc.providers.embeddings.base import Embedder
from omnidoc.providers.storage.base import FileStore
from omnidoc.providers.vectorstore.base import VectorStore
from omnidoc.services.doc_types import UNIQUE_TYPES, normalize_doc_type
from omnidoc.services.errors import NotFound, QuotaExceeded
from omnidoc.services.people import get_person
from omnidoc.services.retrieval import index_chunks


@dataclass
class AddResult:
    document_id: int
    doc_type: str
    fields_found: list[str]   # names only, never the values
    warnings: list[str]
    replaced: int


@dataclass
class DocumentInfo:
    id: int
    person_id: int
    person_name: str
    doc_type: str
    filename: str
    mime: str
    created_at: datetime
    # names of the values we hold (e.g. "pan_number"), never the values
    fields: list[str]


def _owned_document(db, user_id: int, document_id: int) -> Document:
    doc = db.scalar(select(Document).where(
        Document.id == document_id, Document.user_id == user_id))
    if doc is None:
        # same answer whether it is missing or someone else's
        raise NotFound("Document not found")
    return doc


def _fields_of(user_id: int, doc: Document) -> dict:
    return crypto.decrypt_json(user_id, doc.fields_enc) if doc.fields_enc else {}


def add_document(db, *, user_id: int, filename: str, data: bytes, files: FileStore, embedder: Embedder,
                 store: VectorStore, person_id: int | None = None, doc_type: str | None = None) -> AddResult:
    s = get_settings()
    if db.scalar(select(func.count()).select_from(Document).where(Document.user_id == user_id)) >= s.max_documents_per_user:
        raise QuotaExceeded(
            f"Document limit reached ({s.max_documents_per_user})")
    if person_id is None:  # default: the account's own "self" profile
        person = db.scalar(select(Person).where(
            Person.user_id == user_id).order_by(Person.id))
        if person is None:
            raise NotFound("Person not found")
    else:
        person = get_person(db, user_id, person_id)

    # may raise UnsupportedFileType / FileTooLarge
    processed = process_document(data)
    chosen = normalize_doc_type(doc_type) if doc_type else None
    final_type = chosen or processed.suggested_type or "other"

    warnings = []
    if chosen and processed.suggested_type and chosen != processed.suggested_type:
        warnings.append(
            f"You said this is a {chosen} document, but it looks like {processed.suggested_type}.")
    if not processed.has_text:
        warnings.append("No readable text was found. The file is stored and you can ask for it back, "
                        "but questions about its contents won't work unless you enter the numbers by hand.")
    if any(k.endswith("_unverified") for k in processed.fields):
        warnings.append("A number was read but failed its check, so it may contain a reading error. "
                        "Compare it with the original.")

    old_ids = []
    if final_type in UNIQUE_TYPES:  # a new upload replaces the old one of the same kind
        old_ids = list(db.scalars(select(Document.id).where(
            Document.user_id == user_id, Document.person_id == person.id, Document.doc_type == final_type)))

    key = files.save(user_id, data)
    try:
        doc = Document(user_id=user_id, person_id=person.id, doc_type=final_type,
                       filename=re.sub(r"[\r\n/\\]", "_",
                                       filename or "")[:255] or "document",
                       mime=processed.mime, storage_key=key,
                       fields_enc=crypto.encrypt_json(user_id, processed.fields) if processed.fields else None)
        db.add(doc)
        db.flush()
        index_chunks(db, user_id=user_id, document_id=doc.id, person_id=person.id, doc_type=final_type,
                     chunks=processed.chunks, embedder=embedder, store=store)
        db.commit()
    except Exception:
        db.rollback()
        files.delete(user_id, key)  # no orphan file if indexing failed
        raise
    for old_id in old_ids:
        delete_document(db, user_id, old_id, files, store)
    return AddResult(doc.id, final_type, sorted(processed.fields), warnings, len(old_ids))


def list_documents(db, user_id: int) -> list[DocumentInfo]:
    rows = db.execute(select(Document, Person.name).join(Person, Person.id == Document.person_id)
                      .where(Document.user_id == user_id).order_by(Document.id.desc())).all()
    return [DocumentInfo(d.id, d.person_id, name, d.doc_type, d.filename, d.mime, d.created_at,
                         sorted(_fields_of(user_id, d))) for d, name in rows]


def find_documents(db, user_id: int, *, person_id: int | None = None, doc_type: str | None = None) -> list[Document]:
    q = select(Document).where(Document.user_id == user_id)
    if person_id is not None:
        q = q.where(Document.person_id == person_id)
    if doc_type:
        q = q.where(Document.doc_type == normalize_doc_type(doc_type))
    return list(db.scalars(q.order_by(Document.id.desc())))


def get_fields(db, user_id: int, document_id: int) -> dict:
    return _fields_of(user_id, _owned_document(db, user_id, document_id))


def set_field(db, user_id: int, document_id: int, name: str, value: str) -> None:
    """For when OCR could not read a number: the user types it in. Validated before it is saved."""
    doc = _owned_document(db, user_id, document_id)
    # raises ValueError for a bad value or unknown field
    clean = normalize_field(name, value)
    fields = _fields_of(user_id, doc)
    fields[name] = clean
    fields.pop(f"{name}_unverified", None)
    doc.fields_enc = crypto.encrypt_json(user_id, fields)
    db.commit()


def read_file(db, user_id: int, document_id: int, files: FileStore) -> tuple[Document, bytes]:
    doc = _owned_document(db, user_id, document_id)
    return doc, files.load(user_id, doc.storage_key)


def delete_document(db, user_id: int, document_id: int, files: FileStore, store: VectorStore) -> None:
    doc = _owned_document(db, user_id, document_id)
    chunk_ids = list(db.scalars(select(Chunk.id).where(
        Chunk.user_id == user_id, Chunk.document_id == doc.id)))
    if chunk_ids:
        store.delete(user_id, chunk_ids)
    files.delete(user_id, doc.storage_key)
    db.execute(delete(Chunk).where(Chunk.user_id ==
               user_id, Chunk.document_id == doc.id))
    db.delete(doc)
    db.commit()

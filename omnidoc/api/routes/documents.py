import re
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status

from omnidoc.api.deps import DB, CurrentUser, Embeds, Files, Vectors, enforce
from omnidoc.api.schemas import DocumentOut, FieldIn, UploadOut
from omnidoc.core.config import get_settings
from omnidoc.ingestion.extract import FileTooLarge
from omnidoc.services import documents as docs

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut])
def list_documents(user: CurrentUser, db: DB):
    return [DocumentOut.model_validate(d, from_attributes=True) for d in docs.list_documents(db, user.id)]


@router.post("", response_model=UploadOut, status_code=status.HTTP_201_CREATED)
def upload_document(user: CurrentUser, db: DB, embedder: Embeds, store: Vectors, files: Files,
                    file: Annotated[UploadFile, File()],
                    person_id: Annotated[int | None, Form()] = None,
                    doc_type: Annotated[str | None, Form()] = None):
    s = get_settings()
    enforce(f"upload:{user.id}", s.uploads_per_hour_per_user, 3600)
    limit = s.max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)  # never read more than the limit allows
    if len(data) > limit:
        raise FileTooLarge(f"File is larger than {s.max_upload_mb} MB")
    r = docs.add_document(db, user_id=user.id, filename=file.filename or "document", data=data, files=files,
                          embedder=embedder, store=store, person_id=person_id, doc_type=(doc_type or None))
    return UploadOut(document_id=r.document_id, doc_type=r.doc_type, fields_found=r.fields_found,
                     warnings=r.warnings, replaced=r.replaced)


@router.get("/{document_id}/file")
def download_document(document_id: int, user: CurrentUser, db: DB, files: Files):
    doc, data = docs.read_file(db, user.id, document_id, files)
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_",
                       doc.filename)[:100] or "document"
    return Response(content=data, media_type=doc.mime, headers={
        "Content-Disposition": f'inline; filename="{safe_name}"',
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; sandbox",
    })


@router.put("/{document_id}/fields/{name}", status_code=status.HTTP_204_NO_CONTENT)
def set_document_field(document_id: int, name: str, body: FieldIn, user: CurrentUser, db: DB):
    """Type in a number the scanner couldn't read. It is checked before it is saved."""
    try:
        docs.set_field(db, user.id, document_id, name, body.value)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, user: CurrentUser, db: DB, store: Vectors, files: Files):
    docs.delete_document(db, user.id, document_id, files, store)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

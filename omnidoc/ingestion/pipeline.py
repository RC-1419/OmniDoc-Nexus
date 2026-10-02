from dataclasses import dataclass

from omnidoc.core.config import get_settings
from omnidoc.ingestion.chunker import chunk_text
from omnidoc.ingestion.extract import FileTooLarge, UnsupportedFileType, detect_mime, extract_text
from omnidoc.ingestion.fields import extract_fields, suggest_doc_type


@dataclass
class ProcessedDocument:
    mime: str
    chunks: list[str]
    fields: dict[str, str]
    suggested_type: str | None
    # False = nothing readable found (blurry scan?). The file can still be stored.
    has_text: bool


def process_document(data: bytes) -> ProcessedDocument:
    """Pure function: bytes in, structured result out. No database, no user, no network."""
    if not data:
        raise UnsupportedFileType("Empty file")
    if len(data) > get_settings().max_upload_mb * 1024 * 1024:
        raise FileTooLarge(
            f"File is larger than {get_settings().max_upload_mb} MB")
    mime = detect_mime(data)
    text = extract_text(data, mime)
    fields = extract_fields(text)
    return ProcessedDocument(mime, chunk_text(text), fields, suggest_doc_type(text, fields), bool(text.strip()))

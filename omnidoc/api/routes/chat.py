from fastapi import APIRouter

from omnidoc.api import deps
from omnidoc.api.deps import DB, CurrentUser, Embeds, Files, Vectors, enforce
from omnidoc.api.schemas import ChatIn, ChatOut, ConfirmIn, EmailActionOut, SentOut, ShownDocument
from omnidoc.core.config import get_settings
from omnidoc.services import chat as chat_service
from omnidoc.services import documents as docs

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatOut)
def send_message(body: ChatIn, user: CurrentUser, db: DB, embedder: Embeds, store: Vectors, files: Files):
    enforce(f"chat:{user.id}", get_settings().chat_per_minute_per_user, 60)
    llm = deps.llm_for(body.provider)
    reply = chat_service.chat(db, user=user, message=body.message, history=[m.model_dump() for m in body.history],
                              llm=llm, embedder=embedder, store=store, files=files)
    shown = None
    if reply.show_document_id is not None:  # the file itself is fetched with GET /documents/{id}/file
        info = next((d for d in docs.list_documents(db, user.id) if d.id == reply.show_document_id), None)
        if info:
            shown = ShownDocument(document_id=info.id, filename=info.filename, mime=info.mime, doc_type=info.doc_type)
    action = reply.email_action
    return ChatOut(
        text=reply.text, show_document=shown, provider=reply.provider,
        email_action=EmailActionOut(token=action.token, to=action.to, document_id=action.document_id,
                                    doc_type=action.doc_type, description=action.description) if action else None)


@router.post("/confirm-email", response_model=SentOut)
def confirm_email(body: ConfirmIn, user: CurrentUser, db: DB, files: Files):
    """Sends an email the user was shown in the chat. Needs the signed token that /chat produced."""
    enforce(f"confirm:{user.id}", get_settings().chat_per_minute_per_user, 60)
    result = chat_service.confirm_email(db, user=user, token=body.token, files=files, preferred=body.provider)
    return SentOut(provider=result.provider)

from datetime import datetime, timedelta

from sqlalchemy import func, select

from omnidoc.core.config import get_settings
from omnidoc.db.models import EmailLog
from omnidoc.providers.email.base import Attachment, EmailError, OutgoingEmail, clean_address, clean_subject
from omnidoc.providers.email.factory import (SendResult, get_email_provider, provider_order,
                                             send_with_fallback)


class EmailLimitReached(EmailError):
    def __init__(self, limit: int):
        super().__init__("limit", f"daily limit of {limit} emails reached")


def sent_last_24h(db, user_id: int) -> int:
    since = datetime.utcnow() - timedelta(hours=24)
    return db.scalar(select(func.count()).select_from(EmailLog)
                     .where(EmailLog.user_id == user_id, EmailLog.status == "sent",
                            EmailLog.created_at >= since)) or 0


def send_email(db, *, user_id: int, to: str, subject: str, body: str,
               attachment: Attachment | None = None, preferred: str | None = None) -> SendResult:
    """Every email goes out from the owner's account, so each user gets a daily cap."""
    limit = get_settings().email_daily_limit_per_user
    if sent_last_24h(db, user_id) >= limit:
        raise EmailLimitReached(limit)
    try:
        message = OutgoingEmail(clean_address(
            to), clean_subject(subject), body, attachment)
    except ValueError as e:
        raise EmailError("input", str(e)) from None
    names = provider_order(preferred, needs_attachment=attachment is not None)
    if not names:
        raise EmailError(
            "email", "no email provider is set up that can send this")
    try:
        result = send_with_fallback(
            [get_email_provider(n) for n in names], message)
    except EmailError:
        db.add(EmailLog(user_id=user_id, to_address=message.to,
               provider="none", status="failed"))
        db.commit()
        raise
    db.add(EmailLog(user_id=user_id, to_address=message.to,
           provider=result.provider, status="sent"))
    db.commit()
    return result

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from omnidoc.db.models import Base
from omnidoc.core.clock import utcnow


class UsedActionToken(Base):
    """A confirmation token that has been used (only a hash of it is kept). The table is created
    automatically at startup; rows older than a day are removed, because the tokens expire in 10 minutes."""
    __tablename__ = "used_action_tokens"
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    used_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, index=True)

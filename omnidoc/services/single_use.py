import hashlib
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from omnidoc.db.used_tokens import UsedActionToken

# tokens expire after 10 minutes, so a day is far more than enough
KEEP = timedelta(days=1)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def claim(db, user_id: int, token: str) -> bool:
    """True for the first caller only. The database decides: two clicks at the same moment cannot both win."""
    db.execute(delete(UsedActionToken).where(
        UsedActionToken.used_at < datetime.utcnow() - KEEP))
    result = db.execute(insert(UsedActionToken).values(user_id=int(user_id), token_hash=_hash(token))
                        .on_conflict_do_nothing())
    db.commit()
    return result.rowcount == 1


def release(db, user_id: int, token: str) -> None:
    """Give a token back after a failed send, so the user can press Confirm again."""
    db.rollback()
    db.execute(delete(UsedActionToken).where(UsedActionToken.user_id == int(user_id),
                                             UsedActionToken.token_hash == _hash(token)))
    db.commit()

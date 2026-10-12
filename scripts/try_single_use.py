"""Checks the single-use rule on its own, against your local database.   python -m scripts.try_single_use"""
from datetime import timedelta

from sqlalchemy import delete

from omnidoc.db.session import SessionLocal, init_db
from omnidoc.db.used_tokens import UsedActionToken
from omnidoc.services import single_use
from omnidoc.core.clock import utcnow

init_db()
U1, U2 = 987654321, 987654322  # not real accounts: the table has no link to users
with SessionLocal() as db:
    try:
        assert single_use.claim(db, U1, "token-a") is True
        assert single_use.claim(db, U1, "token-a") is False
        print("1. the first use works and the second is refused OK")
        assert single_use.claim(
            db, U1, "token-b") is True and single_use.claim(db, U2, "token-a") is True
        print("2. other tokens and other users are not affected OK")
        single_use.release(db, U1, "token-a")
        assert single_use.claim(db, U1, "token-a") is True
        print("3. a token given back after a failed send can be used again OK")
        db.add(UsedActionToken(user_id=U1, token_hash="old",
               used_at=utcnow() - timedelta(days=2)))
        db.commit()
        single_use.claim(db, U1, "token-c")
        assert db.get(UsedActionToken, (U1, "old")) is None
        print("4. records older than a day are cleaned up OK")
    finally:
        db.rollback()
        db.execute(delete(UsedActionToken).where(
            UsedActionToken.user_id.in_([U1, U2])))
        db.commit()

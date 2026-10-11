"""Single-use tokens against the real database, including two clicks at exactly the same moment."""
import random
import threading
from datetime import datetime, timedelta

import pytest
from sqlalchemy import delete, select

from omnidoc.db.session import SessionLocal
from omnidoc.db.used_tokens import UsedActionToken
from omnidoc.services import single_use


@pytest.fixture
# `world` makes sure the table exists (created when the app starts)
def uid(world):
    # not a real user, so nothing real can be touched
    user_id = random.randint(10**9, 2 * 10**9)
    yield user_id
    with SessionLocal() as db:
        db.execute(delete(UsedActionToken).where(
            UsedActionToken.user_id == user_id))
        db.commit()


def claim(user_id, token):
    with SessionLocal() as db:
        return single_use.claim(db, user_id, token)


def test_first_claim_wins_and_the_second_loses(uid):
    assert claim(uid, "token-one") is True
    assert claim(uid, "token-one") is False


def test_different_tokens_and_different_users_are_independent(uid):
    assert claim(uid, "a") and claim(uid, "b")
    # the same text for another user is a different claim
    assert claim(uid + 1, "a")
    with SessionLocal() as db:
        db.execute(delete(UsedActionToken).where(
            UsedActionToken.user_id == uid + 1))
        db.commit()


def test_a_released_token_can_be_claimed_again(uid):
    assert claim(uid, "retry")
    with SessionLocal() as db:
        single_use.release(db, uid, "retry")
    assert claim(uid, "retry") is True


def test_only_a_hash_is_stored(uid):
    claim(uid, "plain-text-token")
    with SessionLocal() as db:
        stored = db.execute(select(UsedActionToken.token_hash).where(
            UsedActionToken.user_id == uid)).scalar_one()
    assert stored == single_use._hash(
        "plain-text-token") and "plain-text-token" not in stored


def test_old_rows_are_cleaned_up_on_the_next_claim(uid):
    with SessionLocal() as db:
        db.add(UsedActionToken(user_id=uid, token_hash=single_use._hash(
            "old"), used_at=datetime.utcnow() - timedelta(days=2)))
        db.commit()
    assert claim(uid, "new")
    with SessionLocal() as db:
        hashes = set(db.execute(select(UsedActionToken.token_hash).where(
            UsedActionToken.user_id == uid)).scalars())
    assert hashes == {single_use._hash("new")}


def test_two_clicks_at_the_same_moment_only_one_wins(uid):
    results, barrier = [], threading.Barrier(8)

    def click():
        barrier.wait()
        results.append(claim(uid, "double-click"))

    threads = [threading.Thread(target=click) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [False] * 7 + [True]

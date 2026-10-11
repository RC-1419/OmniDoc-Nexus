"""Single-use confirmation tokens: tested with a stand-in for the database that records what is sent to it.
The real database behaviour (including two clicks at the same moment) is in tests/integration."""
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

from omnidoc.services import single_use


class FakeDb:
    def __init__(self, insert_rowcount=1):
        self.insert_rowcount = insert_rowcount
        self.statements, self.calls = [], []

    def execute(self, stmt):
        self.statements.append(stmt)
        self.calls.append("execute")
        return SimpleNamespace(rowcount=self.insert_rowcount if stmt.__visit_name__ == "insert" else 0)

    def commit(self):
        self.calls.append("commit")

    def rollback(self):
        self.calls.append("rollback")


def sql(stmt):
    return str(stmt.compile(dialect=postgresql.dialect()))


def test_hash_is_sha256_and_hides_the_token():
    h = single_use._hash("secret-token-value")
    assert len(h) == 64 and int(h, 16) >= 0
    assert "secret" not in h
    assert h == single_use._hash(
        "secret-token-value") and h != single_use._hash("secret-token-valuf")


def test_first_claim_wins():
    db = FakeDb(insert_rowcount=1)
    assert single_use.claim(db, 7, "tok") is True
    assert db.calls[-1] == "commit"


def test_second_claim_loses():
    assert single_use.claim(FakeDb(insert_rowcount=0), 7, "tok") is False


def test_claim_inserts_with_conflict_ignored_and_purges_old_rows_first():
    db = FakeDb()
    single_use.claim(db, 7, "tok")
    first, second = (sql(s) for s in db.statements)
    assert first.startswith(
        "DELETE FROM used_action_tokens") and "used_at <" in first
    assert second.startswith(
        "INSERT INTO used_action_tokens") and "ON CONFLICT DO NOTHING" in second


def test_the_token_itself_is_never_stored():
    db = FakeDb()
    single_use.claim(db, 7, "plain-token-text")
    params = {k: v for s in db.statements for k, v in s.compile(
        dialect=postgresql.dialect()).params.items()}
    assert "plain-token-text" not in params.values() and single_use._hash("plain-token-text") in params.values()


def test_release_rolls_back_then_deletes_that_one_token():
    db = FakeDb()
    single_use.release(db, 7, "tok")
    assert db.calls == ["rollback", "execute", "commit"]
    stmt = sql(db.statements[0])
    assert stmt.startswith(
        "DELETE FROM used_action_tokens") and "user_id =" in stmt and "token_hash =" in stmt

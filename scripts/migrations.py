"""Helpers for database changes (Alembic). Both commands use a throw-away scratch database,
so your real data and your current tables are never involved.

  python -m scripts.migrations new "add phone number to users"   # write a new change script
  python -m scripts.migrations check                             # do the change scripts match the models?

Day to day: change a model in omnidoc/db/models.py, run `new`, read the script it wrote in
migrations/versions/, then run `check`. The change is applied to a real database by `alembic upgrade head`
(the server does this by itself on every update).
"""
import sys

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

import omnidoc.db.used_tokens  # noqa: F401
from omnidoc.core.config import get_settings
from omnidoc.db.models import Base

SCRATCH = "omnidoc_migrate_scratch"


def _scratch_url():
    return make_url(get_settings().database_url).set(database=SCRATCH)


def _admin():
    return create_engine(make_url(get_settings().database_url).set(database="postgres"),
                         isolation_level="AUTOCOMMIT")


def _recreate_scratch():
    _drop_scratch()
    admin = _admin()
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{SCRATCH}"'))
    admin.dispose()


def _drop_scratch():
    admin = _admin()
    with admin.connect() as c:
        c.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                       # close stray sessions
                       "WHERE datname = :d AND pid <> pg_backend_pid()"), {"d": SCRATCH})
        c.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH}"'))
    admin.dispose()


def _config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", _scratch_url().render_as_string(
        hide_password=False).replace("%", "%%"))
    return cfg


def new(message: str) -> None:
    _recreate_scratch()
    try:
        cfg = _config()
        # the scratch database as the scripts leave it today
        command.upgrade(cfg, "head")
        # what the models need on top of that
        command.revision(cfg, message=message, autogenerate=True)
    finally:
        _drop_scratch()
    print("Written to migrations/versions/. Read it before you commit it.")


def check() -> int:
    _recreate_scratch()
    try:
        command.upgrade(_config(), "head")
        engine = create_engine(_scratch_url())
        try:
            with engine.connect() as conn:
                diff = compare_metadata(MigrationContext.configure(
                    conn, opts={"compare_type": True}), Base.metadata)
        finally:
            engine.dispose()  # close its connections, or the scratch database cannot be deleted
    finally:
        _drop_scratch()
    if diff:
        print("The change scripts do NOT match the models yet. Differences:")
        for d in diff:
            print("  ", d)
        print('Run:  python -m scripts.migrations new "describe the change"')
        return 1
    print("OK: the change scripts match the models.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "new":
        new(" ".join(sys.argv[2:]))
    elif len(sys.argv) == 2 and sys.argv[1] == "check":
        sys.exit(check())
    else:
        raise SystemExit(__doc__)

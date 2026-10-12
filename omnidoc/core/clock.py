"""One place for 'now in UTC', so the rest of the code does not use the deprecated datetime.utcnow().

The database columns store plain (timezone-less) UTC times, so this returns a plain UTC value as well. It is
the same value utcnow() gave, built with the current, non-deprecated call.
"""
from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from omnidoc.core.security import hash_password, verify_password
from omnidoc.db.models import Person, User

# keeps timing equal for unknown users
_DUMMY_HASH = hash_password("dummy-password")


class UsernameTaken(Exception):
    pass


def register_user(db, username: str, password: str, email: str | None = None) -> User:
    username = username.strip().lower()
    user = User(username=username, email=email,
                password_hash=hash_password(password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:  # unique constraint on username
        db.rollback()
        raise UsernameTaken(username)
    # default "self" profile
    db.add(Person(user_id=user.id, name=username, relation="self"))
    db.commit()
    return user


def authenticate(db, username: str, password: str) -> User | None:
    user = db.scalar(select(User).where(
        User.username == username.strip().lower()))
    if user is None:
        verify_password(password, _DUMMY_HASH)
        return None
    return user if verify_password(password, user.password_hash) else None

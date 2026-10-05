from sqlalchemy import func, select

from omnidoc.core.config import get_settings
from omnidoc.db.models import Person
from omnidoc.services.errors import DocumentError, NotFound, QuotaExceeded


def list_people(db, user_id: int) -> list[Person]:
    return list(db.scalars(select(Person).where(Person.user_id == user_id).order_by(Person.id)))


def get_person(db, user_id: int, person_id: int) -> Person:
    person = db.scalar(select(Person).where(
        Person.id == person_id, Person.user_id == user_id))
    if person is None:
        raise NotFound("Person not found")
    return person


def add_person(db, user_id: int, name: str, relation: str = "family") -> Person:
    name, relation = (name or "").strip(
    ), (relation or "family").strip().lower()
    if not 1 <= len(name) <= 120 or not 1 <= len(relation) <= 40:
        raise DocumentError(
            "Give a name (up to 120 characters) and a relation (up to 40)")
    count = db.scalar(select(func.count()).select_from(
        Person).where(Person.user_id == user_id))
    if count >= get_settings().max_people_per_user:
        raise QuotaExceeded("Family member limit reached")
    person = Person(user_id=user_id, name=name, relation=relation)
    db.add(person)
    db.commit()
    return person

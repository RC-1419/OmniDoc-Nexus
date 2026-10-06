from fastapi import APIRouter, status

from omnidoc.api.deps import DB, CurrentUser
from omnidoc.api.schemas import PersonIn, PersonOut
from omnidoc.services import people

router = APIRouter(prefix="/people", tags=["people"])


@router.get("", response_model=list[PersonOut])
def list_people(user: CurrentUser, db: DB):
    return [PersonOut.model_validate(p, from_attributes=True) for p in people.list_people(db, user.id)]


@router.post("", response_model=PersonOut, status_code=status.HTTP_201_CREATED)
def add_person(body: PersonIn, user: CurrentUser, db: DB):
    return PersonOut.model_validate(people.add_person(db, user.id, body.name, body.relation), from_attributes=True)

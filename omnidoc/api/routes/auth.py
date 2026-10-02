from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from omnidoc.api.deps import DB, CurrentUser
from omnidoc.api.schemas import SignupIn, TokenOut, UserOut
from omnidoc.core.security import create_access_token
from omnidoc.services.auth import UsernameTaken, authenticate, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(body: SignupIn, db: DB):
    try:
        return register_user(db, body.username, body.password, body.email)
    except UsernameTaken:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")


@router.post("/login", response_model=TokenOut)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DB):
    user = authenticate(db, form.username, form.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password",
                            headers={"WWW-Authenticate": "Bearer"})
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from omnidoc.api.deps import DB, CurrentUser, client_ip, enforce, limiter, too_many
from omnidoc.api.schemas import SignupIn, TokenOut, UserOut
from omnidoc.core.config import get_settings
from omnidoc.core.security import create_access_token
from omnidoc.services.auth import UsernameTaken, authenticate, register_user

router = APIRouter(prefix="/auth", tags=["auth"])

FAILURE_WINDOW = 15 * 60


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(body: SignupIn, db: DB, request: Request):
    enforce(f"signup:{client_ip(request)}", get_settings().signup_per_hour_per_ip, 3600)
    try:
        return register_user(db, body.username, body.password, body.email)
    except UsernameTaken:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")


@router.post("/login", response_model=TokenOut)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DB, request: Request):
    limit = get_settings().login_failures_per_15min
    keys = (f"login-fail-ip:{client_ip(request)}", f"login-fail-user:{form.username.strip().lower()[:64]}")
    for key in keys:  # only failed attempts count, so normal use is never slowed down
        wait = limiter.wait_time(key, limit, FAILURE_WINDOW)
        if wait:
            raise too_many(wait)
    user = authenticate(db, form.username, form.password)
    if user is None:
        for key in keys:
            limiter.record(key, FAILURE_WINDOW)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password",
                            headers={"WWW-Authenticate": "Bearer"})
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user

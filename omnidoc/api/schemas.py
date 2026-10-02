from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupIn(BaseModel):
    username: str = Field(min_length=3, max_length=32,
                          pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=72)
    email: EmailStr | None = None  # optional; used for "email it to me"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

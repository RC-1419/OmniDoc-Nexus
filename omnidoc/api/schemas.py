from datetime import datetime
from typing import Literal

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


class ProviderOut(BaseModel):
    name: str
    label: str


class ProvidersOut(BaseModel):
    llm: list[ProviderOut]
    default_llm: str | None
    email: list[str]


class PersonIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    relation: str = Field(default="family", min_length=1, max_length=40)


class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    relation: str


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    person_id: int
    person_name: str
    doc_type: str
    filename: str
    mime: str
    created_at: datetime
    # names of the numbers we hold, never the numbers themselves
    fields: list[str]


class UploadOut(BaseModel):
    document_id: int
    doc_type: str
    fields_found: list[str]
    warnings: list[str]
    replaced: int


class FieldIn(BaseModel):
    value: str = Field(min_length=1, max_length=64)


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=20)
    provider: str | None = Field(default=None, max_length=30)


class ShownDocument(BaseModel):
    document_id: int
    filename: str
    mime: str
    doc_type: str


class EmailActionOut(BaseModel):
    token: str
    to: str
    document_id: int
    doc_type: str
    description: str


class ChatOut(BaseModel):
    text: str
    show_document: ShownDocument | None = None
    email_action: EmailActionOut | None = None
    provider: str = ""


class ConfirmIn(BaseModel):
    token: str = Field(min_length=10, max_length=2000)
    provider: str | None = Field(default=None, max_length=30)


class SentOut(BaseModel):
    sent: bool = True
    provider: str

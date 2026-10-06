from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Omnidoc Nexus"
    database_url: str = "postgresql+psycopg2://omnidoc:omnidoc@localhost:5432/omnidoc"

    jwt_secret: str = ""
    jwt_expire_minutes: int = 60

    vault_key: str = ""
    vault_dir: str = "data/vault"

    pinecone_api_key: str = ""
    # "shared" (filter by user_id) or "user" (namespace per user)
    pinecone_namespace_mode: str = "shared"
    pinecone_index: str = "omnidoc-nexus"
    pinecone_region: str = "us-east-1"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    embedding_cache_dir: str = "data/models"

    default_llm: str = "groq"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""  # empty = same as smtp_user
    gmail_credentials_path: str = "data/gmail/credentials.json"
    gmail_token_path: str = "data/gmail/token.json"
    gmail_sender: str = ""  # empty = Gmail uses the authorised account
    sendlib_api_url: str = "https://sendlib.samueltuoyo.com/api/send"
    sendlib_api_key: str = ""
    sendlib_enabled: bool = False
    sendlib_allow_attachments: bool = False
    email_provider_order: str = "smtp,gmail,sendlib"
    email_daily_limit_per_user: int = 10
    email_timeout_seconds: int = 20

    tesseract_cmd: str = ""
    ocr_languages: str = "eng"
    ocr_max_pages: int = 10
    max_upload_mb: int = 10
    ocr_psm: int = 11
    # "gray,B,R,G" can be added for other kinds of documents, but each extra channel adds slower OCR passes on a document that fails.
    ocr_channels: str = "gray,B"

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    mistral_api_key: str = ""
    mistral_model: str = "mistral-small-latest"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    # e.g. "groq,mistral". Empty = never switch provider silently
    llm_fallback_order: str = ""
    llm_timeout_seconds: int = 30

    max_documents_per_user: int = 30
    max_people_per_user: int = 20

    cors_origins: str = ""
    enable_docs: bool = True
    login_failures_per_15min: int = 10
    signup_per_hour_per_ip: int = 5
    chat_per_minute_per_user: int = 20
    uploads_per_hour_per_user: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()

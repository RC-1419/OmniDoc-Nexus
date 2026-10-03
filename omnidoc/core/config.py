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
    sendlib_api_url: str = "https://sendlib.samueltuoyo.com/api/send"
    sendlib_api_key: str = ""
    email_provider_order: str = "sendlib,smtp,gmail"

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
    llm_fallback_order: str = ""  # e.g. "groq,mistral". Empty = never switch provider silently
    llm_timeout_seconds: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()

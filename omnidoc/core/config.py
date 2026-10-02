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
    pinecone_index: str = "omnidoc-nexus"
    pinecone_region: str = "us-east-1"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    default_llm: str = "groq"
    default_email_provider: str = "smtp"


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://user:password@db:5432/db"
    app_base_url: str = "http://host.docker.internal:5374"
    api_base_url: str = "http://host.docker.internal:5301"
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_name: str = "Company SSO"
    oidc_redirect_uri: str = "http://host.docker.internal:5301/api/v1/auth/oidc/callback"
    session_cookie: str = "issue_tracker_session"
    cookie_secure: bool = False
    session_ttl: int = 43200
    attachment_dir: Path = Path(__file__).resolve().parents[2] / "var" / "attachments"
    max_upload_bytes: int = 20 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()

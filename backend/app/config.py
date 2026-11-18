from functools import lru_cache
from pathlib import Path
import os
import tomllib
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderConfig(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,39}$")
    name: str
    type: Literal["oidc", "facebook"] = "oidc"
    issuer: str = ""
    client_id: str
    client_secret: str = ""
    client_secret_env: str = ""
    graph_version: str = Field(default="v24.0", pattern=r"^v[0-9]+\.0$")

    @model_validator(mode="after")
    def validate_provider(self):
        if self.client_secret_env:
            self.client_secret = os.environ.get(self.client_secret_env, "")
            if not self.client_secret:
                raise ValueError("Provider client secret environment variable is missing")
        if self.id == "password" or not self.client_id:
            raise ValueError("Provider requires a non-reserved ID and client ID")
        if self.type == "oidc" and not self.issuer:
            raise ValueError("OIDC provider requires an issuer")
        if self.type == "facebook" and not self.client_secret:
            raise ValueError("Facebook provider requires a client secret")
        return self


def toml_settings(path):
    if not path:
        return {}
    with open(path, "rb") as stream:
        return tomllib.load(stream)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    tracker_config: Path | None = None
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
    providers: list[ProviderConfig] = Field(default_factory=list)
    password_enabled: bool = False
    notifications_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_security: Literal["starttls", "tls", "none"] = "starttls"
    smtp_from: str = ""
    mail_encryption_key: str = ""
    invitation_ttl: int = Field(default=86400, ge=300, le=604800)
    password_reset_ttl: int = Field(default=3600, ge=300, le=86400)

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        def config_source():
            path = (init_settings().get("tracker_config") or env_settings().get("tracker_config")
                    or dotenv_settings().get("tracker_config"))
            return toml_settings(path)
        return init_settings, env_settings, dotenv_settings, config_source, file_secret_settings

    @model_validator(mode="after")
    def validate_auth(self):
        ids = [p.id for p in self.providers]
        if len(ids) != len(set(ids)):
            raise ValueError("Provider IDs must be unique")
        if self.password_enabled:
            from cryptography.fernet import Fernet
            if not self.smtp_host or not self.smtp_from:
                raise ValueError("Password login requires smtp_host and smtp_from")
            Fernet(self.mail_encryption_key.encode())
        if self.notifications_enabled:
            from cryptography.fernet import Fernet
            if not self.smtp_host or not self.smtp_from:
                raise ValueError("Notifications require smtp_host and smtp_from")
            Fernet(self.mail_encryption_key.encode())
        return self

    def configured_providers(self):
        if self.providers:
            return self.providers
        if self.oidc_issuer and self.oidc_client_id:
            return [ProviderConfig(id="oidc", name=self.oidc_name, issuer=self.oidc_issuer,
                                   client_id=self.oidc_client_id, client_secret=self.oidc_client_secret)]
        return []


@lru_cache
def get_settings() -> Settings:
    return Settings()

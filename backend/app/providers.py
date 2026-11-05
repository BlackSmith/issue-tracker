from dataclasses import dataclass
from typing import Protocol

from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request

from app.config import Settings


@dataclass(frozen=True)
class ExternalProfile:
    issuer: str
    subject: str
    name: str
    email: str


class IdentityProvider(Protocol):
    async def authorize(self, request: Request): ...
    async def identity(self, request: Request) -> ExternalProfile: ...


class OIDCProvider:
    """Provider-specific OAuth adapters can implement the same normalized contract."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.oauth = OAuth()
        self.client = self.oauth.register(
            "oidc",
            client_id=settings.oidc_client_id,
            client_secret=settings.oidc_client_secret or None,
            server_metadata_url=settings.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration",
            client_kwargs={"scope": "openid profile email", "code_challenge_method": "S256"},
        )

    async def authorize(self, request: Request):
        return await self.client.authorize_redirect(request, self.settings.oidc_redirect_uri)

    async def identity(self, request: Request) -> ExternalProfile:
        token = await self.client.authorize_access_token(request)
        # Authlib verifies signature, audience, expiry and nonce before returning userinfo.
        claims = token.get("userinfo")
        if not claims or claims.get("iss") != self.settings.oidc_issuer:
            raise ValueError("Invalid issuer or missing ID token")
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise ValueError("Missing subject")
        return ExternalProfile(
            issuer=claims["iss"], subject=subject,
            name=str(claims.get("name") or claims.get("preferred_username") or "User")[:200],
            email=str(claims.get("email") or "")[:320],
        )

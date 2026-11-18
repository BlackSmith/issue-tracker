from dataclasses import dataclass
from typing import Protocol
import hashlib
import hmac

from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request

from app.config import Settings, ProviderConfig


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

    def __init__(self, settings: Settings, config: ProviderConfig | None = None):
        self.settings = settings
        self.config = config
        self.issuer = config.issuer if config else settings.oidc_issuer
        self.redirect_uri = settings.api_base_url.rstrip('/') + f"/api/v1/auth/{config.id}/callback" if config else settings.oidc_redirect_uri
        self.oauth = OAuth()
        self.client = self.oauth.register(
            config.id if config else "oidc",
            client_id=config.client_id if config else settings.oidc_client_id,
            client_secret=(config.client_secret if config else settings.oidc_client_secret) or None,
            server_metadata_url=self.issuer.rstrip("/") + "/.well-known/openid-configuration",
            client_kwargs={"scope": "openid profile email", "code_challenge_method": "S256"},
        )

    async def authorize(self, request: Request):
        return await self.client.authorize_redirect(request, self.redirect_uri)

    async def identity(self, request: Request) -> ExternalProfile:
        token = await self.client.authorize_access_token(request)
        # Authlib verifies signature, audience, expiry and nonce before returning userinfo.
        claims = token.get("userinfo")
        if not claims or claims.get("iss") != self.issuer:
            raise ValueError("Invalid issuer or missing ID token")
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise ValueError("Missing subject")
        return ExternalProfile(
            issuer=claims["iss"], subject=subject,
            name=str(claims.get("name") or claims.get("preferred_username") or "User")[:200],
            email=str(claims.get("email") or "")[:320],
        )


class FacebookProvider:
    def __init__(self, settings: Settings, config: ProviderConfig):
        self.config = config
        self.redirect_uri = settings.api_base_url.rstrip('/') + f"/api/v1/auth/{config.id}/callback"
        oauth = OAuth()
        self.client = oauth.register(config.id, client_id=config.client_id, client_secret=config.client_secret,
                                     authorize_url=f"https://www.facebook.com/{config.graph_version}/dialog/oauth",
                                     access_token_url=f"https://graph.facebook.com/{config.graph_version}/oauth/access_token",
                                     api_base_url=f"https://graph.facebook.com/{config.graph_version}/",
                                     client_kwargs={"scope": "public_profile email", "token_endpoint_auth_method": "client_secret_post"})

    async def authorize(self, request: Request):
        return await self.client.authorize_redirect(request, self.redirect_uri)

    async def identity(self, request: Request) -> ExternalProfile:
        # Authlib validates the session-bound OAuth state before exchanging the code.
        token = await self.client.authorize_access_token(request)
        proof = hmac.new(self.config.client_secret.encode(), token["access_token"].encode(), hashlib.sha256).hexdigest()
        response = await self.client.get("me", token=token, params={"fields": "id,name,email", "appsecret_proof": proof})
        response.raise_for_status()
        profile = response.json()
        if not isinstance(profile.get("id"), str) or not profile["id"]:
            raise ValueError("Missing Facebook user ID")
        # Facebook IDs are app-scoped. Include the app ID in the identity namespace.
        return ExternalProfile(issuer=f"https://www.facebook.com/{self.config.client_id}", subject=profile["id"],
                               name=str(profile.get("name") or "User")[:200], email=str(profile.get("email") or "")[:320])

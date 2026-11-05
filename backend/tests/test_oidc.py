import asyncio
import json
import time
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import pytest
from authlib.jose import JsonWebKey, jwt
from starlette.requests import Request

from app.config import Settings
from app.providers import OIDCProvider


@pytest.mark.parametrize("failure", [None, "nonce", "issuer", "audience", "expiry", "signature", "missing_token", "state"])
def test_oidc_verifies_identity_and_authorization_binding(failure):
    async def scenario():
        key = JsonWebKey.generate_key("RSA", 2048, is_private=True, options={"kid": "test-key"})
        settings = Settings(oidc_issuer="https://identity.example", oidc_client_id="tracker",
                            oidc_redirect_uri="https://tracker.example/callback")
        provider = OIDCProvider(settings)
        nonce = ""

        def transport(request):
            if request.url.path == "/.well-known/openid-configuration":
                return httpx.Response(200, json={
                    "issuer": settings.oidc_issuer,
                    "authorization_endpoint": settings.oidc_issuer + "/authorize",
                    "token_endpoint": settings.oidc_issuer + "/token",
                    "jwks_uri": settings.oidc_issuer + "/jwks",
                    "id_token_signing_alg_values_supported": ["RS256"],
                })
            if request.url.path == "/jwks":
                return httpx.Response(200, json={"keys": [key.as_dict(is_private=False)]})
            if request.url.path == "/token":
                params = parse_qs(request.content.decode())
                assert params["code_verifier"][0]
                claims = {"iss": settings.oidc_issuer, "sub": "stable-subject", "aud": "tracker",
                          "iat": int(time.time()), "exp": int(time.time()) + 300,
                          "nonce": nonce, "name": "Test User", "email": "person@example.test"}
                if failure == "nonce": claims["nonce"] = "other"
                if failure == "issuer": claims["iss"] = "https://attacker.example"
                if failure == "audience": claims["aud"] = "other-client"
                if failure == "expiry": claims["exp"] = int(time.time()) - 1000
                signing_key = JsonWebKey.generate_key("RSA", 2048, is_private=True) if failure == "signature" else key
                token = jwt.encode({"alg": "RS256", "kid": "test-key"}, claims, signing_key).decode()
                result = {"access_token": "access", "token_type": "Bearer", "id_token": token}
                if failure == "missing_token": result.pop("id_token")
                return httpx.Response(200, json=result)
            raise AssertionError(f"Unexpected endpoint {request.url}")

        provider.client.client_kwargs["transport"] = httpx.MockTransport(transport)
        session = {}

        def request(query=""):
            return Request({"type": "http", "method": "GET", "scheme": "https", "path": "/callback",
                            "query_string": query.encode(), "headers": [], "server": ("tracker.example", 443),
                            "session": session})

        redirect = await provider.authorize(request())
        params = parse_qs(urlparse(redirect.headers["location"]).query)
        nonce = params["nonce"][0]
        assert params["code_challenge_method"] == ["S256"]
        assert "code_verifier" not in redirect.headers["location"]
        assert "code_verifier" in json.dumps(session)
        state = "forged" if failure == "state" else params["state"][0]
        callback = request(urlencode({"code": "test-code", "state": state}))
        if failure:
            with pytest.raises(Exception):
                await provider.identity(callback)
        else:
            identity = await provider.identity(callback)
            assert identity.issuer == settings.oidc_issuer
            assert identity.subject == "stable-subject"
            assert identity.name == "Test User"

    asyncio.run(scenario())

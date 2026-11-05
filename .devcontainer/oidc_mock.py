"""Development-only compatibility shim for keycloak-mockup v0.1.0.

The upstream image omits ID tokens and ignores PKCE. Keep these corrections in
the fake provider so the application exercises normal OIDC verification.
"""

import base64
import hashlib
import importlib
import secrets
import time
from contextvars import ContextVar
from functools import wraps

from fastapi import HTTPException
from fastapi.responses import JSONResponse

mock = importlib.import_module("keycloak_mockup.main")
parameters = ContextVar("oidc_parameters", default={})
original_issue_code = mock._issue_code
CALLBACK = "http://host.docker.internal:5301/api/v1/auth/oidc/callback"


def issue_code(user, redirect_uri):
    code = original_issue_code(user, redirect_uri)
    params = parameters.get()
    mock._auth_codes[code].update(
        nonce=params.get("nonce"), challenge=params.get("code_challenge"),
        client_id=params.get("client_id"),
    )
    return code


def handle_code_grant(code, redirect_uri, request):
    mock._purge_expired_codes()
    entry = mock._auth_codes.pop(code, None)
    if not entry or entry["expires"] <= time.time():
        raise HTTPException(400, "Invalid or expired authorization code")
    if redirect_uri != entry["redirect_uri"]:
        raise HTTPException(400, "Redirect URI mismatch")
    params = parameters.get()
    client_id = params.get("client_id") or ""
    authorization = request.headers.get("authorization", "")
    if not client_id and authorization.lower().startswith("basic "):
        try:
            client_id = base64.b64decode(authorization.split(" ", 1)[1]).decode().split(":", 1)[0]
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(400, "Invalid client authentication")
    if client_id != entry["client_id"]:
        raise HTTPException(400, "Client mismatch")
    verifier = params.get("code_verifier") or ""
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    if not verifier or not secrets.compare_digest(challenge, entry.get("challenge") or ""):
        raise HTTPException(400, "Invalid PKCE verifier")
    user = mock.cfg.find_user(entry["username"])
    if not user:
        raise HTTPException(400, "User not found")
    result = mock._build_token_response(user, request)
    now = int(time.time())
    result["id_token"] = mock.keys.sign_token({
        "iss": mock._issuer(request), "sub": mock._user_sub(user),
        "aud": mock.cfg.client_id, "iat": now, "exp": now + mock.cfg.access_token_ttl,
        "nonce": entry["nonce"], "email": user.email, "name": user.name,
        "preferred_username": user.username,
    })
    return JSONResponse(result)


def wrap(endpoint):
    @wraps(endpoint)
    async def call(**kwargs):
        params = dict(kwargs["request"].query_params)
        params.update({k: v for k, v in kwargs.items() if isinstance(v, str)})
        if endpoint.__name__ in {"auth_get", "auth_post"}:
            if params.get("client_id") != mock.cfg.client_id or params.get("redirect_uri") != CALLBACK:
                raise HTTPException(400, "Invalid client or redirect URI")
            if (params.get("response_type") != "code" or "openid" not in params.get("scope", "").split()
                    or not params.get("nonce") or not params.get("code_challenge")
                    or params.get("code_challenge_method") != "S256"):
                raise HTTPException(400, "Authorization code flow with nonce and S256 PKCE is required")
        context_token = parameters.set(params)
        try:
            return await endpoint(**kwargs)
        finally:
            parameters.reset(context_token)
    return call


mock._issue_code = issue_code
mock._handle_code_grant = handle_code_grant
for route in mock.app.routes:
    if getattr(route, "name", "") in {"auth_get", "auth_post", "token"}:
        route.dependant.call = wrap(route.dependant.call)

if __name__ == "__main__":
    mock.main()

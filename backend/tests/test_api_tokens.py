import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import ApiToken, BrowserSession, ExternalIdentity, ProjectMember, User
from app.providers import ExternalProfile
from app.security import token_hash
from conftest import grant_project_access


def issue(client, scopes=None, path="/api/v1/tokens"):
    response = client.post(path, json={"name": "Integration test", "scopes": scopes or ["read"]})
    assert response.status_code == 201, response.text
    return response.json()


def bearer(secret):
    return TestClient(app, headers={"Authorization": f"Bearer {secret}"})


def project(admin, key="APP", visibility="organization"):
    response = admin.post("/api/v1/projects", json={"key": key, "name": key, "visibility": visibility})
    assert response.status_code == 201
    if visibility == 'organization':
        grant_project_access(admin, response.json()['id'])
    return response.json()


def item(admin, pid):
    response = admin.post(f"/api/v1/projects/{pid}/items", json={"title": "API task", "description": "- [ ] Verify token"})
    assert response.status_code == 201
    return response.json()


def bot(admin, role="member"):
    response = admin.post("/api/v1/bots", json={"name": "Automation bot", "role": role})
    assert response.status_code == 201
    return response.json()


def test_secret_is_one_time_hashed_and_last_used_is_recorded(env):
    factory, client, people = env
    member = client("member")
    created = issue(member)
    secret = created["token"]
    assert secret.startswith("itr_") and created["prefix"] == secret[:12]
    with factory() as db:
        row = db.get(ApiToken, created["id"])
        assert row.secret_hash == token_hash(secret) and row.secret_hash != secret
        assert row.created_by_id == row.user_id == people["member"]
        assert row.last_used_at is None
    listed = member.get("/api/v1/tokens").json()[0]
    assert "token" not in listed and "secret_hash" not in listed and secret not in str(listed)
    response = bearer(secret).get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["user"]["id"] == people["member"]
    assert response.json()["csrf_token"] is None and response.json()["auth_method"] == "token"
    assert "set-cookie" not in response.headers
    assert member.get("/api/v1/tokens").json()[0]["last_used_at"] is not None


def test_scopes_and_csrf_bypass_apply_only_to_valid_bearer(env):
    _, client, _ = env
    admin, member = client("administrator"), client("member")
    p = project(admin)
    i = item(admin, p["id"])
    read = bearer(issue(member)["token"])
    write = bearer(issue(member, ["write"])["token"])
    assert read.get(f"/api/v1/items/{i['id']}").status_code == 200
    assert read.post("/api/v1/references/resolve", json={"tickets": [i["id"]]}).status_code == 200
    assert read.post(f"/api/v1/items/{i['id']}/comments", json={"body": "Blocked"}).status_code == 403
    assert read.put(f"/api/v1/items/{i['id']}", json={"title": "Blocked"}).status_code == 403
    assert read.patch(f"/api/v1/items/{i['id']}/checklist/0", json={"checked": True, "version": i["description_version"]}).status_code == 403
    assert read.post(f"/api/v1/items/{i['id']}/attachments", files={"file": ("x.txt", b"x")}).status_code == 403
    assert write.post(f"/api/v1/items/{i['id']}/comments", json={"body": "Posted using API"}).status_code == 201
    assert write.patch(f"/api/v1/items/{i['id']}/checklist/0", json={"checked": True, "version": i["description_version"]}).status_code == 200
    uploaded = write.post(f"/api/v1/items/{i['id']}/attachments", files={"file": ("note.txt", b"api file")})
    assert uploaded.status_code == 201
    assert read.get(uploaded.json()["url"]).content == b"api file"
    member.headers.pop("X-CSRF-Token")
    assert member.post(f"/api/v1/items/{i['id']}/comments", json={"body": "Missing CSRF"}).status_code == 403


@pytest.mark.parametrize("header", ["Bearer invalid", "Bearer itr_" + "x" * 54, "Basic anything", ""])
def test_bad_authorization_never_falls_back_to_browser_cookie(env, header):
    _, client, _ = env
    admin = client("administrator")
    admin.headers["Authorization"] = header
    assert admin.get("/api/v1/projects").status_code == 401
    assert admin.post("/api/v1/projects", json={"key": "APP", "name": "Bad fallback"}).status_code == 401
    assert admin.get("/api/v1/auth/me").status_code == 401


def test_token_identity_wins_over_admin_cookie_and_cannot_manage_credentials(env):
    _, client, people = env
    admin, member = client("administrator"), client("member")
    created = issue(member, ["write"])
    admin.headers["Authorization"] = "Bearer " + created["token"]
    assert admin.get("/api/v1/auth/me").json()["user"]["id"] == people["member"]
    assert admin.post("/api/v1/projects", json={"key": "APP", "name": "No escalation"}).status_code == 403
    for path in ["/api/v1/tokens", "/api/v1/bots"]:
        assert admin.get(path).status_code == 403
        assert admin.post(path, json={"name": "Forbidden"}).status_code == 403
    assert admin.delete(f"/api/v1/tokens/{created['id']}").status_code == 403
    assert admin.get("/api/v1/auth/oidc/login").status_code == 403
    assert admin.get("/api/v1/auth/oidc/callback").status_code == 403
    assert admin.post("/api/v1/auth/logout").status_code == 403


def test_owner_only_revocation_expiry_and_account_deactivation(env):
    factory, client, people = env
    member, reader = client("member"), client("reader")
    created = issue(member)
    api = bearer(created["token"])
    assert reader.delete(f"/api/v1/tokens/{created['id']}").status_code == 404
    assert api.get("/api/v1/projects").status_code == 200
    assert member.delete(f"/api/v1/tokens/{created['id']}").json()["status"] == "revoked"
    assert api.get("/api/v1/projects").status_code == 401
    expired = issue(member)
    with factory() as db:
        db.get(ApiToken, expired["id"]).expires_at = int(time.time()) - 1
        db.commit()
    assert bearer(expired["token"]).get("/api/v1/projects").status_code == 401
    active = issue(member)
    with factory() as db:
        db.get(User, people["member"]).active = False
        db.commit()
    assert bearer(active["token"]).get("/api/v1/projects").status_code == 401


def test_tokens_never_exceed_current_owner_permissions(env):
    factory, client, people = env
    admin, member, reader = client("administrator"), client("member"), client("reader")
    private = project(admin, visibility="private")
    hidden = item(admin, private["id"])
    public = project(admin, key="PUBLIC")
    visible = item(admin, public["id"])
    created = issue(member, ["write"])
    api = bearer(created["token"])
    assert api.get(f"/api/v1/items/{hidden['id']}").status_code == 404
    assert api.post("/api/v1/references/resolve", json={"tickets": [hidden["id"]]}).json()["tickets"] == []
    reader_api = bearer(issue(reader, ['write'])['token'])
    assert reader_api.post(f"/api/v1/items/{visible['id']}/comments", json={'body': 'No write'}).status_code == 403
    with factory() as db:
        db.get(ProjectMember, (public['id'], people["member"])).role = "read-only"
        db.commit()
    assert api.post(f"/api/v1/items/{visible['id']}/comments", json={"body": "Role downgraded"}).status_code == 403
    with factory() as db:
        db.get(User, people["member"]).role = None
        db.commit()
    assert api.get("/api/v1/projects").status_code == 401


@pytest.mark.parametrize("values", [{"name": "   "}, {"scopes": []}, {"scopes": ["administrator"]},
    {"expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()},
    {"expires_at": (datetime.now(timezone.utc) + timedelta(days=366)).isoformat()},
    {"expires_at": "2028-01-01T12:00:00"}, {"user_id": "another-user"}])
def test_token_input_validation(env, values):
    _, client, _ = env
    assert client("member").post("/api/v1/tokens", json={"name": "Test token", **values}).status_code == 422


def test_only_browser_admin_can_manage_bots(env):
    _, client, _ = env
    for role in ["member", "reader", "outsider"]:
        assert client(role).get("/api/v1/bots").status_code == 403
        assert client(role).post("/api/v1/bots", json={"name": "No bot"}).status_code == 403
    admin = client("administrator")
    credential = issue(admin, ["write"])
    assert bearer(credential["token"]).post("/api/v1/bots", json={"name": "No bot"}).status_code == 403
    assert admin.post("/api/v1/bots", json={"name": "No administrator bot", "role": "administrator"}).status_code == 422


def test_bot_requires_explicit_project_access_and_records_bot_actor(env):
    factory, client, _ = env
    admin = client("administrator")
    p = project(admin)
    other = project(admin, key="OTHER")
    i = item(admin, p["id"])
    account = bot(admin)
    created = issue(admin, ["write"], f"/api/v1/bots/{account['id']}/tokens")
    api = bearer(created["token"])
    assert api.get("/api/v1/projects").json() == []
    assert api.get(f"/api/v1/items/{i['id']}").status_code == 404
    assert admin.put(f"/api/v1/bots/{account['id']}/projects/{p['id']}", json={"role": "reporter"}).status_code == 200
    assert [row["id"] for row in api.get("/api/v1/projects").json()] == [p["id"]]
    assert api.get(f"/api/v1/projects/{other['id']}/items").status_code == 404
    assert len(api.get("/api/v1/references/tickets").json()) == 1
    posted = api.post(f"/api/v1/items/{i['id']}/comments", json={"body": "Automated summary"})
    assert posted.status_code == 201
    entries = admin.get(f"/api/v1/items/{i['id']}/discussion").json()
    entry = next(row for row in entries if row["id"] == posted.json()["id"])
    assert entry["author"] == "Automation bot" and entry["author_is_bot"]
    with factory() as db:
        assert db.scalar(select(ExternalIdentity).where(ExternalIdentity.user_id == account["id"])) is None
    assert api.post("/api/v1/tokens", json={"name": "Cannot mint credentials"}).status_code == 403
    assert api.put("/api/v1/users/me", json={"name": "No rename", "email": "bot@example.test"}).status_code == 403
    assert admin.delete(f"/api/v1/bots/{account['id']}/projects/{p['id']}").status_code == 200
    assert api.get(f"/api/v1/items/{i['id']}").status_code == 404


def test_bot_read_only_ceiling_disable_and_reenable_do_not_restore_old_tokens(env):
    _, client, _ = env
    admin = client("administrator")
    p = project(admin)
    i = item(admin, p["id"])
    account = bot(admin)
    created = issue(admin, ["write"], f"/api/v1/bots/{account['id']}/tokens")
    api = bearer(created["token"])
    admin.put(f"/api/v1/bots/{account['id']}/projects/{p['id']}", json={"role": "read-only"})
    edit = {"name": account["name"], "role": "member", "active": True}
    assert admin.put(f"/api/v1/bots/{account['id']}", json=edit).status_code == 200
    assert api.get(f"/api/v1/items/{i['id']}").status_code == 200
    assert api.post(f"/api/v1/items/{i['id']}/comments", json={"body": "No write"}).status_code == 403
    assert admin.put(f"/api/v1/bots/{account['id']}", json={**edit, "active": False}).status_code == 200
    assert api.get("/api/v1/projects").status_code == 401
    assert admin.get(f"/api/v1/bots/{account['id']}/tokens").json()[0]["status"] == "revoked"
    assert admin.post(f"/api/v1/bots/{account['id']}/tokens", json={"name": "Inactive"}).status_code == 409
    assert admin.put(f"/api/v1/bots/{account['id']}", json=edit).status_code == 200
    assert api.get("/api/v1/projects").status_code == 401


def test_bot_cannot_use_a_browser_session_or_oidc(env):
    factory, client, people = env
    admin = client("administrator")
    account = bot(admin)
    with factory() as db:
        user = db.get(User, people["member"])
        user.is_bot = True
        db.add(ExternalIdentity(user_id=account["id"], issuer="https://identity.example", subject="bot-subject"))
        db.commit()
    assert client("member").get("/api/v1/projects").status_code == 401

    class Provider:
        async def identity(self, request):
            return ExternalProfile("https://identity.example", "bot-subject", "Automation bot", "")

    with client() as visitor:
        app.state.provider = Provider()
        assert visitor.get("/api/v1/auth/oidc/callback", follow_redirects=False).status_code == 403
        assert visitor.get("/api/v1/auth/me").json()["user"] is None

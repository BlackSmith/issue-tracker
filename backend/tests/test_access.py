import time

from sqlalchemy import select

from app.main import settings
from app.models import BrowserSession, ExternalIdentity, ProjectMember, User
from app.providers import ExternalProfile
from app.security import token_hash
from conftest import grant_project_access


def project(client, visibility="organization", key="APP"):
    response = client.post("/api/v1/projects", json={"key": key, "name": "Application", "visibility": visibility})
    assert response.status_code == 201, response.text
    if visibility == 'organization':
        grant_project_access(client, response.json()['id'])
    return response.json()["id"]


def item(client, project_id):
    path = f"/api/v1/projects/{project_id}/labels"
    if not any(label["name"] == "auth" for label in client.get(path).json()):
        assert client.post(path, json={"name": "auth", "color": "#16a34a", "description": "Authentication"}).status_code == 201
    response = client.post(f"/api/v1/projects/{project_id}/items", json={"title": "Fix login", "labels": ["auth"]})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_anonymous_and_nonmember_access(env):
    _, client, _ = env
    assert client().get("/api/v1/projects").status_code == 401
    assert client("outsider").get("/api/v1/projects").status_code == 403


def test_csrf_and_origin_are_required(env):
    _, client, _ = env
    admin = client("administrator")
    admin.headers.pop("X-CSRF-Token")
    assert admin.post("/api/v1/projects", json={"key": "APP", "name": "App"}).status_code == 403
    admin.headers["X-CSRF-Token"] = "test-csrf"
    admin.headers["Origin"] = "https://other.example"
    assert admin.post("/api/v1/projects", json={"key": "APP", "name": "App"}).status_code == 403


def test_private_project_and_attachments_are_isolated(env):
    _, client, _ = env
    admin, member = client("administrator"), client("member")
    pid = project(admin, "private")
    iid = item(admin, pid)
    uploaded = admin.post(f"/api/v1/items/{iid}/attachments", files={"file": ("note.txt", b"private")})
    assert uploaded.status_code == 201
    url = uploaded.json()["url"]
    assert member.get("/api/v1/projects").json() == []
    assert member.get(f"/api/v1/projects/{pid}/items").status_code == 404
    assert member.get(f"/api/v1/items/{iid}").status_code == 404
    assert member.get(f"/api/v1/items/{iid}/discussion").status_code == 404
    assert member.get(url).status_code == 404
    assert admin.get(url).content == b"private"


def test_reader_cannot_mutate_or_upload(env):
    _, client, _ = env
    admin, reader = client("administrator"), client("reader")
    pid = project(admin)
    iid = item(admin, pid)
    assert reader.get(f"/api/v1/items/{iid}").status_code == 200
    assert reader.post(f"/api/v1/projects/{pid}/items", json={"title": "No"}).status_code == 403
    assert reader.put(f"/api/v1/items/{iid}", json={"title": "No"}).status_code == 403
    assert reader.patch(f"/api/v1/items/{iid}", json={"priority": "High"}).status_code == 403
    assert reader.post(f"/api/v1/items/{iid}/comments", json={"body": "No"}).status_code == 403
    assert reader.post(f"/api/v1/items/{iid}/attachments", files={"file": ("x", b"x")}).status_code == 403


def test_partial_item_edits_preserve_other_fields_and_record_actual_changes(env):
    _, client, _ = env
    admin = client("administrator")
    pid = project(admin)
    path = f"/api/v1/items/{item(admin, pid)}"
    original = admin.get(path).json()
    updated = admin.patch(path, json={"priority": "High"})
    assert updated.status_code == 200
    assert updated.json()["priority"] == "High"
    for field in ("title", "description", "type", "status", "labels", "due_date"):
        assert updated.json()[field] == original[field]
    entries = admin.get(path + "/discussion").json()
    assert entries[-1]["body"] == 'updated priority from "Medium" to "High"'
    assert admin.patch(path, json={"priority": "High"}).status_code == 200
    assert admin.get(path + "/discussion").json() == entries
    assert admin.patch(path, json={"due_date": "2026-12-01"}).json()["due_date"] == "2026-12-01"
    assert admin.patch(path, json={"due_date": None}).json()["due_date"] is None
    assert admin.post(f"/api/v1/projects/{pid}/labels", json={"name": "one", "color": "#123456"}).status_code == 201
    assert admin.patch(path, json={"labels": [" one ", "one"]}).json()["labels"] == ["one"]
    assert admin.patch(path, json={"labels": []}).json()["labels"] == []


def test_partial_item_edit_validation_and_access(env):
    _, client, _ = env
    admin, member = client("administrator"), client("member")
    path = f"/api/v1/items/{item(admin, project(admin, 'private'))}"
    assert member.patch(path, json={"priority": "High"}).status_code == 404
    assert client().patch(path, json={"priority": "High"}).status_code == 403
    for payload in ({"title": " "}, {"title": None}, {"description": None}, {"labels": None},
                    {"status": "Unknown"}, {"priority": "Unknown"}, {"due_date": "invalid"},
                    {"labels": [" "]}, {"labels": ["x" * 51]}, {"author_id": "other"}):
        assert admin.patch(path, json=payload).status_code == 422
    admin.headers.pop("X-CSRF-Token")
    assert admin.patch(path, json={"priority": "High"}).status_code == 403


def test_explicit_project_roles_control_contribution(env):
    _, client, people = env
    admin, member, reader = client("administrator"), client("member"), client("reader")
    pid = project(admin, "private")
    assert admin.put(f"/api/v1/projects/{pid}/members", json={"user_id": people["member"], "role": "read-only"}).status_code == 200
    assert member.get(f"/api/v1/projects/{pid}/items").status_code == 200
    assert member.post(f"/api/v1/projects/{pid}/items", json={"title": "No"}).status_code == 403
    assert admin.put(f"/api/v1/projects/{pid}/members", json={"user_id": people["reader"], "role": "owner"}).status_code == 200
    assert admin.put(f"/api/v1/projects/{pid}/members", json={"user_id": people["reader"], "role": "read-only"}).status_code == 200
    assert reader.post(f"/api/v1/projects/{pid}/items", json={"title": "No"}).status_code == 403
    assert member.put(f"/api/v1/projects/{pid}/members", json={"user_id": people["member"], "role": "owner"}).status_code == 403


def test_member_management_and_revoked_private_access(env):
    _, client, people = env
    admin, member = client("administrator"), client("member")
    pid = project(admin, "private")
    iid = item(admin, pid)
    url = admin.post(f"/api/v1/items/{iid}/attachments", files={"file": ("note.txt", b"private")}).json()["url"]
    path = f"/api/v1/projects/{pid}/members"
    creator = admin.get(path).json()
    assert len(creator) == 1 and creator[0]['user_id'] == people['administrator']
    assert admin.put(path, json={"user_id": people["member"], "role": "reporter"}).status_code == 200
    rows = admin.get(path).json()
    assert len(rows) == 2
    assert next(row for row in rows if row['user_id'] == people['member']) == {"user_id": people["member"], "name": "member", "email": "member@example.test",
                       "role": "reporter", "organization_role": "member", "inherited": False, "active": True, "is_bot": False, "avatar_url": None}
    assert member.post(f"/api/v1/projects/{pid}/items", json={"title": "Allowed"}).status_code == 201
    assert member.get(path).status_code == 403
    assert member.delete(f"{path}/{people['member']}").status_code == 403
    assert admin.put(path, json={"user_id": people["member"], "role": "read-only"}).status_code == 200
    assert next(row for row in admin.get(path).json() if row['user_id'] == people['member'])["role"] == "read-only"
    assert member.post(f"/api/v1/projects/{pid}/items", json={"title": "Denied"}).status_code == 403
    assert member.get(url).status_code == 200
    assert admin.delete(f"{path}/{people['member']}").status_code == 200
    assert admin.get(path).json() == creator
    assert member.get(f"/api/v1/items/{iid}").status_code == 404
    assert member.get(url).status_code == 404
    assert admin.delete(f"{path}/{people['member']}").status_code == 404


def test_membership_removal_revokes_access_and_requires_csrf(env):
    _, client, people = env
    admin, member, reader = client("administrator"), client("member"), client("reader")
    pid = project(admin)
    path = f"/api/v1/projects/{pid}/members"
    assert member.get(path).status_code == 403
    assert reader.get(path).status_code == 403
    assert client().get(path).status_code == 401
    assert admin.put(path, json={"user_id": people["member"], "role": "read-only"}).status_code == 200
    admin.headers.pop("X-CSRF-Token")
    assert admin.delete(f"{path}/{people['member']}").status_code == 403
    admin.headers["X-CSRF-Token"] = "test-csrf"
    assert admin.delete(f"{path}/{people['member']}").status_code == 200
    assert member.post(f"/api/v1/projects/{pid}/items", json={"title": "No implicit access"}).status_code == 404
    assert admin.get("/api/v1/projects/missing/members").status_code == 404
    assert admin.delete(f"/api/v1/projects/missing/members/{people['member']}").status_code == 404


def test_inactive_members_remain_visible_and_can_be_removed(env):
    factory, client, people = env
    admin = client("administrator")
    pid = project(admin, "private")
    path = f"/api/v1/projects/{pid}/members"
    assert admin.put(path, json={"user_id": people["member"], "role": "reporter"}).status_code == 200
    with factory() as db:
        db.get(User, people["member"]).active = False
        db.commit()
    assert next(row for row in admin.get(path).json() if row['user_id'] == people['member'])["active"] is False
    assert admin.delete(f"{path}/{people['member']}").status_code == 200


def test_session_hash_expiry_logout_and_deactivated_user(env):
    factory, client, people = env
    member = client("member")
    token = member.cookies.get(settings.session_cookie)
    with factory() as db:
        assert db.get(BrowserSession, token) is None
        assert db.get(BrowserSession, token_hash(token)) is not None
    assert member.post("/api/v1/auth/logout").status_code == 200
    with factory() as db:
        assert db.get(BrowserSession, token_hash(token)) is None
    assert member.get("/api/v1/projects").status_code == 401
    expired = client("member")
    with factory() as db:
        row = db.get(BrowserSession, token_hash(expired.cookies.get(settings.session_cookie)))
        row.expires_at = int(time.time()) - 1
        db.commit()
    assert expired.get("/api/v1/projects").status_code == 401
    disabled = client("member")
    with factory() as db:
        db.get(User, people["member"]).active = False
        db.commit()
    assert disabled.get("/api/v1/projects").status_code == 401


def test_comment_activity_filter_pagination_and_numbering(env):
    _, client, _ = env
    admin = client("administrator")
    pid = project(admin)
    iid = item(admin, pid)
    second = admin.post(f"/api/v1/projects/{pid}/items", json={"title": "Documentation", "status": "Done"}).json()
    assert second["reference"] == "APP-2"
    result = admin.get(f"/api/v1/projects/{pid}/items?q=login&status=Open").json()
    assert result["total"] == 1 and result["items"][0]["id"] == iid
    assert admin.get(f"/api/v1/projects/{pid}/items?per_page=1&page=2").json()["total"] == 2
    assert admin.post(f"/api/v1/items/{iid}/comments", json={"body": "A comment"}).status_code == 201
    discussion = admin.get(f"/api/v1/items/{iid}/discussion").json()
    assert {entry["kind"] for entry in discussion} == {"activity", "comment"}
    assert admin.post(f"/api/v1/items/{iid}/comments", json={"body": "  "}).status_code == 422
    assert admin.post(f"/api/v1/projects/{pid}/items", json={"title": "  "}).status_code == 422


def test_upload_size_cleanup_and_safe_download(env, monkeypatch):
    _, client, _ = env
    admin = client("administrator")
    pid = project(admin)
    iid = item(admin, pid)
    monkeypatch.setattr(settings, "max_upload_bytes", 4)
    assert admin.post(f"/api/v1/items/{iid}/attachments", files={"file": ("large", b"12345")}).status_code == 413
    assert list(settings.attachment_dir.iterdir()) == []
    uploaded = admin.post(f"/api/v1/items/{iid}/attachments", files={"file": ("../../x.html", b"test")}).json()
    response = admin.get(uploaded["url"])
    assert uploaded["filename"] == "x.html"
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.headers["x-content-type-options"] == "nosniff"


def test_oidc_identity_never_merges_matching_email_and_rotates_session(env):
    factory, client, people = env
    from app.main import app

    class Provider:
        async def identity(self, request):
            return ExternalProfile("https://oidc.example", "new-subject", "New person", "member@example.test")

    c = client()
    with c:
        app.state.provider = Provider()
        c.get("/api/v1/auth/me")
        old = c.cookies.get(settings.session_cookie)
        response = c.get("/api/v1/auth/oidc/callback", follow_redirects=False)
        assert response.status_code == 303
        assert c.cookies.get(settings.session_cookie) != old
        user = c.get("/api/v1/auth/me").json()["user"]
        assert user["id"] != people["member"] and user["role"] is None
        assert c.get("/api/v1/projects").status_code == 403
        with factory() as db:
            assert db.get(BrowserSession, token_hash(old)) is None
            identity = db.scalar(select(ExternalIdentity).where(ExternalIdentity.subject == "new-subject"))
            assert identity.user_id == user["id"]


def test_invalid_oidc_callback_does_not_authenticate(env):
    _, client, _ = env
    from app.main import app

    class Provider:
        async def identity(self, request):
            raise ValueError("Invalid state or signature")

    with client() as c:
        app.state.provider = Provider()
        response = c.get("/api/v1/auth/oidc/callback?state=forged", follow_redirects=False)
        assert response.status_code == 303 and "auth_error" in response.headers["location"]
        assert c.get("/api/v1/auth/me").json()["user"] is None

from datetime import timedelta

from sqlalchemy import select

from app import attachments
from app.main import settings
from app.models import Attachment, WorkItem, utcnow
from test_access import item, project


def upload(client, path, name="draft.txt"):
    response = client.post(path, files={"file": (name, b"draft bytes")})
    assert response.status_code == 201, response.text
    return response.json()


def test_new_ticket_claims_uploads_only_after_successful_save(env):
    factory, client, _ = env
    admin, member = client("administrator"), client("member")
    pid = project(admin)
    a = upload(admin, f"/api/v1/projects/{pid}/attachments")
    assert admin.get(a["url"]).content == b"draft bytes"
    assert member.get(a["url"]).status_code == 404
    path = f"/api/v1/projects/{pid}/items"
    body = {"title": "Draft", "description": f'[{a["filename"]}]({a["url"]})'}
    assert admin.post(path, json={**body, "title": ""}).status_code == 422
    with factory() as db:
        assert db.get(Attachment, a["id"]).pending
    created = admin.post(path, json=body)
    assert created.status_code == 201, created.text
    iid = created.json()["id"]
    assert member.get(a["url"]).status_code == 200
    assert len(admin.get(f"/api/v1/items/{iid}/attachments").json()) == 1
    with factory() as db:
        row = db.get(Attachment, a["id"])
        assert not row.pending and row.item_id == iid


def test_comment_and_description_confirm_only_referenced_uploads(env):
    _, client, _ = env
    admin = client("administrator")
    iid = item(admin, project(admin))
    path = f"/api/v1/items/{iid}"
    a, b, unused = [upload(admin, path + "/attachments?pending=true", name) for name in ["a.txt", "b.png", "unused.txt"]]
    assert admin.get(path + "/attachments").json() == []
    assert not any(row["body"].startswith("uploaded ") for row in admin.get(path + "/discussion").json())
    assert admin.post(path + "/comments", json={"body": f'[a]({a["url"]})'}).status_code == 201
    assert admin.patch(path, json={"description": f'![b]({b["url"]})'}).status_code == 200
    assert {row["id"] for row in admin.get(path + "/attachments").json()} == {a["id"], b["id"]}
    entries = admin.get(path + "/discussion").json()
    assert sum(row["body"].startswith("uploaded ") for row in entries) == 2
    assert admin.patch(path, json={"description": f'![b]({b["url"]})'}).status_code == 200
    assert len(admin.get(path + "/discussion").json()) == len(entries)


def test_pending_upload_permissions_and_claim_boundaries(env):
    factory, client, _ = env
    admin, member, reader = client("administrator"), client("member"), client("reader")
    pid = project(admin)
    private = project(admin, "private", "PRIV")
    endpoint = f"/api/v1/projects/{pid}/attachments"
    assert reader.post(endpoint, files={"file": ("x", b"x")}).status_code == 403
    assert member.post(f"/api/v1/projects/{private}/attachments", files={"file": ("x", b"x")}).status_code == 404
    a = upload(admin, endpoint)
    body = {"title": "Claim", "description": f'[a]({a["url"]})'}
    assert member.post(f"/api/v1/projects/{pid}/items", json=body).status_code == 404
    assert admin.post(f"/api/v1/projects/{private}/items", json=body).status_code == 404
    with factory() as db:
        assert not list(db.scalars(select(WorkItem)))
        assert db.get(Attachment, a["id"]).pending
    first, second = item(admin, pid), item(admin, pid)
    b = upload(admin, f"/api/v1/items/{first}/attachments?pending=true")
    assert admin.post(f"/api/v1/items/{second}/comments", json={"body": f'[b]({b["url"]})'}).status_code == 404
    no_csrf = client("administrator")
    no_csrf.headers.pop("X-CSRF-Token")
    assert no_csrf.post(endpoint, files={"file": ("x", b"x")}).status_code == 403


def test_cleanup_removes_only_old_unconfirmed_files(env, monkeypatch):
    factory, client, _ = env
    monkeypatch.setattr(attachments, "SessionLocal", factory)
    admin = client("administrator")
    pid = project(admin)
    iid = item(admin, pid)
    endpoint = f"/api/v1/projects/{pid}/attachments"
    abandoned, recent = upload(admin, endpoint), upload(admin, endpoint)
    comment = upload(admin, f"/api/v1/items/{iid}/attachments?pending=true")
    saved = upload(admin, endpoint)
    assert admin.patch(f"/api/v1/items/{iid}", json={"description": f'[saved]({saved["url"]})'}).status_code == 200
    legacy = upload(admin, f"/api/v1/items/{iid}/attachments")
    with factory() as db:
        for a in [abandoned, comment, saved, legacy]:
            db.get(Attachment, a["id"]).created_at = utcnow() - timedelta(hours=25)
        db.commit()
    assert attachments.cleanup_attachments() == 2
    for a in [abandoned, comment]:
        assert not (settings.attachment_dir / a["id"]).exists()
        assert admin.get(a["url"]).status_code == 404
    for a in [recent, saved, legacy]:
        assert admin.get(a["url"]).status_code == 200
    assert attachments.cleanup_attachments() == 0
    failed = admin.post(f"/api/v1/projects/{pid}/items", json={"title": "Expired", "description": f'[a]({abandoned["url"]})'})
    assert failed.status_code == 409


def test_pending_size_limit_removes_partial_file(env, monkeypatch):
    _, client, _ = env
    admin = client("administrator")
    pid = project(admin)
    monkeypatch.setattr(settings, "max_upload_bytes", 2)
    assert admin.post(f"/api/v1/projects/{pid}/attachments", files={"file": ("x", b"123")}).status_code == 413
    assert list(settings.attachment_dir.iterdir()) == []

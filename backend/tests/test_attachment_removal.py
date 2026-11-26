from app.main import settings
from app.models import Attachment
from test_access import item, project
from test_api_tokens import bearer, issue
from test_pending_attachments import upload
from test_ticket_visibility import set_restriction


def test_writer_removes_another_users_attachment_and_records_activity(env):
    factory, client, _ = env
    admin, member = client("administrator"), client("member")
    iid = item(admin, project(admin))
    path = f"/api/v1/items/{iid}"
    removed = upload(admin, path + "/attachments", "remove.txt")
    retained = upload(admin, path + "/attachments", "keep.txt")
    before = admin.get(path).json()["updated_at"]
    response = member.delete(path + "/attachments/" + removed["id"])
    assert response.status_code == 204, response.text
    assert response.content == b""
    assert admin.get(removed["url"]).status_code == 404
    assert not (settings.attachment_dir / removed["id"]).exists()
    with factory() as db:
        assert db.get(Attachment, removed["id"]) is None
    assert [a["id"] for a in admin.get(path + "/attachments").json()] == [retained["id"]]
    assert admin.get(retained["url"]).content == b"draft bytes"
    activity = [e for e in admin.get(path + "/discussion").json() if e["body"] == "removed attachment remove.txt"]
    assert len(activity) == 1 and activity[0]["author"] == "member"
    assert admin.get(path).json()["updated_at"] != before
    assert member.delete(path + "/attachments/" + removed["id"]).status_code == 404


def test_removal_enforces_permissions_scope_csrf_and_pending_state(env):
    _, client, _ = env
    admin, member, reader = client("administrator"), client("member"), client("reader")
    pid = project(admin)
    iid, other = item(admin, pid), item(admin, pid)
    path = f"/api/v1/items/{iid}"
    attachment = upload(admin, path + "/attachments")
    endpoint = path + "/attachments/" + attachment["id"]
    assert client().delete(endpoint).status_code == 403
    assert reader.delete(endpoint).status_code == 403
    no_csrf = client("administrator")
    no_csrf.headers.pop("X-CSRF-Token")
    assert no_csrf.delete(endpoint).status_code == 403
    assert admin.delete(f'/api/v1/items/{other}/attachments/{attachment["id"]}').status_code == 404
    pending = upload(admin, path + "/attachments?pending=true")
    assert admin.delete(path + "/attachments/" + pending["id"]).status_code == 404
    set_restriction(admin, pid, True)
    assert member.delete(endpoint).status_code == 404
    assert admin.get(attachment["url"]).status_code == 200
    assert admin.delete(endpoint).status_code == 204


def test_removal_requires_write_token_scope(env):
    _, client, _ = env
    admin = client("administrator")
    iid = item(admin, project(admin))
    path = f"/api/v1/items/{iid}"
    attachment = upload(admin, path + "/attachments")
    endpoint = path + "/attachments/" + attachment["id"]
    read_token = issue(admin, scopes=["read"])["token"]
    write_token = issue(admin, scopes=["read", "write"])["token"]
    assert bearer(read_token).delete(endpoint).status_code == 403
    assert bearer(write_token).delete(endpoint).status_code == 204


def test_removed_editor_attachment_keeps_existing_content_editable(env):
    _, client, _ = env
    admin = client("administrator")
    pid = project(admin)
    iid = item(admin, pid)
    path = f"/api/v1/items/{iid}"
    attachment = upload(admin, path + "/attachments?pending=true")
    description = f'Existing description [{attachment["filename"]}]({attachment["url"]})'
    assert admin.patch(path, json={"description": description}).status_code == 200
    assert admin.post(path + "/comments", json={"body": description}).status_code == 201
    assert admin.delete(path + "/attachments/" + attachment["id"]).status_code == 204
    assert admin.patch(path, json={"description": description + " More context."}).status_code == 200
    assert admin.get(path).json()["description"] == description + " More context."
    assert any(e["kind"] == "comment" and e["body"] == description
               for e in admin.get(path + "/discussion").json())
    other = item(admin, pid)
    assert admin.patch(f"/api/v1/items/{other}", json={"description": description}).status_code == 409
    assert admin.post(path + "/comments", json={"body": description}).status_code == 409

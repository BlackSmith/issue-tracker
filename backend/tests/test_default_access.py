import pytest

from app import mail, notifications
from app.models import User
from test_api_tokens import bearer, bot, issue
from test_notifications import notifying, queued


def settings(access=None, **values):
    return {"name": "Default access", "description": "", "visibility": "private",
            "default_access": access, **values}


@pytest.mark.parametrize("access", ["reporter", "read-only"])
def test_default_access_permissions_references_attachments_and_revocation(env, access):
    _, client, people = env
    admin, member = client("administrator"), client("member")
    project = admin.post("/api/v1/projects", json={"key": "DA", **settings()}).json()
    path = f'/api/v1/projects/{project["id"]}'
    item = admin.post(path + "/items", json={"title": "Shared ticket"}).json()
    item_path = f'/api/v1/items/{item["id"]}'
    upload = admin.post(item_path + "/attachments", files={"file": ("test.txt", b"shared")}).json()
    assert member.get("/api/v1/projects").json() == []
    assert member.get(item_path).status_code == 404
    assert admin.put(path, json=settings(access)).status_code == 200
    visible = member.get("/api/v1/projects").json()[0]
    assert visible["default_access"] == access
    assert visible["can_write"] is (access == "reporter")
    assert visible["can_manage"] is False
    assert member.get(path + "/items").json()["total"] == 1
    assert member.get(item_path).status_code == 200
    assert member.get(f'/api/v1/projects/by-slug/DA/items/{item["number"]}').status_code == 200
    assert member.get(upload["url"]).content == b"shared"
    assert member.get("/api/v1/references/tickets").json()[0]["id"] == item["id"]
    assert member.post("/api/v1/references/resolve", json={"tickets": [item["id"]]}).json()["tickets"][0]["id"] == item["id"]
    assert people["member"] in {u["id"] for u in member.get("/api/v1/references/users", params={"project_id": project["id"]}).json()}
    expected = 201 if access == "reporter" else 403
    assert member.post(path + "/items", json={"title": "Member ticket"}).status_code == expected
    assert member.post(item_path + "/comments", json={"body": "Comment"}).status_code == expected
    assert member.post(item_path + "/attachments", files={"file": ("x", b"x")}).status_code == expected
    assert member.put(path, json=settings(None)).status_code == 403
    assert member.get(path + "/members").status_code == 403
    assert client("outsider").get(path + "/items").status_code == 403
    assert client().get(path + "/items").status_code == 401
    assert admin.put(path, json=settings(None)).status_code == 200
    assert member.get("/api/v1/projects").json() == []
    for url in (path + "/items", item_path, upload["url"]):
        assert member.get(url).status_code == 404
    assert member.get("/api/v1/references/tickets").json() == []


def test_explicit_roles_override_default_and_owners_manage_setting(env):
    _, client, people = env
    admin, member = client("administrator"), client("member")
    project = admin.post("/api/v1/projects", json={"key": "DA", **settings("reporter")}).json()
    path = f'/api/v1/projects/{project["id"]}'
    assert admin.put(path + "/members", json={"user_id": people["member"], "role": "read-only"}).status_code == 200
    assert member.get("/api/v1/projects").json()[0]["can_write"] is False
    assert people["member"] not in {u["id"] for u in admin.get(path + "/assignees").json()}
    assert admin.delete(path + f'/members/{people["member"]}').status_code == 200
    assert member.get("/api/v1/projects").json()[0]["can_write"] is True
    assert people["member"] in {u["id"] for u in admin.get(path + "/assignees").json()}
    assert admin.put(path + "/members", json={"user_id": people["member"], "role": "owner"}).status_code == 200
    assert member.put(path, json=settings("read-only")).status_code == 200
    assert member.get("/api/v1/projects").json()[0]["can_manage"] is True
    assert admin.get("/api/v1/projects").json()[0]["can_manage"] is True
    assert admin.get("/api/v1/projects").json()[0]["can_write"] is True
    legacy = settings()
    del legacy["default_access"]
    assert member.put(path, json=legacy).json()["default_access"] == "read-only"
    for invalid in ("owner", "member", "", False):
        assert member.put(path, json=settings(invalid)).status_code == 422


def test_restricted_tickets_with_inherited_access(env):
    _, client, people = env
    admin, member = client("administrator"), client("member")
    project = admin.post("/api/v1/projects", json={"key": "DA", **settings("reporter", restrict_ticket_visibility=True)}).json()
    path = f'/api/v1/projects/{project["id"]}'
    own = member.post(path + "/items", json={"title": "Own"}).json()
    assigned = admin.post(path + "/items", json={"title": "Assigned", "assignee_id": people["member"]}).json()
    public = admin.post(path + "/items", json={"title": "Public"}).json()
    hidden = admin.post(path + "/items", json={"title": "Hidden"}).json()
    assert admin.put(f'/api/v1/items/{public["id"]}/publication', json={"is_project_public": True}).status_code == 200
    for access in ("reporter", "read-only"):
        assert admin.put(path, json=settings(access)).status_code == 200
        expected = {own["id"], assigned["id"], public["id"]}
        assert {i["id"] for i in member.get(path + "/items").json()["items"]} == expected
        assert {i["id"] for i in member.get("/api/v1/references/tickets").json()} == expected
        for iid in expected:
            assert member.get(f"/api/v1/items/{iid}").status_code == 200
        assert member.get(f'/api/v1/items/{hidden["id"]}').status_code == 404


def test_tokens_bots_and_inactive_users(env):
    factory, client, people = env
    admin = client("administrator")
    project = admin.post("/api/v1/projects", json={"key": "DA", **settings("reporter")}).json()
    path = f'/api/v1/projects/{project["id"]}'
    personal = bearer(issue(client("member"), ["read", "write"])["token"])
    read_token = bearer(issue(client("reader"))["token"])
    automation = bot(admin)
    bot_token = bearer(issue(admin, ["read", "write"], f'/api/v1/bots/{automation["id"]}/tokens')["token"])
    assert personal.post(path + "/items", json={"title": "Token"}).status_code == 201
    assert read_token.post(path + "/items", json={"title": "Denied"}).status_code == 403
    assert bot_token.get("/api/v1/projects").json() == []
    assert bot_token.get(path + "/items").status_code == 404
    assert admin.put(path + "/members", json={"user_id": automation["id"], "role": "read-only"}).status_code == 200
    assert bot_token.get(path + "/items").status_code == 200
    assert bot_token.post(path + "/items", json={"title": "Denied"}).status_code == 403
    assert admin.put(path, json=settings("read-only")).status_code == 200
    assert personal.post(path + "/items", json={"title": "Denied"}).status_code == 403
    with factory() as db:
        db.get(User, people["member"]).active = False
        db.commit()
    assert personal.get(path + "/items").status_code == 401
    assert people["member"] not in {u["id"] for u in admin.get(path + "/assignees").json()}


def test_notifications_include_inherited_participants_and_recheck_access(notifying, monkeypatch):
    factory, client, people, pid = notifying
    admin = client("administrator")
    path = f"/api/v1/projects/{pid}"
    for role in ("member", "reader"):
        assert admin.delete(path + f'/members/{people[role]}').status_code == 200
    assert admin.put(path, json=settings("reporter")).status_code == 200
    item = client("member").post(path + "/items", json={"title": "Notify", "description": f'[@user](/users/{people["reader"]})'}).json()
    assert queued(factory, clear=True) == {people[r] for r in ("administrator", "member", "reader")}
    assert admin.post(f'/api/v1/items/{item["id"]}/comments', json={"body": "Owner participating"}).status_code == 201
    queued(factory, clear=True)
    assert client("reader").post(f'/api/v1/items/{item["id"]}/comments', json={"body": "Participating"}).status_code == 201
    assert queued(factory) == {people[r] for r in ("administrator", "member", "reader")}
    assert admin.put(path, json=settings(None)).status_code == 200
    sent = []
    monkeypatch.setattr(mail, "send_message", sent.append)
    notifications.deliver_notifications()
    assert {str(message["To"]) for message in sent} == {"administrator@example.test"}

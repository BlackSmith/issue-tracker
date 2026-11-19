import pytest
from sqlalchemy import select

from app import mail, notifications
from app.models import TicketNotification
from test_access import project
from test_api_tokens import bearer, bot, issue
from test_notifications import notifying, queued, create


def set_restriction(admin, pid, enabled):
    response = admin.put(f"/api/v1/projects/{pid}", json={
        "name": "Restricted", "description": "", "visibility": "private",
        "restrict_ticket_visibility": enabled})
    assert response.status_code == 200, response.text
    assert response.json()["restrict_ticket_visibility"] is enabled


@pytest.mark.parametrize("role", ["reporter", "read-only"])
def test_own_tickets_lists_references_and_role_changes(env, role):
    _, client, people = env
    admin, member = client("administrator"), client("member")
    pid = project(admin)
    path = f"/api/v1/projects/{pid}"
    authored = member.post(path + "/items", json={"title": "Authored"}).json()
    assigned = admin.post(path + "/items", json={"title": "Assigned", "assignee_id": people["member"]}).json()
    hidden = admin.post(path + "/items", json={"title": "Hidden", "assignee_id": people["administrator"]}).json()
    assert member.get(path + "/items").json()["total"] == 3
    set_restriction(admin, pid, True)
    assert admin.put(path + "/members", json={"user_id": people["member"], "role": role}).status_code == 200
    result = member.get(path + "/items?per_page=1").json()
    assert result["total"] == 2 and len(result["items"]) == 1
    assert member.get(path + "/items?q=Hidden").json()["total"] == 0
    for item in (authored, assigned):
        assert member.get(f'/api/v1/items/{item["id"]}').status_code == 200
        assert member.get(f'/api/v1/projects/by-slug/APP/items/{item["number"]}').status_code == 200
    assert member.get(f'/api/v1/projects/by-slug/APP/items/{hidden["number"]}').status_code == 404
    assert {person["id"] for person in member.get(path + "/item-assignees").json()} == {people["member"]}
    suggestions = member.get("/api/v1/references/tickets").json()
    assert {item["id"] for item in suggestions} == {authored["id"], assigned["id"]}
    resolved = member.post("/api/v1/references/resolve", json={"tickets": [hidden["id"], authored["id"]]}).json()
    assert [item["id"] for item in resolved["tickets"]] == [authored["id"]]
    assert member.get(path + "/items?assignee=me").json()["total"] == 1
    assert admin.get(path + "/items").json()["total"] == 3
    assert admin.put(path + "/members", json={"user_id": people["member"], "role": "owner"}).status_code == 200
    assert member.get(path + "/items").json()["total"] == 3
    assert member.get(f'/api/v1/items/{hidden["id"]}').status_code == 200
    assert admin.put(path + "/members", json={"user_id": people["member"], "role": role}).status_code == 200
    set_restriction(admin, pid, False)
    assert member.get(path + "/items").json()["total"] == 3


def test_hidden_ticket_content_writes_attachments_and_reassignment(env):
    _, client, people = env
    admin, member = client("administrator"), client("member")
    pid = project(admin)
    item = admin.post(f"/api/v1/projects/{pid}/items", json={"title": "Hidden"}).json()
    path = f'/api/v1/items/{item["id"]}'
    upload = admin.post(path + "/attachments", files={"file": ("private.txt", b"private")}).json()
    set_restriction(admin, pid, True)
    for suffix in ("", "/discussion", "/attachments"):
        assert member.get(path + suffix).status_code == 404
    assert member.get(upload["url"]).status_code == 404
    assert member.patch(path, json={"title": "Denied"}).status_code == 404
    assert member.put(path, json={"title": "Denied"}).status_code == 404
    assert member.post(path + "/comments", json={"body": "Denied"}).status_code == 404
    assert member.post(path + "/attachments", files={"file": ("x", b"x")}).status_code == 404
    assert admin.patch(path, json={"assignee_id": people["member"]}).status_code == 200
    assert member.get(upload["url"]).content == b"private"
    assert member.post(path + "/comments", json={"body": "Allowed"}).status_code == 201
    assert admin.patch(path, json={"assignee_id": None}).status_code == 200
    assert member.get(path).status_code == 404


def test_setting_permissions_defaults_and_legacy_updates(env):
    _, client, _ = env
    admin = client("administrator")
    created = admin.post("/api/v1/projects", json={"key": "OWN", "name": "Own", "restrict_ticket_visibility": True}).json()
    pid = project(admin)
    assert next(p for p in admin.get("/api/v1/projects").json() if p["id"] == pid)["restrict_ticket_visibility"] is False
    set_restriction(admin, pid, True)
    payload = {"name": "Legacy", "description": "", "visibility": "private"}
    assert admin.put(f"/api/v1/projects/{pid}", json=payload).json()["restrict_ticket_visibility"] is True
    for role in ("member", "reader"):
        assert client(role).put(f"/api/v1/projects/{pid}", json={**payload, "restrict_ticket_visibility": False}).status_code == 403
    assert created["restrict_ticket_visibility"] is True


def test_notifications_recheck_ticket_visibility(notifying, monkeypatch):
    factory, client, people, pid = notifying
    admin = client("administrator")
    iid = create(admin, pid, assignee_id=people["member"], description=f'[@user](/users/{people["reader"]})')
    assert queued(factory) == {people[r] for r in ("administrator", "member", "reader")}
    set_restriction(admin, pid, True)
    sent = []
    monkeypatch.setattr(mail, "send_message", sent.append)
    notifications.deliver_notifications()
    assert {str(message["To"]) for message in sent} == {"administrator@example.test", "member@example.test"}
    with factory() as db:
        row = db.scalar(select(TicketNotification).where(TicketNotification.user_id == people["reader"]))
        assert row.delivery_status == "canceled" and row.encrypted_body is None
    queued(factory, clear=True)
    assert admin.patch(f"/api/v1/items/{iid}", json={"assignee_id": None}).status_code == 200
    assert queued(factory) == {people["administrator"]}


@pytest.mark.parametrize("is_bot", [False, True])
def test_tokens_and_bots_obey_ticket_visibility(env, is_bot):
    _, client, people = env
    admin, member = client("administrator"), client("member")
    pid = project(admin)
    if is_bot:
        uid = bot(admin)["id"]
        assert admin.put(f"/api/v1/bots/{uid}/projects/{pid}", json={"role": "reporter"}).status_code == 200
        api = bearer(issue(admin, ["write"], f"/api/v1/bots/{uid}/tokens")["token"])
    else:
        uid = people["member"]
        api = bearer(issue(member, ["write"])["token"])
    path = f"/api/v1/projects/{pid}/items"
    authored = api.post(path, json={"title": "Authored through token"}).json()
    assigned = admin.post(path, json={"title": "Assigned", "assignee_id": uid}).json()
    hidden = admin.post(path, json={"title": "Hidden"}).json()
    set_restriction(admin, pid, True)
    assert {item["id"] for item in api.get(path).json()["items"]} == {authored["id"], assigned["id"]}
    assert api.get(f'/api/v1/items/{hidden["id"]}').status_code == 404
    assert api.patch(f'/api/v1/items/{hidden["id"]}', json={"title": "Denied"}).status_code == 404
    assert api.post("/api/v1/references/resolve", json={"tickets": [hidden["id"]]}).json()["tickets"] == []

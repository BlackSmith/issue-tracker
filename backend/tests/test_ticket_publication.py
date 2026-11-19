import pytest
from sqlalchemy import select

from app import mail, notifications
from app.models import TicketNotification
from test_access import project
from test_api_tokens import bearer, bot, issue
from test_notifications import notifying, queued, create
from test_ticket_visibility import set_restriction


def publish(client, iid, value=True):
    return client.put(f"/api/v1/items/{iid}/publication", json={"is_project_public": value})


def test_owner_publication_grants_project_access_and_can_be_revoked(env):
    _, client, people = env
    admin, owner, reader = client("administrator"), client("member"), client("reader")
    pid = project(admin)
    item = admin.post(f"/api/v1/projects/{pid}/items", json={"title": "Publishable"}).json()
    iid = item["id"]
    path = f"/api/v1/items/{iid}"
    attachment = admin.post(path + "/attachments", files={"file": ("note.txt", b"shared")}).json()
    set_restriction(admin, pid, True)
    assert admin.put(f"/api/v1/projects/{pid}/members", json={"user_id": people["member"], "role": "owner"}).status_code == 200
    assert item["is_project_public"] is False
    assert reader.get(path).status_code == 404
    result = publish(owner, iid)
    assert result.status_code == 200 and result.json()["is_project_public"] is True
    assert reader.get(path).status_code == 200
    assert reader.get(f'/api/v1/projects/by-slug/APP/items/{item["number"]}').status_code == 200
    assert reader.get(f"/api/v1/projects/{pid}/items").json()["total"] == 1
    assert reader.get(path + "/discussion").status_code == 200
    assert reader.get(attachment["url"]).content == b"shared"
    assert [row["id"] for row in reader.get("/api/v1/references/tickets").json()] == [iid]
    assert reader.post("/api/v1/references/resolve", json={"tickets": [iid]}).json()["tickets"][0]["id"] == iid
    assert reader.post(path + "/comments", json={"body": "Still read-only"}).status_code == 403
    history = owner.get(path + "/discussion").json()
    assert history[-1]["body"] == "published this ticket to project members"
    assert publish(owner, iid).status_code == 200
    assert owner.get(path + "/discussion").json() == history
    # Publication never grants access to users outside this project.
    assert admin.delete(f'/api/v1/projects/{pid}/members/{people["reader"]}').status_code == 200
    assert reader.get(path).status_code == 404
    assert admin.put(f"/api/v1/projects/{pid}/members", json={"user_id": people["reader"], "role": "read-only"}).status_code == 200
    assert publish(owner, iid, False).status_code == 200
    for suffix in ("", "/discussion", "/attachments"):
        assert reader.get(path + suffix).status_code == 404
    assert reader.get(attachment["url"]).status_code == 404
    assert reader.get(f"/api/v1/projects/{pid}/items").json()["total"] == 0
    assert reader.post("/api/v1/references/resolve", json={"tickets": [iid]}).json()["tickets"] == []


def test_only_owners_can_change_publication_and_other_edits_preserve_it(env):
    _, client, people = env
    admin, member, reader = client("administrator"), client("member"), client("reader")
    pid = project(admin)
    iid = member.post(f"/api/v1/projects/{pid}/items", json={"title": "Authored"}).json()["id"]
    assert publish(admin, iid).status_code == 409
    set_restriction(admin, pid, True)
    assert publish(member, iid).status_code == 403
    assert member.patch(f"/api/v1/items/{iid}", json={"is_project_public": True}).status_code == 422
    assert publish(admin, iid).status_code == 200
    for actor in (member, reader):
        for value in (False, True):
            assert publish(actor, iid, value).status_code == 403
    assert member.patch(f"/api/v1/items/{iid}", json={"priority": "High"}).json()["is_project_public"] is True
    assert member.put(f"/api/v1/items/{iid}", json={"title": "Replaced"}).json()["is_project_public"] is True
    assert member.post(f"/api/v1/items/{iid}/comments", json={"body": "Allowed"}).status_code == 201
    set_restriction(admin, pid, False)
    set_restriction(admin, pid, True)
    assert reader.get(f"/api/v1/items/{iid}").json()["is_project_public"] is True
    admin.headers.pop("X-CSRF-Token")
    assert publish(admin, iid, False).status_code == 403


@pytest.mark.parametrize("is_bot", [False, True])
def test_publication_applies_to_tokens_without_granting_owner_permissions(env, is_bot):
    _, client, _ = env
    admin, member = client("administrator"), client("member")
    pid = project(admin)
    iid = admin.post(f"/api/v1/projects/{pid}/items", json={"title": "Shared"}).json()["id"]
    if is_bot:
        uid = bot(admin)["id"]
        assert admin.put(f"/api/v1/bots/{uid}/projects/{pid}", json={"role": "reporter"}).status_code == 200
        api = bearer(issue(admin, ["write"], f"/api/v1/bots/{uid}/tokens")["token"])
    else:
        api = bearer(issue(member, ["write"])["token"])
    set_restriction(admin, pid, True)
    assert api.get(f"/api/v1/items/{iid}").status_code == 404
    assert publish(admin, iid).status_code == 200
    assert api.get(f"/api/v1/items/{iid}").status_code == 200
    assert api.post(f"/api/v1/items/{iid}/comments", json={"body": "Visible"}).status_code == 201
    assert publish(api, iid, False).status_code == 403
    assert publish(admin, iid, False).status_code == 200
    assert api.get(f"/api/v1/items/{iid}").status_code == 404


def test_publication_notifications_recheck_access_on_restriction(notifying, monkeypatch):
    factory, client, people, pid = notifying
    admin = client("administrator")
    set_restriction(admin, pid, True)
    iid = create(admin, pid, description=f'[@user](/users/{people["reader"]})')
    assert queued(factory, clear=True) == {people["administrator"]}
    assert publish(admin, iid).status_code == 200
    assert queued(factory) == {people["administrator"], people["reader"]}
    assert publish(admin, iid, False).status_code == 200
    sent = []
    monkeypatch.setattr(mail, "send_message", sent.append)
    notifications.deliver_notifications()
    assert {str(message["To"]) for message in sent} == {"administrator@example.test"}
    with factory() as db:
        row = db.scalar(select(TicketNotification).where(TicketNotification.user_id == people["reader"]))
        assert row.delivery_status == "canceled" and row.encrypted_body is None

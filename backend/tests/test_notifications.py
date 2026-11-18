import json
import time

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import delete, select

from app import mail, notifications
from app.main import settings
from app.models import ProjectMember, TicketNotification, User


@pytest.fixture
def notifying(env, monkeypatch):
    factory, client, people = env
    monkeypatch.setattr(settings, "notifications_enabled", True)
    monkeypatch.setattr(settings, "mail_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "smtp_host", "mail.example.com")
    monkeypatch.setattr(settings, "smtp_from", "tracker@example.com")
    monkeypatch.setattr(settings, "password_enabled", False)
    monkeypatch.setattr(notifications, "SessionLocal", factory)
    admin = client("administrator")
    response = admin.post("/api/v1/projects", json={"name": "Notifications", "key": "NT"})
    assert response.status_code == 201, response.text
    project = response.json()["id"]
    for role, access in (("member", "reporter"), ("reader", "read-only")):
        assert admin.put(f"/api/v1/projects/{project}/members", json={
            "user_id": people[role], "role": access}).status_code == 200
    return factory, client, people, project


def queued(factory, clear=False):
    with factory() as db:
        rows = db.scalars(select(TicketNotification)).all()
        result = {row.user_id for row in rows}
        assert len(rows) == len(result), "Each event must notify a user only once"
        if clear:
            db.execute(delete(TicketNotification))
            db.commit()
        return result


def create(client, project, **values):
    response = client.post(f"/api/v1/projects/{project}/items", json={"title": "Notification test", **values})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_creation_owners_assignee_mentions_and_deduplication(notifying):
    factory, client, people, project = notifying
    with factory() as db:
        owner = User(name="Owner", email="owner@example.com", role="member")
        inherited = User(name="Admin", email="admin@example.com", role="administrator")
        unrelated = User(name="Other", email="other@example.com", role="member")
        db.add_all([owner, inherited, unrelated])
        db.flush()
        db.add(ProjectMember(project_id=project, user_id=owner.id, role="owner"))
        db.commit()
        expected = {people["administrator"], people["member"], people["reader"], owner.id, inherited.id}
    create(client("member"), project, assignee_id=people["member"], description=(
        f'Hello [@user](/users/{people["reader"]}) [@user](/users/{people["reader"]}) '
        f'[@user](/users/{unrelated.id}) [@user](/users/{people["outsider"]})'))
    assert queued(factory) == expected


def test_updates_participants_persistent_mentions_old_and_new_assignee_noops(notifying):
    factory, client, people, project = notifying
    admin, member = client("administrator"), client("member")
    item = create(admin, project, assignee_id=people["member"])
    queued(factory, clear=True)
    assert member.post(f"/api/v1/items/{item}/comments", json={
        "body": f'Please review [@user](/users/{people["reader"]})'}).status_code == 201
    assert queued(factory, clear=True) == {people[role] for role in ("administrator", "member", "reader")}
    assert admin.patch(f"/api/v1/items/{item}", json={"assignee_id": people["administrator"]}).status_code == 200
    assert queued(factory, clear=True) == {people[role] for role in ("administrator", "member", "reader")}
    # The former assignee remains a participant through their comment.
    assert admin.patch(f"/api/v1/items/{item}", json={"status": "Done"}).status_code == 200
    assert queued(factory, clear=True) == {people[role] for role in ("administrator", "member", "reader")}
    assert admin.patch(f"/api/v1/items/{item}", json={"status": "Done"}).status_code == 200
    assert queued(factory) == set()
    assert client("reader").patch(f"/api/v1/items/{item}", json={"title": "Denied"}).status_code == 403
    assert queued(factory) == set()


def test_reassignment_notifies_previous_assignee_without_participation(notifying):
    factory, client, people, project = notifying
    admin = client("administrator")
    item = create(admin, project, assignee_id=people["member"])
    queued(factory, clear=True)
    assert admin.patch(f"/api/v1/items/{item}", json={"assignee_id": None}).status_code == 200
    assert queued(factory, clear=True) == {people["administrator"], people["member"]}
    assert admin.patch(f"/api/v1/items/{item}", json={"priority": "High"}).status_code == 200
    assert queued(factory) == {people["administrator"]}


def test_checklist_upload_and_pending_upload(notifying):
    factory, client, people, project = notifying
    admin = client("administrator")
    item = create(admin, project, description="- [ ] Verify notifications")
    queued(factory, clear=True)
    from app.checklists import content_version
    path = f"/api/v1/items/{item}/checklist/0"
    payload = {"checked": True, "version": content_version("- [ ] Verify notifications")}
    response = admin.patch(path, json=payload)
    assert response.status_code == 200
    assert queued(factory, clear=True) == {people["administrator"]}
    assert admin.patch(path, json=payload).status_code == 409
    assert queued(factory) == set()
    assert admin.post(f"/api/v1/items/{item}/attachments?pending=true",
                      files={"file": ("draft.txt", b"draft")}).status_code == 201
    assert queued(factory) == set()
    assert admin.post(f"/api/v1/items/{item}/attachments",
                      files={"file": ("saved.txt", b"saved")}).status_code == 201
    assert queued(factory) == {people["administrator"]}


def test_delivery_encryption_retry_and_current_contact_address(notifying, monkeypatch):
    factory, client, people, project = notifying
    item = create(client("member"), project)
    with factory() as db:
        row = db.scalar(select(TicketNotification).where(TicketNotification.user_id == people["member"]))
        payload = json.loads(Fernet(settings.mail_encryption_key.encode()).decrypt(row.encrypted_body.encode()))
        assert "Notification test" not in row.encrypted_body
        assert f"/NT/1" in payload["body"]
        db.get(User, people["member"]).email = "new-contact@example.com"
        db.commit()
    sent = []

    def fail(message):
        raise OSError("SMTP unavailable")

    monkeypatch.setattr(mail, "send_message", fail)
    notifications.deliver_notifications()
    with factory() as db:
        rows = db.scalars(select(TicketNotification)).all()
        assert all(row.attempts == 1 and row.delivery_status == "queued" and row.next_attempt_at > time.time() for row in rows)
        for row in rows:
            row.next_attempt_at = 0
        db.commit()
    monkeypatch.setattr(mail, "send_message", sent.append)
    notifications.deliver_notifications()
    assert {str(message["To"]) for message in sent} == {"administrator@example.test", "new-contact@example.com"}
    assert all("NT-1" in str(message["Subject"]) and "/NT/1" in message.get_content() for message in sent)
    with factory() as db:
        assert all(row.delivery_status == "sent" and row.encrypted_body is None for row in db.scalars(select(TicketNotification)))
    notifications.deliver_notifications()
    assert len(sent) == 2


@pytest.mark.parametrize("reason", ["removed", "disabled", "bot", "pending", "empty_email"])
def test_delivery_rechecks_eligibility(notifying, monkeypatch, reason):
    factory, client, people, project = notifying
    create(client("administrator"), project, assignee_id=people["member"])
    with factory() as db:
        person = db.get(User, people["member"])
        if reason == "removed":
            db.delete(db.get(ProjectMember, (project, person.id)))
        elif reason == "disabled":
            person.active = False
        elif reason == "bot":
            person.is_bot = True
        elif reason == "pending":
            person.role = None
        else:
            person.email = ""
        db.commit()
    sent = []
    monkeypatch.setattr(mail, "send_message", sent.append)
    notifications.deliver_notifications()
    assert [str(message["To"]) for message in sent] == ["administrator@example.test"]
    with factory() as db:
        row = db.scalar(select(TicketNotification).where(TicketNotification.user_id == people["member"]))
        assert row.delivery_status == "canceled" and row.encrypted_body is None


def test_bounded_failure_and_disabled_notifications(notifying, monkeypatch):
    factory, client, people, project = notifying
    create(client("administrator"), project)
    with factory() as db:
        db.scalar(select(TicketNotification)).attempts = 7
        db.commit()
    def fail(message):
        raise OSError("SMTP unavailable")
    monkeypatch.setattr(mail, "send_message", fail)
    notifications.deliver_notifications()
    with factory() as db:
        row = db.scalar(select(TicketNotification))
        assert row.attempts == 8 and row.delivery_status == "failed" and row.encrypted_body is None
        db.execute(delete(TicketNotification))
        db.commit()
    monkeypatch.setattr(settings, "notifications_enabled", False)
    create(client("administrator"), project)
    assert queued(factory) == set()


def test_mentions_parse_real_markdown_links_only():
    user_id = "52c0c1bc-09f5-4243-b5c4-3395366c2b85"
    mention = f"[@user](/users/{user_id})"
    assert notifications.mentioned_users(mention) == {user_id}
    assert notifications.mentioned_users(f"`{mention}`\n\n```\n{mention}\n```\n") == set()
    assert notifications.mentioned_users(f"!{mention} [bad](/users/not-a-uuid) [external](https://other/users/{user_id})") == set()


def test_notification_configuration_is_independent_of_passwords():
    from app.config import Settings
    key = Fernet.generate_key().decode()
    configured = Settings(_env_file=None, password_enabled=False, notifications_enabled=True,
                          smtp_host="mail.example.com", smtp_from="tracker@example.com", mail_encryption_key=key)
    assert configured.notifications_enabled and not configured.password_enabled
    with pytest.raises(ValueError):
        Settings(_env_file=None, password_enabled=False, notifications_enabled=True, smtp_host="", smtp_from="")
    with pytest.raises(ValueError):
        Settings(_env_file=None, password_enabled=False, notifications_enabled=True,
                 smtp_host="mail.example.com", smtp_from="tracker@example.com", mail_encryption_key="invalid")

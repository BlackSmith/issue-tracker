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
        assert "/NT/1" in payload["url"]
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
    assert all("NT-1" in str(message["Subject"]) and "/NT/1" in message.get_body(preferencelist=("plain",)).get_content() for message in sent)
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


def test_multipart_delivery_uses_each_recipients_latest_language(notifying, monkeypatch):
    factory, client, people, project = notifying
    create(client("member"), project)
    # A saved language change after queueing must affect delivery, independently of the actor.
    with factory() as db:
        db.get(User, people["member"]).language = "cs"
        db.commit()
    sent = []
    monkeypatch.setattr(mail, "send_message", sent.append)
    notifications.deliver_notifications()
    messages = {str(message["To"]): message for message in sent}
    for address, language, heading, action, link_label in (
        ("member@example.test", "cs", "Nový ticket", "vytvořil(a) tento ticket", "Otevřít ticket"),
        ("administrator@example.test", "en", "New ticket", "created this work item", "Open ticket"),
    ):
        message = messages[address]
        assert message.get_content_type() == "multipart/alternative"
        assert message["Content-Language"] == language
        assert heading in str(message["Subject"])
        plain = message.get_body(preferencelist=("plain",)).get_content()
        html = message.get_body(preferencelist=("html",)).get_content()
        assert action in plain and action in html
        assert f'{link_label}: {settings.app_base_url}/NT/1' in plain
        assert f'href="{settings.app_base_url}/NT/1"' in html
        assert f'lang="{language}"' in html and link_label in html


@pytest.mark.parametrize("summary,expected", [
    ('updated status from "Open" to "In progress", priority from "Medium" to "High"',
     'změnil(a): stav z "Otevřeno" na "Probíhá", prioritu z "Střední" na "Vysoká"'),
    ('updated title, description', 'změnil(a): název, popis'),
    ('updated labels from ["Open", "High, urgent"] to ["Done"], assignee to "Open"',
     'změnil(a): štítky z ["Open", "High, urgent"] na ["Done"], řešitele na "Open"'),
    ('updated assignee from "Member" to Unassigned, due date to Not set, labels to No labels',
     'změnil(a): řešitele z "Member" na Nepřiřazeno, termín na Nenastaveno, štítky na Žádné štítky'),
    ('updated type from "Task" to "Bug", status from "Done" to "Canceled"',
     'změnil(a): typ z "Úkol" na "Chyba", stav z "Hotovo" na "Zrušeno"'),
    ('checked checklist item #1 "Open" in the description',
     'zaškrtl(a) položku seznamu úkolů č. 1 "Open" v popisu'),
    ('unchecked checklist item #2 "High" in a comment',
     'odškrtl(a) položku seznamu úkolů č. 2 "High" v komentáři'),
    ('uploaded Open.txt', 'nahrál(a) soubor Open.txt'),
    ('added a comment', 'přidal(a) komentář'),
])
def test_localized_change_summaries_preserve_user_content(summary, expected):
    from app.notification_email import summary_text
    assert summary_text(summary, "cs") == expected
    assert summary_text(summary, "en") == summary


def test_html_escapes_user_content_and_preserves_snapshot_and_safe_subject(notifying, monkeypatch):
    from html.parser import HTMLParser
    factory, client, people, project = notifying
    title = '<script>alert("ticket")</script> & "quoted"\nSubject: injected'
    with factory() as db:
        db.get(User, people["member"]).name = '<img src=x onerror="alert(1)">'
        db.commit()
    item = create(client("member"), project, title=title)
    # The queued creation email must describe the creation, not this later edit.
    assert client("administrator").patch(f"/api/v1/items/{item}", json={"title": "Later title"}).status_code == 200
    sent = []
    monkeypatch.setattr(mail, "send_message", sent.append)
    notifications.deliver_notifications()
    creation = next(message for message in sent if "New ticket" in str(message["Subject"]))
    html = creation.get_body(preferencelist=("html",)).get_content()
    assert "&lt;script&gt;" in html and "&lt;img" in html and "&amp;" in html
    assert "Later title" not in html
    assert "\n" not in str(creation["Subject"])
    assert title in creation.get_body(preferencelist=("plain",)).get_content()

    class Links(HTMLParser):
        def handle_starttag(self, tag, attrs):
            assert tag not in {"script", "img"}
            if tag == "a":
                assert dict(attrs)["href"] in {f"{settings.app_base_url}/NT/1",
                                              f"{settings.app_base_url}/NT/1#notifications",
                                              f"{settings.app_base_url}/NT/#project-notifications"}
    Links().feed(html)


def test_preexisting_queued_payload_still_delivers_as_multipart(notifying, monkeypatch):
    factory, client, people, project = notifying
    create(client("administrator"), project)
    legacy = {"subject": "[NT-1] New ticket: Legacy", "body": "Legacy <title>\n\nOpen ticket: https://tracker.example.com/NT/1\n"}
    with factory() as db:
        row = db.scalar(select(TicketNotification))
        row.encrypted_body = Fernet(settings.mail_encryption_key.encode()).encrypt(json.dumps(legacy).encode()).decode()
        db.commit()
    sent = []
    monkeypatch.setattr(mail, "send_message", sent.append)
    notifications.deliver_notifications()
    assert len(sent) == 1
    message = sent[0]
    assert str(message["Subject"]) == legacy["subject"]
    assert message.get_body(preferencelist=("plain",)).get_content().startswith(legacy["body"])
    html = message.get_body(preferencelist=("html",)).get_content()
    assert "&lt;title&gt;" in html and 'href="https://tracker.example.com/NT/1"' in html


def test_subscription_overrides_project_and_adds_readonly_participant(notifying):
    factory, client, people, project = notifying
    admin, reader = client("administrator"), client("reader")
    item = create(admin, project)
    queued(factory, clear=True)
    project_path = f"/api/v1/projects/{project}/notifications"
    ticket_path = f"/api/v1/items/{item}/notifications"
    assert reader.put(project_path, json={"enabled": False}).json() == {"enabled": False}
    assert reader.get(ticket_path).json()["enabled"] is None
    response = reader.put(ticket_path, json={"enabled": True})
    assert response.status_code == 200
    assert people["reader"] in {p["id"] for p in response.json()["participants"]}
    assert all(entry["author"] != "reader" for entry in admin.get(f"/api/v1/items/{item}/discussion").json())
    assert admin.patch(f"/api/v1/items/{item}", json={"priority": "High"}).status_code == 200
    assert queued(factory, clear=True) == {people["administrator"], people["reader"]}
    assert reader.put(ticket_path, json={"enabled": False}).status_code == 200
    admin.patch(f"/api/v1/items/{item}", json={"priority": "Low"})
    assert queued(factory, clear=True) == {people["administrator"]}
    assert reader.put(ticket_path, json={"enabled": None}).json()["enabled"] is None
    assert reader.get(project_path).json()["enabled"] is False
    assert admin.get(project_path).json()["enabled"] is True


@pytest.mark.parametrize("direct", ["assignee", "description", "comment", None])
def test_muting_exceptions_and_delivery_recheck(notifying, monkeypatch, direct):
    factory, client, people, project = notifying
    admin, member = client("administrator"), client("member")
    mention = f'[@user](/users/{people["member"]})'
    item = create(member, project, **({"assignee_id": people["member"]} if direct == "assignee" else
                                    {"description": mention} if direct == "description" else {}))
    if direct == "comment":
        queued(factory, clear=True)
        admin.post(f"/api/v1/items/{item}/comments", json={"body": mention})
        queued(factory, clear=True)
        admin.patch(f"/api/v1/items/{item}", json={"priority": "High"})
    # Mute after queueing: ordinary notifications must be canceled at delivery.
    assert member.put(f"/api/v1/projects/{project}/notifications", json={"enabled": False}).status_code == 200
    assert member.put(f"/api/v1/items/{item}/notifications", json={"enabled": False}).status_code == 200
    sent = []
    monkeypatch.setattr(mail, "send_message", sent.append)
    notifications.deliver_notifications()
    assert ("member@example.test" in {str(m["To"]) for m in sent}) == (direct is not None)
    with factory() as db:
        db.execute(delete(TicketNotification))
        db.commit()
    admin.patch(f"/api/v1/items/{item}", json={"status": "Done"})
    assert (people["member"] in queued(factory)) == (direct is not None)


def test_preferences_permissions_csrf_and_restricted_subscription(notifying):
    from test_api_tokens import bearer, issue
    factory, client, people, project = notifying
    admin, member = client("administrator"), client("member")
    item = create(admin, project)
    path = f"/api/v1/items/{item}/notifications"
    assert client().get(path).status_code == 401
    assert client("outsider").put(path, json={"enabled": True}).status_code == 404
    member.headers.pop("X-CSRF-Token")
    assert member.put(path, json={"enabled": True}).status_code == 403
    token = bearer(issue(admin, ["read", "write"])["token"])
    assert token.get(path).status_code == 403
    assert member.get(path).status_code == 200
    assert admin.put(f"/api/v1/projects/{project}", json={"name": "Notifications", "description": "",
                     "visibility": "private", "restrict_ticket_visibility": True}).status_code == 200
    assert member.get(path).status_code == 404
    member.headers["X-CSRF-Token"] = "test-csrf"
    assert member.put(path, json={"enabled": True}).status_code == 404


def test_bot_updates_follow_subscription_rules_and_localized_footer(notifying, monkeypatch):
    from test_api_tokens import bearer, bot, issue
    factory, client, people, project = notifying
    admin, reader = client("administrator"), client("reader")
    item = create(admin, project)
    queued(factory, clear=True)
    reader.put(f"/api/v1/items/{item}/notifications", json={"enabled": True})
    account = bot(admin)
    admin.put(f'/api/v1/bots/{account["id"]}/projects/{project}', json={"role": "reporter"})
    api = bearer(issue(admin, ["write"], f'/api/v1/bots/{account["id"]}/tokens')["token"])
    assert api.patch(f"/api/v1/items/{item}", json={"status": "Done"}).status_code == 200
    assert queued(factory) == {people["administrator"], people["reader"]}
    with factory() as db:
        db.get(User, people["reader"]).language = "cs"
        db.commit()
    sent = []
    monkeypatch.setattr(mail, "send_message", sent.append)
    notifications.deliver_notifications()
    for message in sent:
        plain = message.get_body(preferencelist=("plain",)).get_content()
        html = message.get_body(preferencelist=("html",)).get_content()
        assert "Automation bot" in plain
        assert f"{settings.app_base_url}/NT/1#notifications" in plain and "#project-notifications" in html
        assert ("Tento e-mail byl odeslán" if message["Content-Language"] == "cs" else "This email was sent") in plain
        assert ("Spravovat notifikace" if message["Content-Language"] == "cs" else "Manage ticket notifications") in html

import pytest
from starlette.websockets import WebSocketDisconnect

from app import realtime
from app.main import settings
from app.models import BrowserSession, User
from app.security import token_hash
from test_access import item, project


def test_optimistic_fields_reject_stale_updates_without_side_effects(env):
    _, client, _ = env
    admin = client("administrator")
    path = f"/api/v1/items/{item(admin, project(admin))}"
    original = admin.get(path).json()
    assert admin.patch(path, json={"title": "Changed elsewhere"}).status_code == 200
    before = admin.get(path + "/discussion").json()
    response = admin.patch(path, json={"title": "Stale draft", "description": "Also stale",
        "expected": {"title": original["title"], "description": original["description"]}})
    assert response.status_code == 409
    assert admin.get(path).json()["title"] == "Changed elsewhere"
    assert admin.get(path).json()["description"] == original["description"]
    assert admin.get(path + "/discussion").json() == before
    # Independent metadata edits remain possible after unrelated changes.
    assert admin.patch(path, json={"priority": "High", "expected": {"priority": "Medium"}}).status_code == 200
    assert admin.patch(path, json={"due_date": "2026-12-01", "expected": {"due_date": None}}).status_code == 200
    assert admin.patch(path, json={"due_date": None, "expected": {"due_date": "2026-12-01"}}).status_code == 200
    assert admin.patch(path, json={"title": "Invalid", "expected": {"role": "administrator"}}).status_code == 422


def test_websocket_requires_browser_session_and_trusted_origin(env, monkeypatch):
    factory, client, _ = env
    monkeypatch.setattr(realtime, "SessionLocal", factory)
    admin = client("administrator")
    project_id = project(admin)
    url = f"/api/v1/tickets/live?project={project_id}"
    for c, headers in [(admin, {"origin": "https://evil.test"}),
                       (client(), {"origin": settings.app_base_url}),
                       (admin, {"origin": settings.app_base_url, "authorization": "Bearer invalid"})]:
        with pytest.raises(WebSocketDisconnect):
            with c.websocket_connect(url, headers=headers):
                pass


def test_live_socket_filters_private_events_and_invalidates_lost_access(env, monkeypatch):
    factory, client, people = env
    monkeypatch.setattr(realtime, "SessionLocal", factory)
    admin, reader = client("administrator"), client("reader")
    project_id = project(admin)
    ticket_id = item(admin, project_id)
    assert admin.put(f"/api/v1/projects/{project_id}", json={"name": "Restricted", "description": "",
        "visibility": "private", "restrict_ticket_visibility": True}).status_code == 200
    assert admin.put(f"/api/v1/items/{ticket_id}/publication", json={"is_project_public": True}).status_code == 200
    url = f"/api/v1/tickets/live?project={project_id}"
    with reader.websocket_connect(url, headers={"origin": settings.app_base_url}) as socket:
        assert socket.receive_json() == {"type": "refresh"}
        socket.portal.call(realtime.broadcast, ["item", ticket_id])
        assert socket.receive_json() == {"type": "refresh"}
        assert admin.put(f"/api/v1/items/{ticket_id}/publication", json={"is_project_public": False}).status_code == 200
        socket.portal.call(realtime.broadcast, ["item", ticket_id])
        assert socket.receive_json() == {"type": "refresh"}
        # The same now-private event is no longer delivered as an invalidation.
        socket.portal.call(realtime.broadcast, ["item", ticket_id])
        assert socket.receive_json() == {"type": "ping"}
        assert admin.delete(f"/api/v1/projects/{project_id}/members/{people['reader']}").status_code == 200
        socket.portal.call(realtime.broadcast, ["project", project_id])
        assert socket.receive_json() == {"type": "refresh"}
        socket.portal.call(realtime.broadcast, ["project", project_id])
        assert socket.receive_json() == {"type": "ping"}
        with factory() as db:
            db.get(User, people["reader"]).active = False
            db.commit()
        socket.portal.call(realtime.broadcast, ["resync", None])
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()


def test_logout_revokes_open_socket(env, monkeypatch):
    factory, client, _ = env
    monkeypatch.setattr(realtime, "SessionLocal", factory)
    admin = client("administrator")
    project_id = project(admin)
    secret = admin.cookies.get(settings.session_cookie)
    with admin.websocket_connect(f"/api/v1/tickets/live?project={project_id}",
                                 headers={"origin": settings.app_base_url}) as socket:
        assert socket.receive_json() == {"type": "refresh"}
        with factory() as db:
            db.delete(db.get(BrowserSession, token_hash(secret)))
            db.commit()
        socket.portal.call(realtime.broadcast, ["resync", None])
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()

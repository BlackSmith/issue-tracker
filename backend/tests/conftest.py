import secrets
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import security
from app.db import Base, get_db
from app.main import app, settings
from app.models import BrowserSession, ExternalIdentity, User
from app.security import token_hash


def grant_project_access(admin, project_id):
    """Give standard test contributors explicit roles in a shared fixture project."""
    for person in admin.get('/api/v1/users').json():
        if person['name'] in {'member', 'reader'}:
            role = 'reporter' if person['name'] == 'member' else 'read-only'
            response = admin.put(f'/api/v1/projects/{project_id}/members', json={'user_id': person['id'], 'role': role})
            assert response.status_code == 200, response.text


@pytest.fixture
def env(monkeypatch, tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    factory = sessionmaker(engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(security, "SessionLocal", factory)
    monkeypatch.setattr(settings, "attachment_dir", tmp_path)

    def override():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override
    with factory() as db:
        people = {}
        for role in ["administrator", "member", "reader", "outsider"]:
            user = User(name=role, email=f"{role}@example.test", role=None if role == "outsider" else "member" if role == "reader" else role)
            db.add(user)
            db.flush()
            people[role] = user.id
        db.commit()

    def client(role=None):
        c = TestClient(app)
        if role:
            token = secrets.token_urlsafe(48)
            with factory() as db:
                db.add(BrowserSession(token_hash=token_hash(token), data={"user_id": people[role], "csrf": "test-csrf"}, expires_at=int(time.time()) + 600))
                db.commit()
            c.cookies.set(settings.session_cookie, token)
            c.headers["X-CSRF-Token"] = "test-csrf"
        return c

    yield factory, client, people
    app.dependency_overrides.clear()
    engine.dispose()

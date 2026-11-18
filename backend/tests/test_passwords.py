import re
import time

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.main import settings
from app.models import PasswordCredential, PasswordLink, User
from app import mail


@pytest.fixture
def local(env, monkeypatch):
    factory, client, people = env
    monkeypatch.setattr(settings, 'password_enabled', True)
    monkeypatch.setattr(settings, 'mail_encryption_key', Fernet.generate_key().decode())
    monkeypatch.setattr(settings, 'smtp_host', 'mail.example.com')
    monkeypatch.setattr(settings, 'smtp_from', 'tracker@example.com')
    monkeypatch.setattr(mail, 'SessionLocal', factory)
    return factory, client, people


def create(client):
    admin = client('administrator')
    response = admin.post('/api/v1/admin/users', json={'name': 'Local person', 'email': 'local@example.com'})
    assert response.status_code == 200, response.text
    return admin, response.json()['id']


def secret(factory):
    with factory() as db:
        link = db.scalar(select(PasswordLink).where(PasswordLink.used.is_(False)))
        body = Fernet(settings.mail_encryption_key.encode()).decrypt(link.encrypted_body.encode()).decode()
        token = re.search(r'#token=([\w-]+)', body)[1]
        assert token not in link.encrypted_body and token not in link.secret_hash
        return token


def anonymous(client):
    c = client()
    c.headers['X-CSRF-Token'] = c.get('/api/v1/auth/me').json()['csrf_token']
    return c


def set_password(c, token, password='a long test password'):
    return c.post('/api/v1/auth/password/setup', json={'token': token, 'password': password})


def login(c, password='a long test password', email='local@example.com'):
    return c.post('/api/v1/auth/password/login', json={'email': email, 'password': password})


def test_invitation_single_use_login_rotation_and_contact_email_isolation(local):
    factory, client, _ = local
    _, user_id = create(client)
    token = secret(factory)
    c = anonymous(client)
    assert login(c).status_code == 401
    assert set_password(c, token).status_code == 200
    assert set_password(c, token).status_code == 400
    assert c.get('/api/v1/auth/me').json()['user'] is None
    before = c.cookies.get(settings.session_cookie)
    assert login(c, email='LOCAL@example.com').status_code == 200
    assert c.cookies.get(settings.session_cookie) != before
    info = c.get('/api/v1/auth/me').json()
    assert info['user']['id'] == user_id
    c.headers['X-CSRF-Token'] = info['csrf_token']
    assert c.put('/api/v1/users/me', json={'name': 'Local', 'email': 'contact@example.com', 'theme_accent': 'green', 'theme_background': 'white'}).status_code == 200
    assert c.get('/api/v1/auth/password/account').json()['login_email'] == 'local@example.com'
    with factory() as db:
        assert db.get(User, user_id).last_login_at is not None
        assert db.get(PasswordCredential, user_id).password_hash.startswith('$argon2id$')


def test_resend_reset_revokes_sessions_and_links(local):
    factory, client, _ = local
    admin, user_id = create(client)
    first = secret(factory)
    assert admin.post(f'/api/v1/admin/users/{user_id}/password/invite').status_code == 200
    second = secret(factory)
    c = anonymous(client)
    assert set_password(c, first).status_code == 400
    assert set_password(c, second).status_code == 200
    assert login(c).status_code == 200
    assert admin.post(f'/api/v1/admin/users/{user_id}/password/invite').status_code == 409
    assert admin.post(f'/api/v1/admin/users/{user_id}/password/reset').status_code == 200
    row = next(row for row in admin.get('/api/v1/admin/users').json() if row['id'] == user_id)
    assert row['mail_status'] == 'queued'
    assert c.get('/api/v1/auth/me').json()['user'] is None
    c = anonymous(client)
    assert login(c).status_code == 401
    assert set_password(c, secret(factory), 'a different strong password').status_code == 200
    assert login(c, 'a different strong password').status_code == 200


def test_change_password_reauthenticates_current_session_and_revokes_others(local):
    factory, client, _ = local
    create(client)
    c, other = anonymous(client), anonymous(client)
    assert set_password(c, secret(factory)).status_code == 200
    assert login(c).status_code == 200 and login(other).status_code == 200
    c.headers['X-CSRF-Token'] = c.get('/api/v1/auth/me').json()['csrf_token']
    path = '/api/v1/auth/password/change'
    assert c.post(path, json={'current_password': 'wrong', 'password': 'a replacement password'}).status_code == 400
    assert c.post(path, json={'current_password': 'a long test password', 'password': 'a replacement password'}).status_code == 200
    assert c.get('/api/v1/auth/me').json()['user'] is not None
    assert other.get('/api/v1/auth/me').json()['user'] is None
    other = anonymous(client)
    assert login(other).status_code == 401
    assert login(other, 'a replacement password').status_code == 200


def test_expiry_disable_csrf_short_password_and_admin_permissions(local):
    factory, client, people = local
    _, user_id = create(client)
    token = secret(factory)
    c = anonymous(client)
    invalid = set_password(c, token, 'tiny-secret')
    assert invalid.status_code == 422 and 'tiny-secret' not in invalid.text and token not in invalid.text
    c.headers.pop('X-CSRF-Token')
    assert set_password(c, token).status_code == 403
    c = anonymous(client)
    with factory() as db:
        db.scalar(select(PasswordLink).where(PasswordLink.user_id == user_id)).expires_at = int(time.time()) - 1
        db.commit()
    assert set_password(c, token).status_code == 400
    assert client('member').post('/api/v1/admin/users', json={'name': 'Test', 'email': 'new@example.com'}).status_code == 403
    assert client('member').post(f'/api/v1/admin/users/{people["member"]}/password/reset').status_code == 403
    assert c.post('/api/v1/auth/password/reset', json={'email': 'local@example.com'}).status_code in {404, 405}


def test_duplicate_email_and_external_identity_never_merge(local):
    factory, client, people = local
    create(client)
    admin = client('administrator')
    assert admin.post('/api/v1/admin/users', json={'name': 'Duplicate', 'email': 'LOCAL@example.com'}).status_code == 409
    with factory() as db:
        db.get(User, people['member']).email = 'existing@example.com'
        db.commit()
    response = admin.post('/api/v1/admin/users', json={'name': 'Separate', 'email': 'existing@example.com'})
    assert response.status_code == 200 and response.json()['id'] != people['member']


def test_login_email_change_forces_new_setup(local):
    factory, client, _ = local
    admin, user_id = create(client)
    c = anonymous(client)
    assert set_password(c, secret(factory)).status_code == 200
    assert login(c).status_code == 200
    assert admin.put(f'/api/v1/admin/users/{user_id}/login-email', json={'email': 'replacement@example.com'}).status_code == 200
    assert c.get('/api/v1/auth/me').json()['user'] is None
    c = anonymous(client)
    assert login(c).status_code == 401
    assert set_password(c, secret(factory)).status_code == 200
    assert login(c, email='replacement@example.com').status_code == 200


def test_login_is_rate_limited_and_disabled_account_cannot_login(local):
    factory, client, _ = local
    _, user_id = create(client)
    c = anonymous(client)
    assert set_password(c, secret(factory)).status_code == 200
    with factory() as db:
        db.get(User, user_id).active = False
        db.commit()
    assert login(c).status_code == 401
    for _ in range(9):
        assert login(c, 'incorrect password').status_code == 401
    assert login(c).status_code == 429


def test_smtp_retry_delivery_and_payload_erasure(local, monkeypatch):
    factory, client, _ = local
    create(client)
    sent = []
    class SMTP:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def starttls(self, **kwargs): pass
        def send_message(self, message):
            if not sent:
                sent.append(None)
                raise OSError('temporary failure')
            sent.append(message)
    monkeypatch.setattr(mail.smtplib, 'SMTP', SMTP)
    mail.deliver_pending()
    with factory() as db:
        link = db.scalar(select(PasswordLink))
        assert link.attempts == 1 and link.delivery_status == 'queued' and link.encrypted_body
        link.next_attempt_at = 0
        db.commit()
    mail.deliver_pending()
    assert '#token=' in sent[-1].get_content()
    with factory() as db:
        link = db.scalar(select(PasswordLink))
        assert link.delivery_status == 'sent' and link.encrypted_body is None and link.attempts == 2


def test_bearer_cannot_manage_or_create_browser_credentials(local):
    from test_api_tokens import issue, bearer
    factory, client, _ = local
    admin, user_id = create(client)
    token = secret(factory)
    c = bearer(issue(admin, ['read', 'write'])['token'])
    assert c.post('/api/v1/admin/users', json={'name': 'Forbidden', 'email': 'no@example.com'}).status_code == 403
    assert c.post(f'/api/v1/admin/users/{user_id}/password/reset').status_code == 403
    assert c.post('/api/v1/auth/password/setup', json={'token': token, 'password': 'a long test password'}).status_code == 403
    assert login(c).status_code == 403
    assert c.get('/api/v1/auth/password/account').status_code == 403
    assert 'set-cookie' not in c.get('/api/v1/auth/password/account').headers


def test_outbox_expires_without_sending_and_disabled_feature_rejects_links(local, monkeypatch):
    factory, client, _ = local
    create(client)
    token = secret(factory)
    c = anonymous(client)
    monkeypatch.setattr(settings, 'password_enabled', False)
    assert login(c).status_code == 404
    assert set_password(c, token).status_code == 404
    monkeypatch.setattr(settings, 'password_enabled', True)
    with factory() as db:
        db.scalar(select(PasswordLink)).expires_at = 0
        db.commit()
    monkeypatch.setattr(mail.smtplib, 'SMTP', lambda *args, **kwargs: pytest.fail('Expired links must not be mailed'))
    mail.deliver_pending()
    with factory() as db:
        link = db.scalar(select(PasswordLink))
        assert link.delivery_status == 'canceled' and link.encrypted_body is None


def test_local_bootstrap_without_external_provider(local, monkeypatch, capsys):
    import sys
    from app import cli
    factory, _, people = local
    with factory() as db:
        db.get(User, people['administrator']).role = 'member'
        db.commit()
    monkeypatch.setattr(cli, 'SessionLocal', factory)
    monkeypatch.setattr(sys, 'argv', ['tracker', 'bootstrap-admin', '--local', '--name', 'First local admin', '--email', 'bootstrap@example.com'])
    cli.main()
    output = capsys.readouterr().out
    assert 'invitation queued' in output and '#token' not in output
    with factory() as db:
        credential = db.scalar(select(PasswordCredential).where(PasswordCredential.login_email == 'bootstrap@example.com'))
        assert credential and db.get(User, credential.user_id).role == 'administrator'
    with pytest.raises(SystemExit):
        cli.main()

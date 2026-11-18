from datetime import datetime, timezone

from app.main import app
from app.models import ExternalIdentity, ProjectMember, User
from app.providers import ExternalProfile
from test_access import project


def test_application_users_include_inactive_and_pending_but_not_bots(env):
    factory, client, people = env
    recorded = datetime(2026, 1, 2, 12, 30, tzinfo=timezone.utc)
    with factory() as db:
        db.get(User, people['member']).last_login_at = recorded
        db.get(User, people['reader']).active = False
        bot = User(name='Automation', email='', role='member', is_bot=True)
        db.add(bot)
        db.commit()
        bot_id = bot.id
    response = client('administrator').get('/api/v1/admin/users')
    assert response.status_code == 200
    rows = {row['id']: row for row in response.json()}
    assert set(rows) == set(people.values()) and bot_id not in rows
    assert rows[people['administrator']]['role'] == 'administrator'
    assert rows[people['outsider']]['role'] is None
    assert rows[people['reader']]['active'] is False
    assert rows[people['member']]['last_login_at'] == recorded.isoformat()
    assert rows[people['administrator']]['last_login_at'] is None
    assert set(rows[people['member']]) == {'id', 'name', 'email', 'role', 'active', 'avatar_url', 'last_login_at',
                                         'login_method', 'login_email', 'password_set', 'mail_status'}


def test_user_overview_is_for_application_admins_not_project_admins(env):
    factory, client, people = env
    pid = project(client('administrator'))
    with factory() as db:
        db.merge(ProjectMember(project_id=pid, user_id=people['member'], role='owner'))
        db.commit()
    for role in ['member', 'reader', 'outsider']:
        assert client(role).get('/api/v1/admin/users').status_code == 403
    assert client().get('/api/v1/admin/users').status_code == 401


def test_only_successful_oidc_login_updates_last_login(env):
    factory, client, people = env
    old = datetime(2020, 1, 1, tzinfo=timezone.utc)
    with factory() as db:
        db.add(ExternalIdentity(user_id=people['member'], issuer='https://identity.example', subject='member-subject'))
        db.get(User, people['member']).last_login_at = old
        db.commit()

    class Provider:
        async def identity(self, request):
            return ExternalProfile('https://identity.example', 'member-subject', 'Provider Name', 'member@example.test')

    member = client('member')
    with member:
        app.state.provider = Provider()
        before = datetime.now(timezone.utc)
        assert member.get('/api/v1/auth/oidc/callback', follow_redirects=False).status_code == 303
        after = datetime.now(timezone.utc)
        with factory() as db:
            last_login = db.get(User, people['member']).last_login_at.replace(tzinfo=timezone.utc)
            assert before <= last_login <= after
        assert member.get('/api/v1/auth/me').status_code == 200
        with factory() as db:
            assert db.get(User, people['member']).last_login_at.replace(tzinfo=timezone.utc) == last_login
            db.get(User, people['member']).active = False
            db.commit()
        assert member.get('/api/v1/auth/oidc/callback', follow_redirects=False).status_code == 403
        with factory() as db:
            assert db.get(User, people['member']).last_login_at.replace(tzinfo=timezone.utc) == last_login


def test_admin_manages_user_roles_and_last_admin_is_preserved(env):
    _, client, people = env
    admin, member = client('administrator'), client('member')
    own = '/api/v1/admin/users/' + people['administrator']
    path = '/api/v1/admin/users/' + people['member']
    assert admin.put(own, json={'role': 'member', 'active': True}).status_code == 409
    assert admin.put(own, json={'role': 'administrator', 'active': False}).status_code == 409
    assert member.put(path, json={'role': 'administrator', 'active': True}).status_code == 403
    assert admin.put(path, json={'role': 'reader', 'active': True}).status_code == 422
    assert admin.put(path, json={'role': 'administrator', 'active': True}).status_code == 200
    assert member.get('/api/v1/admin/users').status_code == 200
    assert admin.put(own, json={'role': 'member', 'active': True}).status_code == 200
    assert admin.get('/api/v1/admin/users').status_code == 403
    assert member.put(own, json={'role': 'member', 'active': False}).status_code == 200
    assert admin.get('/api/v1/projects').status_code == 401
    member.headers.pop('X-CSRF-Token')
    assert member.put(path, json={'role': 'member', 'active': True}).status_code == 403

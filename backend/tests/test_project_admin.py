from app.models import ProjectMember
from test_access import project


def test_project_creator_is_an_explicit_admin_member(env):
    factory, client, people = env
    admin = client('administrator')
    pid = project(admin)
    with factory() as db:
        membership = db.get(ProjectMember, (pid, people['administrator']))
        assert membership is not None and membership.role == 'administrator'
    members = admin.get(f'/api/v1/projects/{pid}/members').json()
    assert any(member['user_id'] == people['administrator'] and member['role'] == 'administrator' for member in members)


def test_project_admin_can_manage_only_the_assigned_project(env):
    _, client, people = env
    admin, manager = client('administrator'), client('member')
    pid, other = project(admin), project(admin, key='OTHER')
    path = f'/api/v1/projects/{pid}'
    other_path = f'/api/v1/projects/{other}'
    assert admin.put(path + '/members', json={'user_id': people['member'], 'role': 'administrator'}).status_code == 200
    permissions = {p['id']: p for p in manager.get('/api/v1/projects').json()}
    assert permissions[pid]['can_manage'] and permissions[pid]['can_write']
    assert not permissions[other]['can_manage'] and permissions[other]['can_write']
    payload = {'name': 'Managed project', 'description': '', 'visibility': 'private'}
    assert manager.put(path, json=payload).status_code == 200
    assert manager.get(path + '/members').status_code == 200
    assert manager.get(path + '/member-candidates').status_code == 200
    assert manager.get('/api/v1/users').status_code == 403
    assert manager.post('/api/v1/projects', json={'key': 'NO', 'name': 'No'}).status_code == 403
    for suffix in ['/members', '/member-candidates']:
        assert manager.get(other_path + suffix).status_code == 403
    assert manager.put(other_path, json=payload).status_code == 403
    reader = {'user_id': people['reader'], 'role': 'reader'}
    assert manager.put(path + '/members', json=reader).status_code == 200
    assert manager.delete(path + '/members/' + people['reader']).status_code == 200
    label = {'name': 'Managed', 'color': '#123456'}
    result = manager.post(path + '/labels', json=label)
    assert result.status_code == 201
    label_path = path + '/labels/' + result.json()['id']
    assert manager.put(label_path, json={**label, 'name': 'Renamed'}).status_code == 200
    assert manager.delete(label_path).status_code == 200
    assert manager.post(other_path + '/labels', json=label).status_code == 403
    assert manager.post('/api/v1/organization/labels', json=label).status_code == 403
    assert manager.post(path + '/items', json={'title': 'Contribution'}).status_code == 201
    manager.headers.pop('X-CSRF-Token')
    assert manager.put(path, json=payload).status_code == 403


def test_member_can_contribute_but_not_manage_and_demotion_is_immediate(env):
    _, client, people = env
    admin, member = client('administrator'), client('member')
    path = f'/api/v1/projects/{project(admin)}'
    membership = {'user_id': people['member'], 'role': 'administrator'}
    assert admin.put(path + '/members', json=membership).status_code == 200
    assert member.put(path + '/members', json={**membership, 'role': 'member'}).status_code == 200
    assert not next(p for p in member.get('/api/v1/projects').json() if path.endswith(p['id']))['can_manage']
    assert member.post(path + '/items', json={'title': 'Member contribution'}).status_code == 201
    assert member.get(path + '/members').status_code == 403
    assert member.get(path + '/member-candidates').status_code == 403
    assert member.put(path + '/members', json=membership).status_code == 403
    assert member.delete(path + '/members/' + people['member']).status_code == 403
    assert member.put(path, json={'name': 'No', 'description': '', 'visibility': 'organization'}).status_code == 403
    assert member.post(path + '/labels', json={'name': 'No', 'color': '#123456'}).status_code == 403


def test_reader_and_bot_cannot_gain_project_admin_permissions(env):
    factory, client, people = env
    admin, reader = client('administrator'), client('reader')
    pid = project(admin, 'private')
    path = f'/api/v1/projects/{pid}'
    assert reader.get(path + '/member-candidates').status_code == 404
    assert admin.put(path + '/members', json={'user_id': people['reader'], 'role': 'administrator'}).status_code == 403
    # Legacy data must not bypass the current organization permission ceiling.
    with factory() as db:
        db.add(ProjectMember(project_id=pid, user_id=people['reader'], role='administrator'))
        db.commit()
    result = reader.get('/api/v1/projects').json()[0]
    assert not result['can_manage'] and not result['can_write']
    assert reader.get(path + '/members').status_code == 403
    assert reader.post(path + '/items', json={'title': 'No'}).status_code == 403
    bot = admin.post('/api/v1/bots', json={'name': 'Bot', 'role': 'member'}).json()
    assert admin.put(path + '/members', json={'user_id': bot['id'], 'role': 'administrator'}).status_code == 403

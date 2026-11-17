from app.models import ProjectMember, User
from test_access import project


def test_project_creator_is_an_explicit_admin_member(env):
    factory, client, people = env
    admin = client('administrator')
    pid = project(admin)
    with factory() as db:
        membership = db.get(ProjectMember, (pid, people['administrator']))
        assert membership is not None and membership.role == 'owner'
    members = admin.get(f'/api/v1/projects/{pid}/members').json()
    assert any(member['user_id'] == people['administrator'] and member['role'] == 'owner' and member['inherited'] for member in members)


def test_project_admin_can_manage_only_the_assigned_project(env):
    _, client, people = env
    admin, manager = client('administrator'), client('member')
    pid, other = project(admin), project(admin, key='OTHER')
    path = f'/api/v1/projects/{pid}'
    other_path = f'/api/v1/projects/{other}'
    assert admin.put(path + '/members', json={'user_id': people['member'], 'role': 'owner'}).status_code == 200
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
    reader = {'user_id': people['reader'], 'role': 'read-only'}
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
    membership = {'user_id': people['member'], 'role': 'owner'}
    assert admin.put(path + '/members', json=membership).status_code == 200
    assert member.put(path + '/members', json={**membership, 'role': 'reporter'}).status_code == 200
    assert not next(p for p in member.get('/api/v1/projects').json() if path.endswith(p['id']))['can_manage']
    assert member.post(path + '/items', json={'title': 'Member contribution'}).status_code == 201
    assert member.get(path + '/members').status_code == 403
    assert member.get(path + '/member-candidates').status_code == 403
    assert member.put(path + '/members', json=membership).status_code == 403
    assert member.delete(path + '/members/' + people['member']).status_code == 403
    assert member.put(path, json={'name': 'No', 'description': '', 'visibility': 'organization'}).status_code == 403
    assert member.post(path + '/labels', json={'name': 'No', 'color': '#123456'}).status_code == 403


def test_application_members_can_be_owners_but_bots_cannot(env):
    factory, client, people = env
    admin, reader = client('administrator'), client('reader')
    pid = project(admin, 'private')
    path = f'/api/v1/projects/{pid}'
    assert reader.get(path + '/member-candidates').status_code == 404
    assert admin.put(path + '/members', json={'user_id': people['reader'], 'role': 'owner'}).status_code == 200
    result = reader.get('/api/v1/projects').json()[0]
    assert result['can_manage'] and result['can_write']
    assert reader.get(path + '/members').status_code == 200
    assert reader.post(path + '/items', json={'title': 'Allowed'}).status_code == 201
    bot = admin.post('/api/v1/bots', json={'name': 'Bot', 'role': 'member'}).json()
    assert admin.put(path + '/members', json={'user_id': bot['id'], 'role': 'owner'}).status_code == 403
    assert reader.put(path + '/members', json={'user_id': bot['id'], 'role': 'reporter'}).status_code == 403
    assert admin.put(path + '/members', json={'user_id': bot['id'], 'role': 'reporter'}).status_code == 200
    assert reader.delete(path + '/members/' + bot['id']).status_code == 403


def test_application_admins_are_permanent_owners_without_explicit_membership(env):
    factory, client, people = env
    admin = client('administrator')
    pid = project(admin, 'private')
    path = f'/api/v1/projects/{pid}/members'
    with factory() as db:
        db.delete(db.get(ProjectMember, (pid, people['administrator'])))
        db.get(User, people['member']).role = 'administrator'
        db.commit()
    members = admin.get(path).json()
    assert len(members) == 2
    assert all(row['role'] == 'owner' and row['inherited'] for row in members)
    for name in ['administrator', 'member']:
        actor = client(name)
        assert actor.get('/api/v1/projects').json()[0]['can_manage']
        for target in ['administrator', 'member']:
            assert actor.delete(path + '/' + people[target]).status_code == 403
            for role in ['owner', 'reporter', 'read-only']:
                assert actor.put(path, json={'user_id': people[target], 'role': role}).status_code == 403


def test_unassigned_member_cannot_see_organization_visibility_projects(env):
    _, client, _ = env
    admin, member = client('administrator'), client('member')
    response = admin.post('/api/v1/projects', json={'key': 'HIDDEN', 'name': 'Hidden', 'visibility': 'organization'})
    pid = response.json()['id']
    item = admin.post(f'/api/v1/projects/{pid}/items', json={'title': 'Protected'}).json()
    assert member.get('/api/v1/projects').json() == []
    for suffix in ['/items', '/members', '/labels', '/assignees', '/member-candidates']:
        assert member.get(f'/api/v1/projects/{pid}' + suffix).status_code == 404
    assert member.get('/api/v1/items/' + item['id']).status_code == 404
    assert member.post('/api/v1/references/resolve', json={'tickets': [item['id']]}).json()['tickets'] == []

def create_project(admin):
    response = admin.post('/api/v1/projects', json={'key': 'APP', 'name': 'Original project'})
    assert response.status_code == 201
    return response.json()


def test_update_project_preserves_identifiers_and_changes_visibility(env):
    _, client, _ = env
    admin, member = client('administrator'), client('member')
    project = create_project(admin)
    path = f"/api/v1/projects/{project['id']}"
    assert len(member.get('/api/v1/projects').json()) == 1
    response = admin.put(path, json={'name': ' Renamed project ', 'description': 'New description', 'visibility': 'private'})
    assert response.status_code == 200
    updated = response.json()
    assert updated['name'] == 'Renamed project'
    assert updated['description'] == 'New description'
    assert updated['visibility'] == 'private'
    for field in ('id', 'key', 'slug'):
        assert updated[field] == project[field]
    assert member.get('/api/v1/projects').json() == []
    assert member.get(path + '/items').status_code == 404
    assert admin.get('/api/v1/projects').json()[0]['name'] == 'Renamed project'


def test_project_settings_require_administrator_and_csrf(env):
    _, client, _ = env
    admin = client('administrator')
    project = create_project(admin)
    path = f"/api/v1/projects/{project['id']}"
    payload = {'name': 'Changed', 'description': '', 'visibility': 'organization'}
    for role in ('member', 'reader'):
        assert client(role).put(path, json=payload).status_code == 403
    admin.headers.pop('X-CSRF-Token')
    assert admin.put(path, json=payload).status_code == 403
    assert client().put(path, json=payload).status_code == 403


def test_project_settings_validation_and_private_isolation(env):
    _, client, _ = env
    admin = client('administrator')
    project = create_project(admin)
    path = f"/api/v1/projects/{project['id']}"
    payload = {'name': 'Private project', 'description': '', 'visibility': 'private'}
    for invalid in ({'name': '  '}, {'visibility': 'public'}, {'slug': 'different'}, {'key': 'OTHER'}):
        assert admin.put(path, json={**payload, **invalid}).status_code == 422
    assert admin.put(path, json=payload).status_code == 200
    assert client('member').put(path, json=payload).status_code == 404
    assert admin.put('/api/v1/projects/missing', json=payload).status_code == 404

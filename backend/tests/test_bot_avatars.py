import io

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


def picture(color='green'):
    output = io.BytesIO()
    Image.new('RGB', (400, 200), color).save(output, format='PNG')
    return {'file': ('picture.png', output.getvalue(), 'image/png')}


def test_bot_avatar_lifecycle_and_member_response(env):
    _, client, _ = env
    admin = client('administrator')
    bot = admin.post('/api/v1/bots', json={'name': 'Avatar bot'}).json()
    path = f"/api/v1/bots/{bot['id']}/avatar"
    assert bot['avatar_url'] is None
    uploaded = admin.put(path, files=picture())
    assert uploaded.status_code == 200
    url = uploaded.json()['avatar_url']
    response = client('reader').get(url)
    assert response.status_code == 200
    with Image.open(io.BytesIO(response.content)) as image:
        assert image.size == (256, 256) and image.format == 'PNG'
    assert admin.get('/api/v1/bots').json()[0]['avatar_url'] == url
    project = admin.post('/api/v1/projects', json={'key': 'AV', 'name': 'Avatar project'}).json()
    members = f"/api/v1/projects/{project['id']}/members"
    admin.put(members, json={'user_id': bot['id'], 'role': 'reader'})
    assert admin.get(members).json()[0]['avatar_url'] == url
    replaced = admin.put(path, files=picture('blue')).json()['avatar_url']
    assert replaced != url
    assert admin.put(f"/api/v1/bots/{bot['id']}", json={'name': bot['name'], 'role': bot['role'], 'active': False}).status_code == 200
    assert client('reader').get(replaced).status_code == 200
    assert client('outsider').get(replaced).status_code == 404
    assert client().get(replaced).status_code == 401
    assert admin.delete(path).json()['avatar_url'] is None
    assert admin.get(replaced).status_code == 404


def test_bot_avatar_requires_admin_browser_session_and_csrf(env):
    _, client, people = env
    admin = client('administrator')
    bot = admin.post('/api/v1/bots', json={'name': 'Avatar bot'}).json()
    path = f"/api/v1/bots/{bot['id']}/avatar"
    for role in ('member', 'reader'):
        account = client(role)
        assert account.put(path, files=picture()).status_code == 403
        assert account.delete(path).status_code == 403
    token = admin.post('/api/v1/tokens', json={'name': 'Avatar test', 'scopes': ['read', 'write']}).json()['token']
    with TestClient(app, headers={'Authorization': f'Bearer {token}'}) as api_client:
        assert api_client.put(path, files=picture()).status_code == 403
        assert api_client.delete(path).status_code == 403
    assert admin.put(f"/api/v1/bots/{people['member']}/avatar", files=picture()).status_code == 404
    admin.headers.pop('X-CSRF-Token')
    assert admin.put(path, files=picture()).status_code == 403
    assert admin.delete(path).status_code == 403


def test_invalid_bot_avatar_keeps_previous_image(env):
    _, client, _ = env
    admin = client('administrator')
    bot = admin.post('/api/v1/bots', json={'name': 'Avatar bot'}).json()
    path = f"/api/v1/bots/{bot['id']}/avatar"
    original = admin.put(path, files=picture()).json()['avatar_url']
    assert admin.put(path, files={'file': ('invalid.png', b'not an image')}).status_code == 422
    assert admin.put(path, files={'file': ('large.png', b'x' * (5 * 1024 * 1024 + 1))}).status_code == 413
    assert admin.get('/api/v1/bots').json()[0]['avatar_url'] == original

import pytest
from app.models import Project
from conftest import grant_project_access


def create_project(client, key="APP", name="Product development", **values):
    response = client.post("/api/v1/projects", json={"key": key, "name": name, **values})
    assert response.status_code == 201, response.text
    return response.json()


def create_ticket(client, project):
    response = client.post(f"/api/v1/projects/{project['id']}/items", json={"title": "Verify readable URL"})
    assert response.status_code == 201
    return response.json()


def test_ticket_number_is_scoped_to_project_slug(env):
    _, client, _ = env
    admin = client("administrator")
    first = create_project(admin)
    second = create_project(admin, key="OTHER", name="Other team")
    first_item = create_ticket(admin, first)
    second_item = create_ticket(admin, second)
    for project, item in [(first, first_item), (second, second_item)]:
        assert item["number"] == 1
        assert item["project_slug"] == project["slug"]
        assert item["web_url"] == f"/{project['slug']}/1"
        response = admin.get(f"/api/v1/projects/by-slug/{project['slug']}/items/1")
        assert response.status_code == 200
        assert response.json()["id"] == item["id"]
        assert response.json()["web_url"] == item["web_url"]
        assert admin.get(f"/api/v1/items/{item['id']}").json() == response.json()
    assert first_item["id"] != second_item["id"]
    assert first["slug"] == first['key'] == "APP"


def test_project_url_comes_from_key_and_rejects_independent_slug(env):
    _, client, _ = env
    admin = client("administrator")
    first = create_project(admin, name="Vývoj aplikace!")
    second = create_project(admin, key="NEXT", name="Vyvoj aplikace")
    custom = create_project(admin, key="CUSTOM", name="Custom project", slug="CUSTOM")
    assert first["slug"] == "APP"
    assert second["slug"] == "NEXT"
    assert custom["slug"] == "CUSTOM"
    assert admin.post("/api/v1/projects", json={"key": "CLASH", "name": "Another", "slug": "my-project"}).status_code == 422
    assert admin.post("/api/v1/projects", json={"key": "APP", "name": "Duplicate"}).status_code == 409
    assert admin.get("/api/v1/projects").json()[0].get("slug")


@pytest.mark.parametrize("slug", ["settings", "items", "api", "projects", "assets", "With spaces", "UPPER", "a/b", "-leading", "trailing-", "a--b", "", "x" * 101])
def test_invalid_and_reserved_slugs_are_rejected(env, slug):
    _, client, _ = env
    assert client("administrator").post("/api/v1/projects", json={"key": "APP", "name": "App", "slug": slug}).status_code == 422


def test_project_names_do_not_affect_url_and_reserved_keys_are_rejected(env):
    _, client, _ = env
    admin = client("administrator")
    assert create_project(admin, name="Settings")["slug"] == "APP"
    first = create_project(admin, key="LONG", name="a" * 150)
    second = create_project(admin, key="LONGER", name="a" * 150)
    assert first["slug"] == "LONG"
    assert second["slug"] == "LONGER"
    assert create_project(admin, key="UNICODE", name="東京")["slug"] == "UNICODE"
    for key in ['API', 'ASSETS', 'ITEMS', 'PROJECTS', 'SETTINGS']:
        assert admin.post('/api/v1/projects', json={'key': key, 'name': 'Reserved'}).status_code == 422


def test_existing_slug_is_an_authorized_alias_for_key_url(env):
    factory, client, people = env
    admin, member = client('administrator'), client('member')
    project = create_project(admin)
    item = create_ticket(admin, project)
    with factory() as db:
        db.get(Project, project['id']).slug = 'product-development'
        db.commit()
    row = admin.get('/api/v1/projects').json()[0]
    assert row['slug'] == 'APP' and row['legacy_slug'] == 'product-development'
    for slug in ['APP', 'product-development']:
        endpoint = f'/api/v1/projects/by-slug/{slug}/items/1'
        resolved = admin.get(endpoint)
        assert resolved.status_code == 200
        assert resolved.json()['id'] == item['id']
        assert resolved.json()['web_url'] == '/APP/1'
        assert resolved.json()['project_slug'] == 'APP'
        assert member.get(endpoint).status_code == 404
    references = admin.post('/api/v1/references/resolve', json={'tickets': [item['id']]}).json()
    assert references['tickets'][0]['href'] == '/APP/1'
    assert admin.put(f"/api/v1/projects/{project['id']}", json={
        'name': 'Renamed', 'description': '', 'visibility': 'private'}).json()['slug'] == 'APP'
    assert admin.get('/api/v1/projects/by-slug/product-development/items/1').json()['web_url'] == '/APP/1'


def test_slug_lookup_preserves_private_project_access(env):
    _, client, _ = env
    admin, member, reader = client("administrator"), client("member"), client("reader")
    private = create_project(admin, visibility="private")
    ticket = create_ticket(admin, private)
    path = f"/api/v1/projects/by-slug/{private['slug']}/items/{ticket['number']}"
    assert admin.get(path).status_code == 200
    assert member.get(path).status_code == 404
    assert member.get(path).json() == member.get("/api/v1/projects/by-slug/missing-project/items/1").json()
    assert reader.get(path).status_code == 404
    assert client().get(path).status_code == 401
    public = create_project(admin, key="PUB", name="Public team")
    grant_project_access(admin, public['id'])
    public_item = create_ticket(admin, public)
    assert reader.get(f"/api/v1/projects/by-slug/{public['slug']}/items/1").json()["id"] == public_item["id"]
    for slug, number in [(public["slug"], 999), ("missing-project", 1), (public["slug"], 0), (public["slug"], -1)]:
        assert admin.get(f"/api/v1/projects/by-slug/{slug}/items/{number}").status_code == 404

import pytest


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
    assert first["slug"] == "product-development"


def test_slug_normalization_collisions_and_optional_custom_slug(env):
    _, client, _ = env
    admin = client("administrator")
    first = create_project(admin, name="Vývoj aplikace!")
    second = create_project(admin, key="NEXT", name="Vyvoj aplikace")
    custom = create_project(admin, key="CUSTOM", name="Custom project", slug="my-project")
    assert first["slug"] == "vyvoj-aplikace"
    assert second["slug"] == "vyvoj-aplikace-2"
    assert custom["slug"] == "my-project"
    assert admin.post("/api/v1/projects", json={"key": "CLASH", "name": "Another", "slug": "my-project"}).status_code == 409
    assert admin.get("/api/v1/projects").json()[0].get("slug")


@pytest.mark.parametrize("slug", ["settings", "items", "api", "projects", "assets", "With spaces", "UPPER", "a/b", "-leading", "trailing-", "a--b", "", "x" * 101])
def test_invalid_and_reserved_slugs_are_rejected(env, slug):
    _, client, _ = env
    assert client("administrator").post("/api/v1/projects", json={"key": "APP", "name": "App", "slug": slug}).status_code == 422


def test_automatic_slug_handles_reserved_names_and_truncation(env):
    _, client, _ = env
    admin = client("administrator")
    assert create_project(admin, name="Settings")["slug"] == "settings-project"
    first = create_project(admin, key="LONG", name="a" * 150)
    second = create_project(admin, key="LONGER", name="a" * 150)
    assert len(first["slug"]) == len(second["slug"]) == 100
    assert second["slug"].endswith("-2")
    assert create_project(admin, key="UNICODE", name="東京")["slug"] == "project"


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
    public_item = create_ticket(admin, public)
    assert reader.get(f"/api/v1/projects/by-slug/{public['slug']}/items/1").json()["id"] == public_item["id"]
    for slug, number in [(public["slug"], 999), ("missing-project", 1), (public["slug"], 0), (public["slug"], -1)]:
        assert admin.get(f"/api/v1/projects/by-slug/{slug}/items/{number}").status_code == 404

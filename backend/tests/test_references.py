from sqlalchemy import select

from app.models import ProjectMember, User
from conftest import grant_project_access


def project(client, key, name, visibility="organization"):
    response = client.post("/api/v1/projects", json={"key": key, "name": name, "visibility": visibility})
    assert response.status_code == 201
    if visibility == 'organization':
        grant_project_access(client, response.json()['id'])
    return response.json()


def ticket(client, project_id, title):
    response = client.post(f"/api/v1/projects/{project_id}/items", json={"title": title})
    assert response.status_code == 201
    return response.json()


def test_suggestions_respect_visibility_and_project_number_context(env):
    _, client, _ = env
    admin, member = client("administrator"), client("member")
    public = project(admin, "APP", "Application")
    other = project(admin, "OTHER", "Other team")
    private = project(admin, "SECRET", "Private team", "private")
    first = ticket(admin, public["id"], "Fix keyboard navigation")
    second = ticket(admin, other["id"], "Another keyboard task")
    hidden = ticket(admin, private["id"], "Secret keyboard design")
    results = member.get("/api/v1/references/tickets?q=keyboard").json()
    assert {row["id"] for row in results} == {first["id"], second["id"]}
    assert all("Secret" not in str(row) for row in results)
    results = member.get(f"/api/v1/references/tickets?q=1&project_id={public['id']}").json()
    assert [row["id"] for row in results] == [first["id"]]
    assert results[0]["href"] == "/APP/1" and results[0]["status"] == "Open"
    results = member.get(f"/api/v1/references/tickets?q=OTHER-1&project_id={public['id']}").json()
    assert [row["id"] for row in results] == [second["id"]]
    assert member.get("/api/v1/references/tickets?q=SECRET-1").json() == []
    assert member.get(f"/api/v1/references/tickets?project_id={private['id']}").status_code == 404
    assert member.get("/api/v1/references/tickets?q=99999999999999999999999").json() == []
    assert member.get("/api/v1/references/tickets?q=%25").json() == []
    assert client().get("/api/v1/references/tickets").status_code == 401
    assert client("outsider").get("/api/v1/references/tickets").status_code == 403
    assert admin.get("/api/v1/references/tickets?q=SECRET-1").json()[0]["id"] == hidden["id"]


def test_reference_resolution_never_returns_private_metadata_to_other_readers(env):
    _, client, people = env
    admin, reader = client("administrator"), client("reader")
    public = project(admin, "APP", "Application")
    private = project(admin, "SECRET", "Private team", "private")
    visible = ticket(admin, public["id"], "Public title")
    hidden = ticket(admin, private["id"], "Private title")
    payload = {"tickets": [visible["id"], hidden["id"]], "users": [people["member"], people["outsider"]]}
    results = reader.post("/api/v1/references/resolve", json=payload).json()
    assert [row["id"] for row in results["tickets"]] == [visible["id"]]
    assert [row["id"] for row in results["users"]] == [people["member"]]
    assert "Private" not in str(results) and "SECRET" not in str(results)
    assert "email" not in results["users"][0] and "theme_accent" not in results["users"][0]
    assert len(admin.post("/api/v1/references/resolve", json=payload).json()["tickets"]) == 2
    changed = admin.put(f"/api/v1/items/{visible['id']}", json={"title": "Renamed public ticket", "status": "Done"})
    assert changed.status_code == 200
    fresh = reader.post("/api/v1/references/resolve", json={"tickets": [visible["id"]]}).json()["tickets"][0]
    assert fresh["title"] == "Renamed public ticket" and fresh["status"] == "Done"


def test_user_search_is_available_to_members_and_scoped_for_private_projects(env):
    factory, client, people = env
    admin, member = client("administrator"), client("member")
    assert member.get("/api/v1/references/users?q=reader").json()[0]["id"] == people["reader"]
    private = project(admin, "PRIVATE", "Private team", "private")
    with factory() as db:
        db.add(ProjectMember(project_id=private["id"], user_id=people["member"], role="reporter"))
        db.commit()
    results = member.get(f"/api/v1/references/users?project_id={private['id']}").json()
    assert {row["id"] for row in results} == {people["administrator"], people["member"]}
    target = member.get(f"/api/v1/references/users/{people['reader']}").json()
    assert target["href"] == f"/users/{people['reader']}" and "email" not in target
    assert member.get(f"/api/v1/references/users/{people['outsider']}").status_code == 404
    with factory() as db:
        db.get(User, people["reader"]).active = False
        db.commit()
    assert member.get("/api/v1/references/users?q=reader").json() == []
    assert member.get(f"/api/v1/references/users/{people['reader']}").status_code == 404


def test_batch_resolution_limits_and_missing_references(env):
    _, client, people = env
    member = client("member")
    assert member.post("/api/v1/references/resolve", json={"tickets": [people["member"]]}).json()["tickets"] == []
    assert member.post("/api/v1/references/resolve", json={"tickets": ["not-a-uuid"]}).status_code == 422
    assert member.post("/api/v1/references/resolve", json={"users": [people["member"]] * 51}).status_code == 422

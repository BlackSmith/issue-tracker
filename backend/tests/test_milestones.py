from app.notification_email import summary_text
from test_access import project
from test_ticket_visibility import set_restriction


def test_milestone_management_requires_project_owner(env):
    _, client, people = env
    admin, reporter, reader = client("administrator"), client("member"), client("reader")
    pid = project(admin)
    private = project(admin, visibility="private", key="PRIV")
    base = f"/api/v1/projects/{pid}/milestones"
    payload = {"name": "  Release 1  ", "description": "First release", "due_date": "2027-01-31"}

    assert reader.get(f"/api/v1/projects/{private}/milestones").status_code == 404
    assert admin.post(base, json={"name": " "}).status_code == 422
    for person in (reporter, reader):
        assert person.post(base, json=payload).status_code == 403

    assert admin.put(f"/api/v1/projects/{pid}/members",
                     json={"user_id": people["member"], "role": "owner"}).status_code == 200
    created = reporter.post(base, json=payload)
    assert created.status_code == 201
    milestone = created.json()
    assert milestone == {**payload, "name": "Release 1", "id": milestone["id"], "project_id": pid, "closed": False}
    assert reader.get(base).json() == [milestone]
    assert reporter.post(base, json=payload).status_code == 409

    path = f'{base}/{milestone["id"]}'
    assert reader.put(path, json=payload).status_code == 403
    assert reader.put(path + "/state", json={"closed": True}).status_code == 403
    assert admin.put(f'/api/v1/projects/{private}/milestones/{milestone["id"]}', json=payload).status_code == 404
    assert reporter.put(path + "/state", json={"closed": True}).json()["closed"] is True
    edited = reporter.put(path, json={"name": "Renamed"}).json()
    assert edited == {**milestone, "name": "Renamed", "description": "", "due_date": None, "closed": True}
    assert reporter.put(path + "/state", json={"closed": False}).json()["closed"] is False


def test_assignment_close_filter_and_legacy_put_respect_ticket_access(env):
    _, client, _ = env
    admin, reporter, reader = client("administrator"), client("member"), client("reader")
    pid = project(admin)
    other = project(admin, key="OTHER")
    set_restriction(admin, pid, True)
    base = f"/api/v1/projects/{pid}"
    catalog = base + "/milestones"
    first = admin.post(catalog, json={"name": 'Done, "Phase 1"'}).json()["id"]
    second = admin.post(catalog, json={"name": "Phase 2"}).json()["id"]
    foreign = admin.post(f"/api/v1/projects/{other}/milestones", json={"name": "Foreign"}).json()["id"]
    items = base + "/items"
    assert reporter.post(items, json={"title": "Wrong project", "milestone_id": foreign}).status_code == 422
    assigned = reporter.post(items, json={"title": "Assigned", "milestone_id": first}).json()
    assert assigned["milestone_id"] == first
    path = f'/api/v1/items/{assigned["id"]}'
    unassigned = reporter.post(items, json={"title": "Unassigned"}).json()
    hidden = admin.post(items, json={"title": "Hidden", "milestone_id": first}).json()
    assert admin.put(f"{catalog}/{first}/state", json={"closed": True}).status_code == 200
    assert reporter.post(items, json={"title": "Too late", "milestone_id": first}).status_code == 409
    assert reporter.patch(f'/api/v1/items/{unassigned["id"]}', json={"milestone_id": first}).status_code == 409
    assert reporter.patch(path, json={"milestone_id": foreign}).status_code == 422
    updated = reporter.put(path, json={"title": "Legacy client"}).json()
    assert updated["milestone_id"] == first and updated["status"] == assigned["status"]
    assert reporter.patch(path, json={"milestone_id": first}).status_code == 200

    def filtered(person, *values):
        response = person.get(items, params=[("milestone", value) for value in values])
        assert response.status_code == 200
        result = response.json()
        assert result["total"] == len(result["items"])
        return {item["id"] for item in result["items"]}

    assert filtered(admin, first) == {assigned["id"], hidden["id"]}
    assert filtered(reporter, first, "none") == {assigned["id"], unassigned["id"]}
    assert filtered(reporter, "none") == {unassigned["id"]}
    assert filtered(reporter, foreign) == set()
    assert filtered(reader, first, "none") == set()
    assert admin.put(path + "/publication", json={"is_project_public": True}).status_code == 200
    assert filtered(reader, first) == {assigned["id"]}
    assert reader.patch(path, json={"milestone_id": second}).status_code == 403

    assert reporter.patch(path, json={"milestone_id": second, "expected": {"milestone_id": None}}).status_code == 409
    assert reporter.patch(path, json={"milestone_id": second, "expected": {"milestone_id": first}}).json()["milestone_id"] == second
    assert reporter.put(path, json={"title": "Cleared", "milestone_id": None}).json()["milestone_id"] is None
    history = [row["body"] for row in reporter.get(path + "/discussion").json()]
    assert 'updated milestone from "Done, \\"Phase 1\\"" to "Phase 2"' in history
    assert history[-1] == 'updated title, milestone from "Phase 2" to No milestone'
    assert summary_text(history[-1], "cs") == 'změnil(a): název, milník z "Phase 2" na bez milníku'

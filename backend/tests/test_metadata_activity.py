from app.models import User
from test_access import item, project


def test_metadata_history_includes_previous_and_new_values(env):
    _, client, _ = env
    admin = client("administrator")
    path = f"/api/v1/items/{item(admin, project(admin))}"
    for name in ['review, QA', 'needs "work"', 'new']:
        assert admin.post("/api/v1/organization/labels", json={"name": name, "color": "#123456"}).status_code == 201
    changes = [
        ({"status": "In progress"}, 'updated status from "Open" to "In progress"'),
        ({"type": "Bug"}, 'updated type from "Task" to "Bug"'),
        ({"priority": "Urgent"}, 'updated priority from "Medium" to "Urgent"'),
        ({"due_date": "2026-12-01"}, 'updated due date to "2026-12-01"'),
        ({"due_date": "2026-12-02"}, 'updated due date from "2026-12-01" to "2026-12-02"'),
        ({"due_date": None}, 'updated due date from "2026-12-02" to Not set'),
        ({"labels": ['review, QA', 'needs "work"']}, 'updated labels from ["auth"] to ["review, QA", "needs \\"work\\""]'),
        ({"labels": []}, 'updated labels from ["review, QA", "needs \\"work\\""] to No labels'),
        ({"labels": ["new"]}, 'updated labels to ["new"]'),
    ]
    for payload, message in changes:
        before = admin.get(path + "/discussion").json()
        response = admin.patch(path, json=payload)
        assert response.status_code == 200, response.text
        entries = admin.get(path + "/discussion").json()
        assert len(entries) == len(before) + 1
        assert entries[-1]["body"] == message
        assert entries[-1]["kind"] == "activity"
        assert entries[-1]["author"] == "administrator"
        assert admin.patch(path, json=payload).status_code == 200
        assert admin.get(path + "/discussion").json() == entries


def test_assignee_history_uses_names_and_preserves_snapshots(env):
    factory, client, people = env
    admin = client("administrator")
    path = f"/api/v1/items/{item(admin, project(admin))}"
    assert admin.patch(path, json={"assignee_id": people["member"]}).status_code == 200
    first = admin.get(path + "/discussion").json()[-1]
    assert first["body"] == 'updated assignee to "member"'
    with factory() as db:
        db.get(User, people["member"]).name = "Renamed member"
        db.commit()
    assert admin.patch(path, json={"assignee_id": people["administrator"]}).status_code == 200
    assert admin.get(path + "/discussion").json()[-1]["body"] == 'updated assignee from "Renamed member" to "administrator"'
    assert admin.patch(path, json={"assignee_id": None}).status_code == 200
    entries = admin.get(path + "/discussion").json()
    assert entries[-1]["body"] == 'updated assignee from "administrator" to Unassigned'
    assert next(entry for entry in entries if entry["id"] == first["id"])["body"] == first["body"]


def test_combined_full_update_records_values_only_for_changed_metadata(env):
    _, client, _ = env
    admin = client("administrator")
    path = f"/api/v1/items/{item(admin, project(admin))}"
    response = admin.put(path, json={"title": "New title", "description": "New description", "status": "Done", "priority": "High", "labels": ["auth"]})
    assert response.status_code == 200, response.text
    assert admin.get(path + "/discussion").json()[-1]["body"] == (
        'updated title, description, status from "Open" to "Done", priority from "Medium" to "High"'
    )


def test_invalid_update_records_no_history_and_preserves_values(env):
    _, client, _ = env
    admin = client("administrator")
    path = f"/api/v1/items/{item(admin, project(admin))}"
    before = admin.get(path + "/discussion").json()
    assert admin.patch(path, json={"priority": "High", "assignee_id": "missing"}).status_code == 422
    assert admin.get(path).json()["priority"] == "Medium"
    assert admin.get(path + "/discussion").json() == before

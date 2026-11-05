from app.models import ProjectMember, User
from test_access import item, project
from test_api_tokens import bearer, issue


def test_member_can_assign_reassign_and_clear_without_changing_other_fields(env):
    _, client, people = env
    admin, member = client("administrator"), client("member")
    pid = project(admin)
    assert admin.post(f"/api/v1/projects/{pid}/labels", json={"name": "auth", "color": "#16a34a"}).status_code == 201
    path = f"/api/v1/items/{item(member, pid)}"
    original = member.get(path).json()
    assert original["assignee_id"] is None and original["assignee"] is None
    for role in ("member", "administrator"):
        response = member.patch(path, json={"assignee_id": people[role]})
        assert response.status_code == 200, response.text
        assigned = response.json()
        assert assigned["assignee_id"] == people[role]
        assert assigned["assignee"] == {"id": people[role], "name": role, "avatar_url": None, "is_bot": False}
        for field in ("title", "description", "type", "status", "priority", "labels", "due_date"):
            assert assigned[field] == original[field]
        assert member.get(path).json()["assignee"] == assigned["assignee"]
        listed = member.get(f"/api/v1/projects/{pid}/items").json()["items"][0]
        assert listed["assignee_id"] == people[role]
    discussion = member.get(path + "/discussion").json()
    assert discussion[-1]["body"] == 'updated assignee from "member" to "administrator"'
    assert member.patch(path, json={"assignee_id": people["administrator"]}).status_code == 200
    assert member.get(path + "/discussion").json() == discussion
    cleared = member.patch(path, json={"assignee_id": None})
    assert cleared.status_code == 200
    assert cleared.json()["assignee_id"] is None and cleared.json()["assignee"] is None


def test_assignable_users_follow_current_roles_project_access_and_bot_membership(env):
    factory, client, people = env
    admin, member = client("administrator"), client("member")
    public_id, private_id = project(admin), project(admin, "private", "PRV")
    with factory() as db:
        inactive = User(name="Inactive", email="inactive@example.test", role="member", active=False)
        bot = User(name="Bot", email="bot@example.test", role="member", is_bot=True)
        db.add_all([inactive, bot])
        db.flush()
        inactive_id, bot_id = inactive.id, bot.id
        db.add(ProjectMember(project_id=private_id, user_id=people["member"], role="member"))
        db.commit()
    public_path = f"/api/v1/projects/{public_id}/assignees"
    private_path = f"/api/v1/projects/{private_id}/assignees"
    assert {row["id"] for row in member.get(public_path).json()} == {people["member"], people["administrator"]}
    assert {row["id"] for row in member.get(private_path).json()} == {people["member"], people["administrator"]}
    for row in member.get(public_path).json():
        assert "email" not in row and "role" not in row
    path = f"/api/v1/items/{item(admin, public_id)}"
    for target in (people["reader"], people["outsider"], inactive_id, bot_id, "missing"):
        assert member.patch(path, json={"assignee_id": target}).status_code == 422
    assert admin.put(f"/api/v1/projects/{public_id}/members", json={"user_id": bot_id, "role": "member"}).status_code == 200
    assert bot_id in {row["id"] for row in member.get(public_path).json()}
    assert member.patch(path, json={"assignee_id": bot_id}).json()["assignee"]["is_bot"] is True
    assert admin.put(f"/api/v1/projects/{public_id}/members", json={"user_id": people["member"], "role": "reader"}).status_code == 200
    assert people["member"] not in {row["id"] for row in admin.get(public_path).json()}
    assert admin.patch(path, json={"assignee_id": people["member"]}).status_code == 422
    assert admin.delete(f"/api/v1/projects/{private_id}/members/{people['member']}").status_code == 200
    assert member.get(private_path).status_code == 404
    assert people["member"] not in {row["id"] for row in admin.get(private_path).json()}


def test_assignee_creation_full_updates_and_later_role_changes(env):
    factory, client, people = env
    admin = client("administrator")
    pid = project(admin)
    created = admin.post(f"/api/v1/projects/{pid}/items", json={"title": "Assigned task", "assignee_id": people["member"]})
    assert created.status_code == 201
    path = f"/api/v1/items/{created.json()['id']}"
    assert created.json()["assignee"]["id"] == people["member"]
    with factory() as db:
        db.get(User, people["member"]).role = "reader"
        db.commit()
    assert people["member"] not in {row["id"] for row in admin.get(f"/api/v1/projects/{pid}/assignees").json()}
    assert admin.patch(path, json={"priority": "High"}).json()["assignee_id"] == people["member"]
    assert admin.get(path).json()["assignee"]["name"] == "member"
    assert admin.patch(path, json={"assignee_id": None}).status_code == 200
    assert admin.patch(path, json={"assignee_id": people["member"]}).status_code == 422
    updated = admin.put(path, json={"title": "Full update", "assignee_id": people["administrator"]})
    assert updated.status_code == 200
    assert updated.json()["assignee_id"] == people["administrator"]
    assert admin.post(f"/api/v1/projects/{pid}/items", json={"title": "Invalid", "assignee_id": people["reader"]}).status_code == 422


def test_reader_csrf_token_scopes_and_private_isolation(env):
    _, client, people = env
    admin, member, reader = client("administrator"), client("member"), client("reader")
    pid, private_id = project(admin), project(admin, "private", "PRV")
    path, private_path = f"/api/v1/items/{item(admin, pid)}", f"/api/v1/items/{item(admin, private_id)}"
    assert reader.get(f"/api/v1/projects/{pid}/assignees").status_code == 403
    assert reader.patch(path, json={"assignee_id": people["member"]}).status_code == 403
    assert member.patch(private_path, json={"assignee_id": people["member"]}).status_code == 404
    read_token = bearer(issue(member)["token"])
    assert read_token.get(f"/api/v1/projects/{pid}/assignees").status_code == 200
    assert read_token.patch(path, json={"assignee_id": people["member"]}).status_code == 403
    write_token = bearer(issue(member, ["write"])["token"])
    assert write_token.patch(path, json={"assignee_id": people["member"]}).status_code == 200
    member.headers.pop("X-CSRF-Token")
    assert member.patch(path, json={"assignee_id": None}).status_code == 403

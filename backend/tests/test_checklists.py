import pytest
from sqlalchemy import select

from app.checklists import checklist_items, content_version, set_checklist_item
from app.models import Activity, Comment, ProjectMember


def setup_ticket(client, visibility="organization", description="- [ ] First task\n- [x] Second task"):
    project = client.post("/api/v1/projects", json={"key": "APP", "name": "Application", "visibility": visibility}).json()
    item = client.post(f"/api/v1/projects/{project['id']}/items", json={"title": "Checklist", "description": description}).json()
    return project, item


def test_task_parser_ignores_non_tasks_and_preserves_source_exactly():
    source = ("# Header\r\n\r\n```md\r\n- [ ] Not a task\r\n```\r\n\r\n"
              "- \\[ ] Escaped\r\n- `[ ] Inline code`\r\n- [ ]\r\n- [ ]  \r\n"
              "- [ ] **Parent** [link](/project/1)\r\n  - [X] Nested `task`\r\n\r\n"
              "> 1. [ ] Quoted task\r\n\r\n<input type=checkbox>\r\n\r\n"
              "![Image](/api/v1/attachments/image/download)\r\n")
    tasks = checklist_items(source)
    assert [task.label for task in tasks] == ["Parent link", "Nested task", "Quoted task"]
    assert [task.checked for task in tasks] == [False, True, False]
    updated, label, changed = set_checklist_item(source, 1, False)
    assert updated == source.replace("[X] Nested", "[ ] Nested")
    assert label == "Nested task" and changed
    assert set_checklist_item(source, 1, True) == (source, "Nested task", False)
    with pytest.raises(IndexError):
        set_checklist_item(source, 3, True)


@pytest.mark.parametrize("separator", ["\v", "\f", "\x85", "\u2028", "\u2029"])
def test_unicode_separators_do_not_shift_task_source_positions(separator):
    source = f"Paragraph{separator}with [ ] literal text\n\n- [ ] Real task\n"
    assert len(checklist_items(source)) == 1
    updated, _, changed = set_checklist_item(source, 0, True)
    assert changed and updated == source.replace("- [ ] Real task", "- [x] Real task")


def test_member_can_toggle_description_and_event_records_actor_and_label(env):
    factory, client, people = env
    admin, member = client("administrator"), client("member")
    _, item = setup_ticket(admin)
    path = f"/api/v1/items/{item['id']}/checklist/0"
    result = member.patch(path, json={"checked": True, "version": item["description_version"]})
    assert result.status_code == 200 and result.json()["changed"]
    saved = member.get(f"/api/v1/items/{item['id']}").json()
    assert saved["description"] == "- [x] First task\n- [x] Second task"
    assert saved["description_version"] == content_version(saved["description"])
    with factory() as db:
        activity = db.scalar(select(Activity).where(Activity.item_id == item["id"], Activity.author_id == people["member"]))
        assert activity.message == 'checked checklist item #1 "First task" in the description'
    result = member.patch(path, json={"checked": False, "version": saved["description_version"]})
    assert result.status_code == 200 and result.json()["text"] == item["description"]
    entries = member.get(f"/api/v1/items/{item['id']}/discussion").json()
    assert entries[-1]["author"] == "member"
    assert entries[-1]["body"] == 'unchecked checklist item #1 "First task" in the description'


def test_member_can_toggle_another_authors_comment_without_changing_authorship(env):
    factory, client, people = env
    admin, member = client("administrator"), client("member")
    _, item = setup_ticket(admin)
    cid = admin.post(f"/api/v1/items/{item['id']}/comments", json={"body": "- [x] Comment task"}).json()["id"]
    entry = next(e for e in member.get(f"/api/v1/items/{item['id']}/discussion").json() if e["id"] == cid)
    response = member.patch(f"/api/v1/items/{item['id']}/comments/{cid}/checklist/0",
                            json={"checked": False, "version": entry["body_version"]})
    assert response.status_code == 200 and response.json()["text"] == "- [ ] Comment task"
    with factory() as db:
        comment = db.get(Comment, cid)
        assert comment.author_id == people["administrator"]
        activity = db.scalar(select(Activity).where(Activity.author_id == people["member"]))
        assert activity.item_id == item["id"] and "unchecked" in activity.message and "in a comment" in activity.message
    assert member.get(f"/api/v1/items/{item['id']}").json()["description"] == item["description"]


@pytest.mark.parametrize("role, visibility, expected", [(None, "organization", 401), ("outsider", "organization", 403),
                                                        ("reader", "organization", 403), ("member", "private", 404)])
def test_checklist_permission_enforced_for_description_and_comments(env, role, visibility, expected):
    _, client, _ = env
    admin, viewer = client("administrator"), client(role)
    _, item = setup_ticket(admin, visibility)
    cid = admin.post(f"/api/v1/items/{item['id']}/comments", json={"body": "- [ ] Comment task"}).json()["id"]
    if role is None:
        token = viewer.get("/api/v1/auth/me").json()["csrf_token"]
        viewer.headers["X-CSRF-Token"] = token
    for path in [f"/api/v1/items/{item['id']}/checklist/0", f"/api/v1/items/{item['id']}/comments/{cid}/checklist/0"]:
        response = viewer.patch(path, json={"checked": True, "version": item["description_version"]})
        assert response.status_code == expected
    assert admin.get(f"/api/v1/items/{item['id']}").json()["description"] == item["description"]


def test_project_reader_cannot_toggle_and_csrf_required(env):
    factory, client, people = env
    admin, member = client("administrator"), client("member")
    project, item = setup_ticket(admin)
    payload = {"checked": True, "version": item["description_version"]}
    path = f"/api/v1/items/{item['id']}/checklist/0"
    with factory() as db:
        db.add(ProjectMember(project_id=project["id"], user_id=people["member"], role="reader"))
        db.commit()
    assert member.patch(path, json=payload).status_code == 403
    admin.headers.pop("X-CSRF-Token")
    assert admin.patch(path, json=payload).status_code == 403


def test_stale_version_conflicts_and_noop_does_not_create_events(env):
    _, client, _ = env
    admin, member = client("administrator"), client("member")
    _, item = setup_ticket(admin)
    path = f"/api/v1/items/{item['id']}/checklist/0"
    payload = {"checked": True, "version": item["description_version"]}
    first = admin.patch(path, json=payload).json()
    assert member.patch(path, json=payload).status_code == 409
    assert member.patch(path, json={"checked": True, "version": first["version"]}).json()["changed"] is False
    entries = admin.get(f"/api/v1/items/{item['id']}/discussion").json()
    assert len([entry for entry in entries if "checklist item" in entry["body"]]) == 1
    assert member.patch(f"/api/v1/items/{item['id']}/checklist/5", json={"checked": True, "version": first["version"]}).status_code == 404


def test_comment_version_and_item_binding_are_checked(env):
    _, client, _ = env
    admin = client("administrator")
    project, item = setup_ticket(admin)
    other = admin.post(f"/api/v1/projects/{project['id']}/items", json={"title": "Other item"}).json()
    cid = admin.post(f"/api/v1/items/{item['id']}/comments", json={"body": "- [ ] Comment task"}).json()["id"]
    version = content_version("- [ ] Comment task")
    assert admin.patch(f"/api/v1/items/{other['id']}/comments/{cid}/checklist/0", json={"checked": True, "version": version}).status_code == 404
    path = f"/api/v1/items/{item['id']}/comments/{cid}/checklist/0"
    assert admin.patch(path, json={"checked": True, "version": version}).status_code == 200
    assert admin.patch(path, json={"checked": False, "version": version}).status_code == 409


@pytest.mark.parametrize("payload", [{"checked": "true", "version": "a" * 64}, {"checked": True},
                                     {"checked": True, "version": "invalid"},
                                     {"checked": True, "version": "a" * 64, "description": "Replace everything"}])
def test_checklist_request_validation(env, payload):
    _, client, _ = env
    admin = client("administrator")
    _, item = setup_ticket(admin)
    assert admin.patch(f"/api/v1/items/{item['id']}/checklist/0", json=payload).status_code == 422

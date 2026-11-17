from test_access import project


def define(client, path, name="bug", color="#dc2626", description="Unexpected behavior"):
    response = client.post(path, json={"name": name, "color": color, "description": description})
    assert response.status_code == 201, response.text
    return response.json()


def test_inheritance_scope_and_explicit_assignment(env):
    _, client, _ = env
    admin, member = client("administrator"), client("member")
    org = define(admin, "/api/v1/organization/labels")
    pid, other = project(admin), project(admin, key="OTHER")
    path = f"/api/v1/projects/{pid}/labels"
    local = define(admin, path, "frontend")
    assert admin.get(path).json() == [org, local]
    assert admin.get(f"/api/v1/projects/{other}/labels").json() == [org]
    assert admin.get("/api/v1/organization/labels").json() == [org]
    item_path = f"/api/v1/projects/{pid}/items"
    response = member.post(item_path, json={"title": "Both scopes", "labels": ["bug", "frontend"]})
    assert response.status_code == 201
    ticket = f'/api/v1/items/{response.json()["id"]}'
    assert member.patch(ticket, json={"labels": ["unknown"]}).status_code == 422
    assert member.put(ticket, json={"title": "Invalid", "labels": ["unknown"]}).status_code == 422
    assert member.get(ticket).json()["labels"] == ["bug", "frontend"]
    assert member.post(f"/api/v1/projects/{other}/items", json={"title": "Invalid scope", "labels": ["frontend"]}).status_code == 422
    assert member.post(item_path, json={"title": "Undefined", "labels": ["unknown"]}).status_code == 422
    assert member.patch(ticket, json={"labels": []}).json()["labels"] == []


def test_conflicts_rename_and_used_deletion(env):
    _, client, _ = env
    admin = client("administrator")
    pid, other = project(admin), project(admin, key="OTHER")
    org_path, path = "/api/v1/organization/labels", f"/api/v1/projects/{pid}/labels"
    org = define(admin, org_path)
    local = define(admin, path, "frontend")
    # A local name can be reused in an independent project, but not inherited scopes.
    define(admin, f"/api/v1/projects/{other}/labels", "frontend")
    for base, name in [(org_path, "bug"), (path, "bug"), (path, "frontend"), (org_path, "frontend")]:
        assert admin.post(base, json={"name": name, "color": "#123456"}).status_code == 409
    tickets = []
    for project_id in [pid, other]:
        ticket = admin.post(f"/api/v1/projects/{project_id}/items", json={"title": "Assigned", "labels": ["bug", "frontend"]}).json()
        tickets.append(f'/api/v1/items/{ticket["id"]}')
    assert admin.delete(f'{org_path}/{org["id"]}').status_code == 409
    assert admin.put(f'{org_path}/{org["id"]}', json={"name": "defect", "color": "#123456", "description": "Updated"}).status_code == 200
    assert [admin.get(ticket).json()["labels"] for ticket in tickets] == [["defect", "frontend"]] * 2
    assert admin.put(f'{path}/{local["id"]}', json={"name": "ui", "color": "#abcdef"}).status_code == 200
    assert admin.get(tickets[0]).json()["labels"] == ["defect", "ui"]
    assert admin.get(tickets[1]).json()["labels"] == ["defect", "frontend"]
    assert admin.delete(f'{path}/{org["id"]}').status_code == 404
    assert admin.delete(f'{path}/{local["id"]}').status_code == 409
    assert admin.patch(tickets[0], json={"labels": []}).status_code == 200
    assert admin.delete(f'{path}/{local["id"]}').status_code == 200


def test_catalog_permissions_private_isolation_validation_and_csrf(env):
    _, client, _ = env
    admin = client("administrator")
    pid = project(admin, "private")
    private_path = f"/api/v1/projects/{pid}/labels"
    label = define(admin, private_path, "private-label")
    path = "/api/v1/organization/labels"
    org = define(admin, path)
    for role in ["member", "reader"]:
        c = client(role)
        assert c.get(private_path).status_code == 404
        assert c.get(path).status_code == 403
        assert c.post(path, json={"name": "No", "color": "#123456"}).status_code == 403
        assert c.put(f'{path}/{org["id"]}', json={"name": "No", "color": "#123456"}).status_code == 403
        assert c.delete(f'{path}/{org["id"]}').status_code == 403
        assert c.post(private_path, json={"name": "No", "color": "#123456"}).status_code == 404
    public_path = f'/api/v1/projects/{project(admin, key="PUBLIC")}/labels'
    assert client("member").post(public_path, json={"name": "No", "color": "#123456"}).status_code == 403
    assert client("outsider").get(path).status_code == 403
    assert client().get(path).status_code == 401
    assert admin.get(path).json() == [org] and label not in admin.get(public_path).json()
    for payload in [{"name": " ", "color": "#123456"}, {"name": "x" * 51, "color": "#123456"},
                    {"name": "bad", "color": "red"}, {"name": "bad", "color": "#123456", "description": "x" * 2001}]:
        assert admin.post(path, json=payload).status_code == 422
    admin.headers.pop("X-CSRF-Token")
    assert admin.delete(f'{path}/{org["id"]}').status_code == 403

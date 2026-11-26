import io

from PIL import Image

from app.models import User
from test_api_tokens import bearer, issue


def picture(color="green"):
    output = io.BytesIO()
    Image.new("RGB", (400, 200), color).save(output, format="PNG")
    return {"file": ("logo.png", output.getvalue(), "image/png")}


def project_with_members(client, people):
    admin = client("administrator")
    project = admin.post("/api/v1/projects", json={"key": "LG", "name": "Logo project"}).json()
    for role, access in (("member", "owner"), ("reader", "read-only")):
        assert admin.put(f'/api/v1/projects/{project["id"]}/members', json={
            "user_id": people[role], "role": access}).status_code == 200
    return project


def test_project_logo_lifecycle_and_preserved_proportions(env):
    _, client, people = env
    project = project_with_members(client, people)
    owner, reader = client("member"), client("reader")
    path = f'/api/v1/projects/{project["id"]}/logo'
    assert project["logo_url"] is None
    assert reader.get(path).status_code == 404
    uploaded = owner.put(path, files=picture())
    assert uploaded.status_code == 200
    url = uploaded.json()["logo_url"]
    response = reader.get(url)
    assert response.status_code == 200
    assert "no-store" in response.headers["Cache-Control"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    with Image.open(io.BytesIO(response.content)) as image:
        assert image.size == (256, 256) and image.format == "PNG"
        assert image.getbbox() == (0, 64, 256, 192), "Rectangular logos must be padded, not cropped or stretched"
    assert reader.get("/api/v1/projects").json()[0]["logo_url"] == url
    replacement = owner.put(path, files=picture("blue")).json()["logo_url"]
    assert replacement != url
    assert owner.delete(path).json()["logo_url"] is None
    assert reader.get(replacement).status_code == 404


def test_project_logo_permissions_csrf_and_current_access(env):
    factory, client, people = env
    project = project_with_members(client, people)
    admin, owner, reader = client("administrator"), client("member"), client("reader")
    path = f'/api/v1/projects/{project["id"]}/logo'
    assert admin.put(path, files=picture()).status_code == 200
    assert client().get(path).status_code == 401
    with factory() as db:
        db.get(User, people["outsider"]).role = "member"
        db.commit()
    assert client("outsider").get(path).status_code == 404
    assert reader.put(path, files=picture()).status_code == 403
    assert reader.delete(path).status_code == 403
    assert reader.get(path).status_code == 200
    owner.headers.pop("X-CSRF-Token")
    assert owner.put(path, files=picture()).status_code == 403
    assert owner.delete(path).status_code == 403
    # Reporter token permissions cannot bypass the project Owner requirement.
    admin.put(f'/api/v1/projects/{project["id"]}/members', json={"user_id": people["member"], "role": "reporter"})
    token = bearer(issue(client("member"), ["read", "write"])["token"])
    assert token.get(path).status_code == 200
    assert token.put(path, files=picture()).status_code == 403
    assert token.delete(path).status_code == 403
    admin.delete(f'/api/v1/projects/{project["id"]}/members/{people["reader"]}')
    assert reader.get(path).status_code == 404


def test_invalid_project_logo_preserves_previous_picture(env):
    _, client, people = env
    project = project_with_members(client, people)
    owner = client("member")
    path = f'/api/v1/projects/{project["id"]}/logo'
    url = owner.put(path, files=picture()).json()["logo_url"]
    assert owner.put(path, files={"file": ("bad.png", b"not an image")}).status_code == 422
    assert owner.put(path, files={"file": ("large.png", b"x" * (5 * 1024 * 1024 + 1))}).status_code == 413
    assert owner.put(path, files={"file": ("logo.svg", b'<svg xmlns="http://www.w3.org/2000/svg"/>')}).status_code == 422
    assert owner.get("/api/v1/projects").json()[0]["logo_url"] == url

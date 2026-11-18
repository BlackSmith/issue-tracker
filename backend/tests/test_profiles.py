import io

import pytest
from PIL import Image
from sqlalchemy import select

from app.main import app
from app.models import ExternalIdentity, User
from app.providers import ExternalProfile


def profile(**values):
    return {"name": "Updated Member", "email": "updated@example.test", "theme_accent": "blue",
            "theme_background": "sand", **values}


def png(color="green"):
    output = io.BytesIO()
    Image.new("RGB", (400, 200), color).save(output, format="PNG")
    return output.getvalue()


def test_profile_defaults_and_own_only_updates(env):
    factory, client, people = env
    member = client("member")
    current = member.get("/api/v1/users/me").json()
    assert current["theme_accent"] == "green" and current["theme_background"] == "white"
    assert current["avatar_url"] is None
    assert current["language"] == "en"
    response = member.put("/api/v1/users/me", json=profile(name="  Updated Member  "))
    assert response.status_code == 200
    result = response.json()
    assert result["name"] == "Updated Member" and result["email"] == "updated@example.test"
    assert result["theme_accent"] == "blue" and result["theme_background"] == "sand"
    assert result["role"] == "member" and result["id"] == people["member"]
    assert member.get("/api/v1/auth/me").json()["user"] == result
    with factory() as db:
        assert db.get(User, people["reader"]).name == "reader"
        assert db.get(User, people["reader"]).theme_accent == "green"


@pytest.mark.parametrize("role", ["reader", "outsider"])
def test_all_authenticated_users_can_manage_own_profile(env, role):
    _, client, _ = env
    user = client(role)
    assert user.put("/api/v1/users/me", json=profile()).status_code == 200
    response = user.put("/api/v1/users/me/avatar", files={"file": ("picture.png", png())})
    assert response.status_code == 200
    assert user.get(response.json()["avatar_url"]).status_code == 200
    assert user.delete("/api/v1/users/me/avatar").status_code == 200


@pytest.mark.parametrize("values", [
    {"name": "   "}, {"email": "invalid-address"}, {"email": "a@b\r\ninvalid"},
    {"theme_accent": "#ffffff"}, {"theme_background": "url(https://example.com)"},
    {"role": "administrator"}, {"id": "another-user"}, {"active": False},
    {"language": "de"},
])
def test_profile_validation_prevents_privilege_changes(env, values):
    _, client, _ = env
    member = client("member")
    before = member.get("/api/v1/users/me").json()
    assert member.put("/api/v1/users/me", json=profile(**values)).status_code == 422
    assert member.get("/api/v1/users/me").json() == before


def test_profile_authentication_and_csrf(env):
    _, client, _ = env
    anonymous = client()
    assert anonymous.get("/api/v1/users/me").status_code == 401
    csrf_token = anonymous.get("/api/v1/auth/me").json()["csrf_token"]
    anonymous.headers["X-CSRF-Token"] = csrf_token
    assert anonymous.put("/api/v1/users/me", json=profile()).status_code == 401
    member = client("member")
    member.headers.pop("X-CSRF-Token")
    assert member.put("/api/v1/users/me", json=profile()).status_code == 403
    assert member.put("/api/v1/users/me/avatar", files={"file": ("picture.png", png())}).status_code == 403
    assert member.delete("/api/v1/users/me/avatar").status_code == 403


def test_language_is_account_scoped_and_preserved_for_legacy_profile_updates(env):
    _, client, _ = env
    member, reader = client("member"), client("reader")
    assert member.put("/api/v1/users/me", json=profile(language="cs")).json()["language"] == "cs"
    assert member.get("/api/v1/auth/me").json()["user"]["language"] == "cs"
    assert reader.get("/api/v1/users/me").json()["language"] == "en"
    assert member.put("/api/v1/users/me", json=profile()).json()["language"] == "cs"
    assert member.put("/api/v1/users/me", json=profile(language="en")).json()["language"] == "en"


def test_avatar_normalization_replacement_and_removal(env):
    _, client, _ = env
    member, reader, outsider = client("member"), client("reader"), client("outsider")
    response = member.put("/api/v1/users/me/avatar", files={"file": ("../photo.png", png(), "text/plain")})
    assert response.status_code == 200
    old_url = response.json()["avatar_url"]
    image_response = member.get(old_url)
    assert image_response.status_code == 200
    assert image_response.headers["content-type"] == "image/png"
    assert image_response.headers["x-content-type-options"] == "nosniff"
    with Image.open(io.BytesIO(image_response.content)) as image:
        assert image.size == (256, 256) and image.format == "PNG"
    assert reader.get(old_url).status_code == 200
    assert outsider.get(old_url).status_code == 404
    assert client().get(old_url).status_code == 401
    response = member.put("/api/v1/users/me/avatar", files={"file": ("blue.png", png("blue"))})
    assert response.status_code == 200 and response.json()["avatar_url"] != old_url
    assert reader.get("/api/v1/users/me").json()["avatar_url"] is None
    assert member.delete("/api/v1/users/me/avatar").json()["avatar_url"] is None
    assert member.get(old_url).status_code == 404


def test_avatar_invalid_files_leave_previous_image_unchanged(env):
    _, client, _ = env
    member = client("member")
    original = member.put("/api/v1/users/me/avatar", files={"file": ("photo.png", png())}).json()["avatar_url"]
    for filename, data in [("picture.png", b"not an image"), ("x.svg", b'<svg xmlns="http://www.w3.org/2000/svg"/>')]:
        assert member.put("/api/v1/users/me/avatar", files={"file": (filename, data, "image/png")}).status_code == 422
    assert member.put("/api/v1/users/me/avatar", files={"file": ("big.png", b"x" * (5 * 1024 * 1024 + 1))}).status_code == 413
    assert member.get("/api/v1/users/me").json()["avatar_url"] == original


def test_contact_profile_survives_oidc_signin_with_same_external_identity(env):
    factory, client, people = env
    member = client("member")
    with factory() as db:
        db.add(ExternalIdentity(user_id=people["member"], issuer="https://identity.example", subject="original-subject"))
        db.commit()
    assert member.put("/api/v1/users/me", json=profile(language="cs")).status_code == 200

    class Provider:
        async def identity(self, request):
            return ExternalProfile("https://identity.example", "original-subject", "Provider Name", "provider@example.test")

    with member:
        app.state.provider = Provider()
        assert member.get("/api/v1/auth/oidc/callback", follow_redirects=False).status_code == 303
        result = member.get("/api/v1/users/me").json()
        assert result["id"] == people["member"]
        assert result["name"] == "Updated Member" and result["email"] == "updated@example.test"
        assert result["theme_accent"] == "blue" and result["theme_background"] == "sand"
        assert result["language"] == "cs"
    with factory() as db:
        identity = db.scalar(select(ExternalIdentity).where(ExternalIdentity.user_id == people["member"]))
        assert identity.issuer == "https://identity.example" and identity.subject == "original-subject"

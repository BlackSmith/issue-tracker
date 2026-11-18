import hashlib
import io
import warnings

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import ProfileUpdate
from app.security import csrf, current_user

router = APIRouter(prefix="/api/v1/users", tags=["Personal settings"])
MAX_AVATAR_BYTES = 5 * 1024 * 1024
MAX_AVATAR_PIXELS = 16_000_000


def avatar_url(user: User) -> str | None:
    if not user.avatar:
        return None
    version = hashlib.sha256(user.avatar).hexdigest()[:16]
    return f"/api/v1/users/{user.id}/avatar?v={version}"


def profile_json(user: User):
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "is_bot": user.is_bot,
            "avatar_url": avatar_url(user), "theme_accent": user.theme_accent,
            "theme_background": user.theme_background, "language": user.language}


@router.get("/me")
def get_profile(user: User = Depends(current_user)):
    return profile_json(user)


@router.put("/me", dependencies=[Depends(csrf)])
def update_profile(payload: ProfileUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    for field, value in payload.model_dump().items():
        if field == "language" and value is None:
            continue
        setattr(user, field, value)
    db.commit()
    return profile_json(user)


async def read_avatar(file: UploadFile) -> bytes:
    try:
        data = await file.read(MAX_AVATAR_BYTES + 1)
    finally:
        await file.close()
    if len(data) > MAX_AVATAR_BYTES:
        raise HTTPException(413, "Profile pictures must be smaller than 5 MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.format not in {"PNG", "JPEG", "GIF", "WEBP"}:
                    raise HTTPException(422, "Choose a PNG, JPEG, GIF, or WebP picture")
                if source.width * source.height > MAX_AVATAR_PIXELS:
                    raise HTTPException(422, "Profile pictures must not exceed 16 megapixels")
                image = ImageOps.fit(ImageOps.exif_transpose(source).convert("RGBA"), (256, 256))
                # Re-encode decoded pixels: discard animation, metadata and any
                # extra file payload rather than serving the original upload.
                image.info.clear()
                output = io.BytesIO()
                image.save(output, format="PNG")
                return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, "Choose a valid PNG, JPEG, GIF, or WebP picture")


@router.put("/me/avatar", dependencies=[Depends(csrf)])
async def upload_avatar(file: UploadFile = File(), user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.avatar = await read_avatar(file)
    db.commit()
    return profile_json(user)


@router.delete("/me/avatar", dependencies=[Depends(csrf)])
def delete_avatar(user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.avatar = None
    db.commit()
    return profile_json(user)


@router.get("/{user_id}/avatar")
def get_avatar(user_id: str, viewer: User = Depends(current_user), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if (not user or (not user.active and not user.is_bot) or not user.avatar
            or (viewer.id != user.id and (not viewer.role or not user.role))):
        raise HTTPException(404, "Profile picture not found")
    return Response(user.avatar, media_type="image/png",
                    headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})

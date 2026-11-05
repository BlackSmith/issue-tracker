from fastapi import HTTPException
from sqlalchemy import or_, select

from app.models import Label, Project


def lock_catalog(db):
    # All catalog mutations and label assignments take the same ordered locks.
    # This also serializes organization/project name conflict checks and renames.
    list(db.scalars(select(Project).order_by(Project.id).with_for_update()))


def available_labels(db, project_id):
    return db.scalars(select(Label).where(or_(Label.project_id.is_(None), Label.project_id == project_id))
                      .order_by(Label.name, Label.id)).all()


def validate_labels(db, project_id, names):
    allowed = {label.name for label in available_labels(db, project_id)}
    if any(name not in allowed for name in names):
        raise HTTPException(422, "Choose existing organization or project labels")


def label_json(label):
    return {field: getattr(label, field) for field in ("id", "project_id", "name", "color", "description")}

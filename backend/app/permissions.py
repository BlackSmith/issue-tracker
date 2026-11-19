"""Shared ticket visibility rules for API reads and notifications."""
from sqlalchemy import exists, or_

from app.models import Project, ProjectMember, WorkItem


def visible_item(user):
    if user.role == "administrator" and not user.is_bot:
        return True
    return or_(
        Project.restrict_ticket_visibility.is_(False),
        WorkItem.is_project_public.is_(True),
        exists().where(ProjectMember.project_id == Project.id,
                       ProjectMember.user_id == user.id, ProjectMember.role == "owner").correlate(Project),
        WorkItem.author_id == user.id,
        WorkItem.assignee_id == user.id,
    )


def can_view_item(db, item, user):
    project = db.get(Project, item.project_id)
    if not project.restrict_ticket_visibility or (user.role == "administrator" and not user.is_bot):
        return True
    member = db.get(ProjectMember, (project.id, user.id))
    return bool(member and (item.is_project_public or member.role == "owner" or user.id in {item.author_id, item.assignee_id}))

"""Shared ticket visibility rules for API reads and notifications."""
from sqlalchemy import and_, exists, or_

from app.models import Project, ProjectMember, User, WorkItem


def effective_project_role(project, user, member):
    if not user.active or user.role not in {"administrator", "member"}:
        return None
    if user.role == "administrator" and not user.is_bot:
        return "owner"
    if member:
        return member.role
    return project.default_access if not user.is_bot else None


def visible_project(user):
    if not user.active or user.role not in {"administrator", "member"}:
        return False
    if user.role == "administrator" and not user.is_bot:
        return True
    membership = exists().where(ProjectMember.project_id == Project.id, ProjectMember.user_id == user.id)
    return membership if user.is_bot else or_(membership, Project.default_access.is_not(None))


def project_user_access(project_id):
    """SQL predicate for candidate users, including inherited human access."""
    return or_(
        and_(User.role == "administrator", User.is_bot.is_(False)),
        exists().where(ProjectMember.project_id == project_id, ProjectMember.user_id == User.id),
        and_(User.role == "member", User.is_bot.is_(False), exists().where(
            Project.id == project_id, Project.default_access.is_not(None))),
    )


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
    role = effective_project_role(project, user, member)
    return bool(role and (item.is_project_public or role == "owner" or user.id in {item.author_id, item.assignee_id}))

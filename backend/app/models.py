import time
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, JSON, LargeBinary, String, Text, UniqueConstraint, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320))
    role: Mapped[str | None] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(default=True)
    is_bot: Mapped[bool] = mapped_column(default=False, server_default=false())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auth_version: Mapped[int] = mapped_column(default=0, server_default="0")
    avatar: Mapped[bytes | None] = mapped_column(LargeBinary)
    theme_accent: Mapped[str] = mapped_column(String(20), default="green", server_default="green")
    theme_background: Mapped[str] = mapped_column(String(20), default="white", server_default="white")
    language: Mapped[str] = mapped_column(String(2), default="en", server_default="en")


class ExternalIdentity(Base):
    __tablename__ = "external_identities"
    __table_args__ = (UniqueConstraint("issuer", "subject"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    issuer: Mapped[str] = mapped_column(String(500))
    subject: Mapped[str] = mapped_column(String(255))


class BrowserSession(Base):
    __tablename__ = "browser_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    expires_at: Mapped[int] = mapped_column(index=True, default=lambda: int(time.time()) + 43200)


class PasswordCredential(Base):
    __tablename__ = "password_credentials"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    login_email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str | None] = mapped_column(Text)


class PasswordLink(Base):
    __tablename__ = "password_links"
    secret_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=time.time_ns, server_default="0")
    expires_at: Mapped[int] = mapped_column(BigInteger)
    used: Mapped[bool] = mapped_column(default=False)
    recipient: Mapped[str] = mapped_column(String(320))
    encrypted_body: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(default=0)
    next_attempt_at: Mapped[int] = mapped_column(BigInteger)
    delivery_status: Mapped[str] = mapped_column(String(20), default="queued")


class LoginThrottle(Base):
    __tablename__ = "login_throttles"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(default=0)
    expires_at: Mapped[int] = mapped_column(BigInteger)


class TicketNotification(Base):
    __tablename__ = "ticket_notifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    item_id: Mapped[str] = mapped_column(ForeignKey("work_items.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    encrypted_body: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(default=0)
    next_attempt_at: Mapped[int] = mapped_column(BigInteger, index=True)
    delivery_status: Mapped[str] = mapped_column(String(20), default="queued", index=True)


class ProjectNotificationPreference(Base):
    __tablename__ = "project_notification_preferences"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=True)


class TicketNotificationPreference(Base):
    __tablename__ = "ticket_notification_preferences"
    item_id: Mapped[str] = mapped_column(ForeignKey("work_items.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    enabled: Mapped[bool] = mapped_column()


class ApiToken(Base):
    __tablename__ = "api_tokens"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(100))
    token_prefix: Mapped[str] = mapped_column(String(12))
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True)
    scopes: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[int] = mapped_column(BigInteger, default=lambda: int(time.time()))
    expires_at: Mapped[int] = mapped_column(BigInteger)
    revoked_at: Mapped[int | None] = mapped_column(BigInteger)
    last_used_at: Mapped[int | None] = mapped_column(BigInteger)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(10), unique=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    logo: Mapped[bytes | None] = mapped_column(LargeBinary)
    description: Mapped[str] = mapped_column(Text, default="")
    visibility: Mapped[str] = mapped_column(String(20), default="private")
    default_access: Mapped[str | None] = mapped_column(String(20))
    restrict_ticket_visibility: Mapped[bool] = mapped_column(default=False, server_default=false())
    next_number: Mapped[int] = mapped_column(default=0)


class ProjectMember(Base):
    __tablename__ = "project_members"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20))


class Label(Base):
    __tablename__ = "labels"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(50))
    color: Mapped[str] = mapped_column(String(7), default="#16a34a")
    description: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (Index("uq_labels_scope_name", func.coalesce(project_id, ""), name, unique=True),)


class Milestone(Base):
    __tablename__ = "milestones"
    __table_args__ = (
        UniqueConstraint("project_id", "id", name="uq_milestones_project_id_id"),
        UniqueConstraint("project_id", "name", name="uq_milestones_project_name"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    due_date: Mapped[date | None] = mapped_column(Date)
    closed: Mapped[bool] = mapped_column(default=False, server_default=false())


class WorkItem(Base):
    __tablename__ = "work_items"
    __table_args__ = (
        UniqueConstraint("project_id", "number"),
        ForeignKeyConstraint(["project_id", "milestone_id"], ["milestones.project_id", "milestones.id"],
                             name="fk_work_items_project_milestone"),
        Index("ix_work_items_project_milestone", "project_id", "milestone_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[int]
    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(Text, default="")
    type: Mapped[str] = mapped_column(String(20), default="Task")
    status: Mapped[str] = mapped_column(String(20), default="Open")
    priority: Mapped[str] = mapped_column(String(20), default="Medium")
    labels: Mapped[list[str]] = mapped_column(JSON, default=list)
    due_date: Mapped[date | None] = mapped_column(Date)
    milestone_id: Mapped[str | None] = mapped_column(String(36))
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id], lazy="selectin")
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    author: Mapped[User] = relationship(foreign_keys=[author_id])
    is_project_public: Mapped[bool] = mapped_column(default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    item_id: Mapped[str] = mapped_column(ForeignKey("work_items.id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Activity(Base):
    __tablename__ = "activities"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    item_id: Mapped[str] = mapped_column(ForeignKey("work_items.id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Attachment(Base):
    __tablename__ = "attachments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    item_id: Mapped[str | None] = mapped_column(ForeignKey("work_items.id"), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), index=True)
    pending: Mapped[bool] = mapped_column(default=False, server_default=false(), index=True)
    filename: Mapped[str] = mapped_column(String(250))
    size: Mapped[int]
    uploader_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

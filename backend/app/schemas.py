from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator
from email_validator import EmailNotValidError, validate_email
from app.project_slugs import RESERVED_PROJECT_SLUGS

Role = Literal["administrator", "member"]
ProjectRole = Literal["owner", "reporter", "read-only"]
Status = Literal["Open", "In progress", "Done", "Canceled"]
Priority = Literal["Low", "Medium", "High", "Urgent"]
ItemType = Literal["Task", "Bug", "Feature"]
ThemeAccent = Literal["green", "blue", "purple", "teal", "amber", "rose"]
ThemeBackground = Literal["white", "mist", "mint", "sand", "slate"]


class ChecklistUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    checked: StrictBool
    version: str = Field(pattern=r"^[a-f0-9]{64}$")


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=1, max_length=320)
    theme_accent: ThemeAccent = "green"
    theme_background: ThemeBackground = "white"
    language: Literal["en", "cs"] | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Name cannot be blank")
        return value.strip()

    @field_validator("email")
    @classmethod
    def valid_contact_email(cls, value):
        try:
            # Contact data may include development .test addresses. It is never
            # used as an authentication identifier or membership claim.
            return validate_email(value.strip(), check_deliverability=False, test_environment=True).normalized
        except EmailNotValidError:
            raise ValueError("Enter a valid email address")


class ProjectCreate(BaseModel):
    key: str = Field(pattern=r"^[A-Z][A-Z0-9]{1,9}$")
    name: str = Field(min_length=1, max_length=150)
    slug: str | None = Field(default=None, description="Deprecated: the URL is derived from key. If supplied, must equal key.")
    description: str = Field(default="", max_length=10000)
    visibility: Literal["organization", "private"] = "private"
    restrict_ticket_visibility: StrictBool = False
    default_access: Literal["reporter", "read-only"] | None = None

    @field_validator("key")
    @classmethod
    def key_not_reserved(cls, value):
        if value.lower() in RESERVED_PROJECT_SLUGS:
            raise ValueError("This project key is reserved for an application URL")
        return value

    @model_validator(mode="after")
    def url_matches_key(self):
        if self.slug is not None and self.slug != self.key:
            raise ValueError("Project URL must match the project key; omit slug or set it to key")
        return self


class ProjectUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(min_length=1, max_length=150)
    description: str = Field(max_length=10000)
    visibility: Literal["organization", "private"]
    restrict_ticket_visibility: StrictBool = False
    default_access: Literal["reporter", "read-only"] | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Project name cannot be blank")
        return value.strip()


class MemberCreate(BaseModel):
    user_id: str
    role: ProjectRole


class ApplicationUserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Role
    active: StrictBool


class LabelCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=50)
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    description: str = Field(default="", max_length=2000)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Label name cannot be blank")
        return value.strip()


class ItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    description: str = Field(default="", max_length=100000)
    type: ItemType = "Task"
    status: Status = "Open"
    priority: Priority = "Medium"
    labels: list[str] = Field(default_factory=list, max_length=20)
    due_date: date | None = None
    assignee_id: str | None = Field(default=None, min_length=1, max_length=36)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Title cannot be blank")
        return value.strip()

    @field_validator("labels")
    @classmethod
    def clean_labels(cls, values):
        if any(not value.strip() or len(value) > 50 for value in values):
            raise ValueError("Labels must contain 1 to 50 characters")
        return list(dict.fromkeys(value.strip() for value in values))


class ItemUpdate(ItemCreate):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=250)
    description: str | None = Field(default=None, max_length=100000)
    type: ItemType | None = None
    status: Status | None = None
    priority: Priority | None = None
    labels: list[str] | None = Field(default=None, max_length=20)

    @model_validator(mode="before")
    @classmethod
    def nonnullable_fields(cls, values):
        if isinstance(values, dict) and any(value is None and key not in {"due_date", "assignee_id"} for key, value in values.items()):
            raise ValueError("Only due_date and assignee_id can be null")
        return values


class TicketPublication(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_project_public: StrictBool


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=100000)

    @field_validator("body")
    @classmethod
    def body_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Comment cannot be blank")
        return value

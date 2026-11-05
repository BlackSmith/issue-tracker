"""Initial users, sessions, projects, work items and attachments.

Revision ID: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("users", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("name", sa.String(200), nullable=False), sa.Column("email", sa.String(320), nullable=False),
                    sa.Column("role", sa.String(20)), sa.Column("active", sa.Boolean(), nullable=False))
    op.create_table("external_identities", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
                    sa.Column("issuer", sa.String(500), nullable=False), sa.Column("subject", sa.String(255), nullable=False),
                    sa.UniqueConstraint("issuer", "subject"))
    op.create_index("ix_external_identities_user_id", "external_identities", ["user_id"])
    op.create_table("browser_sessions", sa.Column("token_hash", sa.String(64), primary_key=True),
                    sa.Column("data", sa.JSON(), nullable=False), sa.Column("expires_at", sa.Integer(), nullable=False))
    op.create_index("ix_browser_sessions_expires_at", "browser_sessions", ["expires_at"])
    op.create_table("projects", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("key", sa.String(10), nullable=False, unique=True), sa.Column("name", sa.String(150), nullable=False),
                    sa.Column("description", sa.Text(), nullable=False), sa.Column("visibility", sa.String(20), nullable=False),
                    sa.Column("next_number", sa.Integer(), nullable=False))
    op.create_table("project_members", sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), primary_key=True),
                    sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True), sa.Column("role", sa.String(20), nullable=False))
    op.create_table("work_items", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
                    sa.Column("number", sa.Integer(), nullable=False), sa.Column("title", sa.String(250), nullable=False),
                    sa.Column("description", sa.Text(), nullable=False), sa.Column("type", sa.String(20), nullable=False),
                    sa.Column("status", sa.String(20), nullable=False), sa.Column("priority", sa.String(20), nullable=False),
                    sa.Column("labels", sa.JSON(), nullable=False), sa.Column("due_date", sa.Date()),
                    sa.Column("author_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("project_id", "number"))
    op.create_index("ix_work_items_project_id", "work_items", ["project_id"])
    for table, text_column in [("comments", "body"), ("activities", "message")]:
        op.create_table(table, sa.Column("id", sa.String(36), primary_key=True),
                        sa.Column("item_id", sa.String(36), sa.ForeignKey("work_items.id"), nullable=False),
                        sa.Column("author_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
                        sa.Column(text_column, sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
        op.create_index(f"ix_{table}_item_id", table, ["item_id"])
    op.create_table("attachments", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("item_id", sa.String(36), sa.ForeignKey("work_items.id"), nullable=False),
                    sa.Column("filename", sa.String(250), nullable=False), sa.Column("size", sa.Integer(), nullable=False),
                    sa.Column("uploader_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_attachments_item_id", "attachments", ["item_id"])


def downgrade():
    for table in ["attachments", "activities", "comments", "work_items", "project_members", "projects", "browser_sessions", "external_identities", "users"]:
        op.drop_table(table)

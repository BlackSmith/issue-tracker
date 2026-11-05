"""Support project-scoped temporary editor uploads.

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("attachments", "item_id", existing_type=sa.String(36), nullable=True)
    op.add_column("attachments", sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=True))
    op.add_column("attachments", sa.Column("pending", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("ix_attachments_project_id", "attachments", ["project_id"])
    op.create_index("ix_attachments_pending", "attachments", ["pending"])


def downgrade():
    op.execute("DELETE FROM attachments WHERE item_id IS NULL")
    op.drop_index("ix_attachments_pending", table_name="attachments")
    op.drop_index("ix_attachments_project_id", table_name="attachments")
    op.drop_column("attachments", "pending")
    op.drop_column("attachments", "project_id")
    op.alter_column("attachments", "item_id", existing_type=sa.String(36), nullable=False)

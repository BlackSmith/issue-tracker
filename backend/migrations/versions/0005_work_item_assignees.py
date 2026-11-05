"""Persist work item assignees.

Revision ID: 0005
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("work_items", sa.Column("assignee_id", sa.String(36), nullable=True))
    op.create_foreign_key("fk_work_items_assignee_id", "work_items", "users", ["assignee_id"], ["id"])
    op.create_index("ix_work_items_assignee_id", "work_items", ["assignee_id"])


def downgrade():
    op.drop_index("ix_work_items_assignee_id", table_name="work_items")
    op.drop_constraint("fk_work_items_assignee_id", "work_items", type_="foreignkey")
    op.drop_column("work_items", "assignee_id")

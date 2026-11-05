"""Define organization and project labels, preserving existing assignments.

Revision ID: 0007
Revises: 0006
"""
import uuid

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    labels = op.create_table(
        "labels",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("color", sa.String(7), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
    )
    op.create_index("ix_labels_project_id", "labels", ["project_id"])
    op.create_index("uq_labels_scope_name", "labels", [sa.text("coalesce(project_id, '')"), "name"], unique=True)
    connection = op.get_bind()
    items = sa.table("work_items", sa.column("project_id"), sa.column("labels", sa.JSON()))
    existing = set()
    for project_id, names in connection.execute(sa.select(items.c.project_id, items.c.labels)):
        for name in names:
            existing.add((project_id, name))
    for project_id, name in sorted(existing):
        connection.execute(labels.insert().values(id=str(uuid.uuid4()), project_id=project_id,
                                                  name=name, color="#16a34a", description=""))


def downgrade():
    op.drop_index("uq_labels_scope_name", table_name="labels")
    op.drop_index("ix_labels_project_id", table_name="labels")
    op.drop_table("labels")

"""Add project milestones and optional work item assignments."""
from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "milestones",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("closed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.UniqueConstraint("project_id", "id", name="uq_milestones_project_id_id"),
        sa.UniqueConstraint("project_id", "name", name="uq_milestones_project_name"),
    )
    op.add_column("work_items", sa.Column("milestone_id", sa.String(36)))
    op.create_foreign_key("fk_work_items_project_milestone", "work_items", "milestones",
                          ["project_id", "milestone_id"], ["project_id", "id"])
    op.create_index("ix_work_items_project_milestone", "work_items", ["project_id", "milestone_id"])


def downgrade():
    op.drop_index("ix_work_items_project_milestone", table_name="work_items")
    op.drop_constraint("fk_work_items_project_milestone", "work_items", type_="foreignkey")
    op.drop_column("work_items", "milestone_id")
    op.drop_table("milestones")

"""Personal project notification preferences and explicit ticket subscriptions."""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    for table, target, column in (
        ("project_notification_preferences", "projects", "project_id"),
        ("ticket_notification_preferences", "work_items", "item_id"),
    ):
        op.create_table(table,
                        sa.Column(column, sa.String(36), sa.ForeignKey(f"{target}.id"), primary_key=True),
                        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
                        sa.Column("enabled", sa.Boolean(), nullable=False))


def downgrade():
    op.drop_table("ticket_notification_preferences")
    op.drop_table("project_notification_preferences")

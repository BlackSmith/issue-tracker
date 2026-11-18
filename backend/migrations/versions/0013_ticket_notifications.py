"""Add the encrypted ticket notification outbox."""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("ticket_notifications",
                    sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("item_id", sa.String(36), sa.ForeignKey("work_items.id"), nullable=False),
                    sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
                    sa.Column("encrypted_body", sa.Text()),
                    sa.Column("attempts", sa.Integer(), nullable=False),
                    sa.Column("next_attempt_at", sa.BigInteger(), nullable=False),
                    sa.Column("delivery_status", sa.String(20), nullable=False))
    for column in ("item_id", "user_id", "next_attempt_at", "delivery_status"):
        op.create_index(f"ix_ticket_notifications_{column}", "ticket_notifications", [column])


def downgrade():
    op.drop_table("ticket_notifications")

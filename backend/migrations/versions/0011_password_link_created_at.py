"""Order outbox messages by creation rather than expiration."""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("password_links", sa.Column("created_at", sa.BigInteger(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("password_links", "created_at")

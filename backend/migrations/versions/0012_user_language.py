"""Add the account's interface language preference."""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("language", sa.String(2), nullable=False, server_default="en"))


def downgrade():
    op.drop_column("users", "language")

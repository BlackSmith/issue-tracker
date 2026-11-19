"""Add optional default project access for application members."""
from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("projects", sa.Column("default_access", sa.String(20), nullable=True))


def downgrade():
    op.drop_column("projects", "default_access")

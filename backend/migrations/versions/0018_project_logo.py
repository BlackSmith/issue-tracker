"""Add normalized project logo storage."""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("projects", sa.Column("logo", sa.LargeBinary(), nullable=True))


def downgrade():
    op.drop_column("projects", "logo")

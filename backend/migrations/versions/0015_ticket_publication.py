"""Allow Owners to publish individual tickets within restricted projects."""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("work_items", sa.Column("is_project_public", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("work_items", "is_project_public")

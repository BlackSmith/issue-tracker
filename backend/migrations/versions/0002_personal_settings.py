"""Personal profiles, avatars and appearance preferences.

Revision ID: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("avatar", sa.LargeBinary(), nullable=True))
    op.add_column("users", sa.Column("theme_accent", sa.String(20), nullable=False, server_default="green"))
    op.add_column("users", sa.Column("theme_background", sa.String(20), nullable=False, server_default="white"))


def downgrade():
    op.drop_column("users", "theme_background")
    op.drop_column("users", "theme_accent")
    op.drop_column("users", "avatar")

"""Add opt-in project ticket visibility restrictions.

Revision ID: 0014
Revises: 0013
"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("projects", sa.Column("restrict_ticket_visibility", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("projects", "restrict_ticket_visibility")

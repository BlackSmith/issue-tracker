"""API tokens and explicit bot identities.

Revision ID: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("is_bot", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table("api_tokens",
                    sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
                    sa.Column("created_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
                    sa.Column("name", sa.String(100), nullable=False),
                    sa.Column("token_prefix", sa.String(12), nullable=False),
                    sa.Column("secret_hash", sa.String(64), nullable=False, unique=True),
                    sa.Column("scopes", sa.JSON(), nullable=False),
                    sa.Column("created_at", sa.BigInteger(), nullable=False),
                    sa.Column("expires_at", sa.BigInteger(), nullable=False),
                    sa.Column("revoked_at", sa.BigInteger()),
                    sa.Column("last_used_at", sa.BigInteger()))
    op.create_index("ix_api_tokens_user_id", "api_tokens", ["user_id"])


def downgrade():
    op.drop_table("api_tokens")
    op.drop_column("users", "is_bot")

"""Local passwords, invitation outbox, and login throttling."""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("auth_version", sa.Integer(), server_default="0", nullable=False))
    op.create_table("password_credentials",
                    sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
                    sa.Column("login_email", sa.String(320), unique=True, nullable=False),
                    sa.Column("password_hash", sa.Text()))
    op.create_table("password_links",
                    sa.Column("secret_hash", sa.String(64), primary_key=True),
                    sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
                    sa.Column("expires_at", sa.BigInteger(), nullable=False),
                    sa.Column("used", sa.Boolean(), nullable=False),
                    sa.Column("recipient", sa.String(320), nullable=False),
                    sa.Column("encrypted_body", sa.Text()),
                    sa.Column("attempts", sa.Integer(), nullable=False),
                    sa.Column("next_attempt_at", sa.BigInteger(), nullable=False),
                    sa.Column("delivery_status", sa.String(20), nullable=False))
    op.create_index("ix_password_links_user_id", "password_links", ["user_id"])
    op.create_table("login_throttles",
                    sa.Column("key", sa.String(64), primary_key=True),
                    sa.Column("attempts", sa.Integer(), nullable=False),
                    sa.Column("expires_at", sa.BigInteger(), nullable=False))


def downgrade():
    op.drop_table("login_throttles")
    op.drop_table("password_links")
    op.drop_table("password_credentials")
    op.drop_column("users", "auth_version")

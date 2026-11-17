"""Separate application membership from explicit project permissions."""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    # Preserve the former account-level read-only ceiling on assigned projects.
    op.execute("""UPDATE project_members SET role = CASE
        WHEN user_id IN (SELECT id FROM users WHERE role = 'reader') THEN 'read-only'
        WHEN role = 'administrator' THEN 'owner'
        WHEN role = 'member' THEN 'reporter'
        ELSE 'read-only' END""")
    op.execute("UPDATE users SET role = 'member' WHERE role = 'reader'")


def downgrade():
    op.execute("""UPDATE project_members SET role = CASE
        WHEN role = 'owner' THEN 'administrator'
        WHEN role = 'reporter' THEN 'member'
        ELSE 'reader' END""")

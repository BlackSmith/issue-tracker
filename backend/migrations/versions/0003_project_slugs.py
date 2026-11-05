"""Stable project slugs for human-readable work item URLs.

Revision ID: 0003
"""
import re
import unicodedata

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("projects", sa.Column("slug", sa.String(100), nullable=True))
    projects = sa.table("projects", sa.column("id", sa.String(36)), sa.column("name", sa.String(150)),
                        sa.column("key", sa.String(10)), sa.column("slug", sa.String(100)))
    connection = op.get_bind()
    used = {"api", "assets", "items", "projects", "settings"}
    # Keep backfill rules frozen here, independently of future application code.
    for row in connection.execute(sa.select(projects.c.id, projects.c.name).order_by(projects.c.key)).mappings():
        ascii_name = unicodedata.normalize("NFKD", row["name"]).encode("ascii", "ignore").decode().lower()
        base = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")[:100].rstrip("-") or "project"
        if base in {"api", "assets", "items", "projects", "settings"}:
            base += "-project"
        slug = base
        suffix = 2
        while slug in used:
            ending = f"-{suffix}"
            slug = base[:100 - len(ending)].rstrip("-") + ending
            suffix += 1
        used.add(slug)
        connection.execute(projects.update().where(projects.c.id == row["id"]).values(slug=slug))
    op.alter_column("projects", "slug", existing_type=sa.String(100), nullable=False)
    op.create_unique_constraint("uq_projects_slug", "projects", ["slug"])


def downgrade():
    op.drop_constraint("uq_projects_slug", "projects", type_="unique")
    op.drop_column("projects", "slug")

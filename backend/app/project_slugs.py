import re
import unicodedata

RESERVED_PROJECT_SLUGS = {"api", "assets", "items", "projects", "settings"}


def project_slug_base(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")[:100].rstrip("-") or "project"
    return slug + "-project" if slug in RESERVED_PROJECT_SLUGS else slug

"""Default developer credential helpers (manager-invited accounts)."""

import re
import unicodedata


def default_developer_password_from_name(name: str) -> str:
    """Predictable initial password; user must change after first login."""
    normalized = unicodedata.normalize("NFKD", name.strip().lower())
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_name).strip("_")
    if not slug:
        slug = "usuario"
    return f"{slug}_cambiar_contrasena"

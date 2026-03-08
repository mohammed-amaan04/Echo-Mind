"""Entity name normalization for deduplication.

Normalizes entity names to a canonical lowercase form, strips punctuation,
collapses whitespace, and applies a configurable alias map so that common
name variations resolve to the same canonical entity.
"""

from __future__ import annotations

import re
import unicodedata

# Alias map: short/informal name → canonical form.
# Extend this as needed for the user's contact graph.
ALIAS_MAP: dict[str, str] = {
    "amaan": "amaan shaikh",
    "abrar": "abrar ahmed",
    "abdullah": "abdullah khan",
}


def normalize_entity_name(name: str) -> str:
    """Return a normalized version of *name* suitable for dedup matching."""
    name = name.strip()
    name = name.lower()
    name = unicodedata.normalize("NFKD", name)
    # Remove punctuation artefacts (keep word chars and spaces)
    name = re.sub(r"[^\w\s]", "", name)
    # Collapse runs of whitespace
    name = re.sub(r"\s+", " ", name).strip()
    # Apply alias mapping
    name = ALIAS_MAP.get(name, name)
    return name

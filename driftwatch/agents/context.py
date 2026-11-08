"""Event context from the web, cached per site in data/context/<site>.json.

load() is what the evidence collector calls at run time: it only reads the cached file and never
searches. The search side (`make context SITE=...`) lives below load() and is never imported by
tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONTEXT_DIR = Path(__file__).resolve().parents[2] / "data" / "context"
KINDS = ("storm", "dam", "construction", "usgs_report", "other")


def path(site: str, root: Path | None = None) -> Path:
    return (root or CONTEXT_DIR) / f"{site}.json"


def load(site: str, root: Path | None = None) -> dict[str, Any] | None:
    """The cached context for a site, or None when there is no file. Items without a URL are
    dropped here too, so a hand-edited file can't slip one through."""
    p = path(site, root)
    if not p.exists():
        return None
    doc = json.loads(p.read_text(encoding="utf-8"))
    items = [i for i in doc.get("items", []) if i.get("url") and i.get("claim")]
    return {**doc, "items": items, "source_file": p.name}

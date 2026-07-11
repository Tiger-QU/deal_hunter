"""Shared helpers for per-category cashback tier notes."""

from __future__ import annotations

import re

MAX_TIERS_SHOWN = 3
MAX_LABEL_LEN = 48


def short_label(label: str, max_len: int = MAX_LABEL_LEN) -> str:
    label = re.sub(r"\s+", " ", (label or "").strip())
    if len(label) <= max_len:
        return label
    return label[: max_len - 1] + "…"


def format_tier_note(
    tiers: list[dict] | None,
    *,
    fallback: str | None = None,
    max_shown: int = MAX_TIERS_SHOWN,
) -> str | None:
    """Build a compact note from label/rate tier dicts."""
    if tiers:
        shown = tiers[:max_shown]
        note = " · ".join(
            f"{short_label(t.get('label', ''))} {t.get('rate', '')}".strip()
            for t in shown
            if t.get("label") or t.get("rate")
        )
        if len(tiers) > max_shown:
            note += f" · +{len(tiers) - max_shown} more"
        return note or fallback
    return fallback


def display_tiers(tiers: list[dict] | None) -> list[dict]:
    """Return tiers with labels shortened for dashboard display."""
    return [
        {
            "label": short_label(t.get("label", "")),
            "rate": t.get("rate", ""),
        }
        for t in (tiers or [])
        if t.get("label") or t.get("rate")
    ]

"""Lifecycle enum -> user-visible display label mapping.

Single source of truth for translating ``ReviewSession.status`` enum
values into the strings operators read. Per ``spec/session_home.md``,
the only divergence today is ``ready -> "Activated"`` (the enum reads
as "ready to be activated" rather than "currently running"); other
states pass through with their first letter capitalised.

Used as a Jinja filter (``lifecycle_label``) wherever a template
renders the enum in user-visible copy. URL slugs, query params, API
responses, log messages, database values, and CSS class names continue
to use the raw enum values.
"""

from __future__ import annotations

DISPLAY_LABELS: dict[str, str] = {
    "ready": "Activated",
}


def lifecycle_display_label(status: str) -> str:
    """Return the user-visible label for a lifecycle enum value.

    Unknown values fall through with ``str.capitalize`` so a future
    state added to the enum still renders something readable until
    the mapping is updated.
    """
    if not status:
        return ""
    return DISPLAY_LABELS.get(status, status.capitalize())


__all__ = ["DISPLAY_LABELS", "lifecycle_display_label"]

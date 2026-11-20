"""Each state's chip tone, one map for every page (ruling 64, U1).

Review Robin's lifecycle palette (`spec/ui_elements.md`, lifecycle
badges): a state that needs work is amber (``warn``), one under way blue
(``info``), one done green (``ok``), one whose window has shut red
(``bad``), and grey (``mute``) only for one set aside or not yet begun.
"""

from __future__ import annotations

TONE: dict[str, str] = {
    # An exercise's and a stage's status (segment AD1K).
    "Draft": "warn",
    "Published": "info",
    "Overdue": "bad",
    "Completed": "ok",
    "Archived": "mute",
    # The form.
    "Open": "info",
    "Closed": "bad",
    # A gate (segment AD1M).
    "Not ready": "warn",
    "Ready": "info",
    "Sent": "info",
    "Detached": "mute",
    "Results in": "ok",
    # An application, and a dossier at a gate (as Dossiers' cells).
    "Submitted": "ok",
    "Entered": "ok",
    "Not entered": "mute",
    "Pending": "warn",
    "Withdrawn": "warn",
    # A stage on the timeline.
    "Done": "ok",
    "Now": "info",
    "Next": "mute",
}


def tone(state: str, default: str = "info") -> str:
    """The chip tone of ``state``, by the one map."""
    return TONE.get(state, default)

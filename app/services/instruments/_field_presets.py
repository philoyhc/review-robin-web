"""Pre-filled type presets for Band 3's data-type picker.

After the per-session ``response_type_definitions`` table retired
(2026-05-26), the Band 3 row's "Type" picker is a plain
``data_type`` dropdown — String / Integer / Decimal / List. Three
operator-friendly presets sit alongside these as a quick-fill: each
one writes ``data_type=list`` plus a pre-filled comma-separated
``list_options``. They are identity-less at storage time — only
the resulting ``data_type`` + ``list_options`` get persisted; the
preset name is not.

Adding a preset:

1. Append a ``(key, label, list_options)`` tuple below.
2. Re-run the Band 3 row JS test to confirm the optgroup renders.
3. No DB migration; no template macro changes.
"""

from __future__ import annotations

from typing import Final


# (key, label, comma-joined list_options). ``key`` is the value the
# template's <select> emits; the JS in instruments_index.html
# catches the ``preset:`` prefix, sets ``data_type=list``, and
# writes ``list_options`` into the inline input.
LIST_PRESETS: Final[tuple[tuple[str, str, str], ...]] = (
    ("preset:boolean", "Boolean (Yes / No)", "Yes, No"),
    (
        "preset:agreement",
        "Agreement (Likert 5)",
        "Strongly agree, Agree, Neutral, Disagree, Strongly disagree",
    ),
    (
        "preset:grades",
        "Grades",
        "A+, A, A-, B+, B, B-, C+, C, D+, D, F",
    ),
)
"""Operator-visible Band 3 quick-fill presets. Each entry's
``list_options`` is a comma-joined string matching the
``InstrumentResponseField._inline_list_csv`` storage shape."""


def preset_list_options_by_key() -> dict[str, str]:
    """Return ``{preset_key: list_options}`` for the template + JS
    to use directly (e.g. as a JSON-serialised data attribute)."""
    return {key: options for key, _label, options in LIST_PRESETS}

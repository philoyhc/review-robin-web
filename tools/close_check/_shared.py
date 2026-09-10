"""The three names every half of the close check needs.

Segment 19J Item 3 measured what the two — really three — jobs in the
old 1,000-line ``tools/close_check.py`` actually shared. Three
snapshots had recorded it as "``REPO``, ``_git`` and
``last_touched_ever``"; ``last_touched_ever``'s only call site is
inside ``check_manifest``, so it was never shared at all. What is:

===================  ========  =======  =====
name                 manifest  archive  sweep
===================  ========  =======  =====
``REPO``                   10        2      5
``_git``                    6        0      3
``Unresolvable``            3        0      2
===================  ========  =======  =====

Nothing else crosses. ``resolve_committed``, the three manifest
regexes and ``last_touched_ever`` are manifest-only and live there.
"""

from __future__ import annotations

import pathlib
import subprocess

REPO = pathlib.Path(__file__).resolve().parents[2]


class Unresolvable(Exception):
    """A usage or resolution error — exit 2, never a check failure."""


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True, text=True, check=False,
    ).stdout

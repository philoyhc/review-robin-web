"""Graph token renewal (`cordware/spec/identity.md`, "Graph"): RRW's and
Utilities' base templates carry the same renewal script, so the two
applications renew the token alike."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = (
    ROOT / "app" / "web" / "templates" / "base.html",
    ROOT / "utilityapps" / "templates" / "utilities" / "base.html",
)
BLOCK = re.compile(r"<script data-graph-renewal>(.*?)</script>", re.DOTALL)


def _block(path: Path) -> str:
    found = BLOCK.findall(path.read_text(encoding="utf-8"))
    assert len(found) == 1, f"{path} carries {len(found)} renewal blocks"
    return "\n".join(line.strip() for line in found[0].strip().splitlines())


def test_both_applications_carry_the_same_renewal_script() -> None:
    assert _block(TEMPLATES[0]) == _block(TEMPLATES[1])


def test_the_script_renews_through_easy_auth_every_45_minutes() -> None:
    script = _block(TEMPLATES[0])
    assert 'fetch("/.auth/refresh"' in script
    assert "45 * 60 * 1000" in script
    assert "window.cordwareRenewGraph" in script

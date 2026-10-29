"""What both applications' pages share: the local-only gate for
placeholders and the account's initials (segment 1D, rung 1). Neither
application may import the other (`residentialapps/spec/architecture.md`,
"Import boundaries"), so what both need lives here."""

from __future__ import annotations

from fastapi import HTTPException

from cordware.identity import is_local


def placeholders_local_only() -> None:
    """Placeholder screens show sample data and enforce no access rules
    yet, so they answer only on a local run (`APP_ENV=local`). Deployed,
    they are 404 until the items that wire them; a router depends on this
    until then."""
    if not is_local():
        raise HTTPException(status_code=404)


def initials(label: str) -> str:
    parts = [p for p in label.replace("@", " ").split() if p[:1].isalpha()]
    return "".join(p[0] for p in parts[:2]).upper() or "?"

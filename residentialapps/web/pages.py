"""What both applications' pages share: the preview gate for placeholders
and the account's initials (segment 1D, rung 1). Neither application may
import the other (`residentialapps/spec/architecture.md`, "Import
boundaries"), so what both need lives here."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException, Request

from cordware.identity import Identity, current_identity, is_local

# The preview list: a Markdown file beside the `residentialapps/` package,
# put there by a deployment's build (Cordware keeps the list and ships it
# with each release). It never lives in this repository: it names real
# people, and `.gitignore` keeps a local copy out.
PREVIEW_FILE = Path(__file__).resolve().parents[2] / "residential_preview.md"
# A list item whose first word is an address, backticked or not:
# "- someone@example.edu" or "* `someone@example.edu` (RF, Tower A)".
_LIST_ADDRESS = re.compile(r"^\s*[-*+]\s+`?([^\s`@,;]+@[^\s`,;]+)`?(?=[\s,;]|$)")


@lru_cache(maxsize=4)
def preview_addresses(path: Path) -> frozenset[str]:
    """The addresses the preview list names, folded. Read once per
    process, so a change ships with a deployment. No file names nobody."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return frozenset()
    return frozenset(
        match.group(1).strip().lower()
        for line in text.splitlines()
        if (match := _LIST_ADDRESS.match(line))
    )


def is_previewer(identity: Identity | None, path: Path | None = None) -> bool:
    """The platform super-admin, or an account whose mail, sign-in name
    (UPN) or address the preview list (`PREVIEW_FILE` unless given)
    names."""
    if identity is None:
        return False
    if identity.is_super_admin:
        return True
    listed = preview_addresses(path or PREVIEW_FILE)
    return any(
        address is not None and address.strip().lower() in listed
        for address in (identity.mail, identity.upn, identity.email)
    )


def placeholders_previewers_only(request: Request) -> None:
    """Placeholder screens show sample data and enforce no access rules
    yet. On a local run (`APP_ENV=local`) they answer anyone; deployed,
    only a previewer (`is_previewer`), and 404 for everyone else, until
    the items that wire them. A router depends on this until then."""
    if is_local():
        return
    if not is_previewer(current_identity(request)):
        raise HTTPException(status_code=404)


def initials(label: str) -> str:
    parts = [p for p in label.replace("@", " ").split() if p[:1].isalpha()]
    return "".join(p[0] for p in parts[:2]).upper() or "?"

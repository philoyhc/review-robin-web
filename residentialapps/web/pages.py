"""What both applications' pages share: the preview gate for placeholders
and the account's initials (segment 1D, rung 1). Neither application may
import the other (`residentialapps/spec/architecture.md`, "Import
boundaries"), so what both need lives here."""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException, Request

from cordware.identity import Identity, current_identity, is_local

log = logging.getLogger("residentialapps.web")

# The preview list: a Markdown file beside the `residentialapps/` package,
# put there by a deployment's build (Cordware keeps the list and ships it
# with each release). It never lives in this repository: it names real
# people, and `.gitignore` keeps a local copy out.
PREVIEW_FILE = Path(__file__).resolve().parents[2] / "residential_preview.md"
# A top-level list item's first word, at the left margin:
# "- someone@example.edu" or "* `someone@example.edu` (RF, Tower A)".
# Indented items are never read, so a nested example, an indented fence
# or an indented code block cannot name anyone.
_LIST_ITEM = re.compile(r"^[-*+][ \t]+(\S+)")
_ADDRESS = re.compile(r"[^@\s<>()\[\]]+@[^@\s<>()\[\]]+\.[^@\s<>()\[\]]+")
# What Markdown hides: an HTML comment (unterminated, to the end), so
# commenting an entry out removes it.
_COMMENT = re.compile(r"<!--.*?(?:-->|\Z)", re.DOTALL)
# A fence opens on three or more backticks or tildes, at any indentation,
# and closes only on a run of the same character at least as long, alone
# on its line, indented no deeper than the opener (three spaces for one
# at the margin). Reading more as fenced only ever reads fewer addresses.
_FENCE = re.compile(r"^( *)(`{3,}|~{3,})(.*)$")


def _first_address(line: str) -> str | None:
    match = _LIST_ITEM.match(line)
    if match is None:
        return None
    word = match.group(1)
    if word.startswith("`"):
        word = word[1:].split("`", 1)[0]
    word = word.strip("<>").rstrip(".,;:")
    return word.lower() if _ADDRESS.fullmatch(word) else None


def parse_preview_list(text: str) -> frozenset[str]:
    """The addresses a preview list names, folded: each top-level list
    item whose first word is an address. Indented lines, comments and
    fenced code are not read."""
    addresses: set[str] = set()
    fence: tuple[str, int] | None = None  # the opener's marker and indent
    for line in _COMMENT.sub("", text).expandtabs(4).splitlines():
        match = _FENCE.match(line)
        if fence is not None:
            marker, indent = fence
            if (
                match
                and len(match.group(1)) <= max(3, indent)
                and match.group(2)[0] == marker[0]
                and len(match.group(2)) >= len(marker)
                and not match.group(3).strip()
            ):
                fence = None
            continue
        if match and not (match.group(2)[0] == "`" and "`" in match.group(3)):
            fence = (match.group(2), len(match.group(1)))
        elif address := _first_address(line):
            addresses.add(address)
    return frozenset(addresses)


@lru_cache(maxsize=4)
def preview_addresses(path: Path) -> frozenset[str]:
    """The addresses the preview list at ``path`` names. Read once per
    process, so a change ships with a deployment. No file, or one that
    cannot be read, names nobody."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return frozenset()
    except (OSError, UnicodeDecodeError):
        log.warning("residential preview list unreadable; admitting only the super-admin")
        return frozenset()
    addresses = parse_preview_list(text)
    log.info("residential preview list: %d address(es)", len(addresses))
    return addresses


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

"""What both applications' pages share: the preview gate for placeholders
and the account's initials (segment 1D, rung 1). Neither application may
import the other (`residentialapps/spec/architecture.md`, "Import
boundaries"), so what both need lives here."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Mapping
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

from fastapi import HTTPException, Request

from cordware.identity import Identity, current_identity, institution_name, is_local

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
# A fence opens on three or more backticks or tildes, at any indentation,
# and closes only on a run of the same character at least as long, alone
# on its line, indented no deeper than the opener (three spaces for one
# at the margin). Reading more as fenced only ever reads fewer addresses.
_FENCE = re.compile(r"^( *)(`{3,}|~{3,})(.*)$")
_OPEN, _CLOSE = "<!--", "-->"
# The RA previewers section (author, 2026-11-09): its addresses reach only
# RA Leave's RA pages and the landing. It fails safe, since a heading
# written a little differently must never make RA previewers full ones:
# any line that is not a list item and says "RA previewer(s)", however
# marked up ("## RA previewers:", "**RA previewers**", an underlined or
# indented heading, plain prose), starts the section, and only a `#`
# heading that does not say it ends the section. Reading the section as
# starting early or ending late only ever narrows access.
_RA_MARKER = re.compile(r"\bra previewers?\b")
_ENDS_SECTION = re.compile(r"^ {0,3}#{1,6}(?:[ \t]|$)")
# In that section a line at the margin may also be a distribution list as
# a mail client copies it, "Name <a@b.edu>; Name <c@d.edu>": each address
# in angle brackets names it, so the list is pasted as it is. The whole
# line must be names and angle-bracketed addresses, separated by `;` or
# `,`, so prose, a quote or a table row that mentions one names nobody.
# A name never holds a colon, and the line must separate an address with
# `;` or `,` as a mail client does (Codex review), so "Contact: <a@b.edu>"
# or "Do not grant access to <a@b.edu>" names nobody; one person alone is
# copied as "Name <a@b.edu>;".
_ANGLED = re.compile(r"<([^<>\s]+)>")
_ENTRY = r"[^<>;:|]*<[^<>\s]+>"
_DISTRIBUTION = re.compile(rf"{_ENTRY}(?:[ \t]*[;,][ \t]*{_ENTRY})*[ \t]*[;,]?[ \t]*")
_SEPARATED = re.compile(r">[ \t]*[;,]")


def _is_distribution_line(line: str) -> bool:
    line = line.rstrip()
    return bool(_DISTRIBUTION.fullmatch(line) and _SEPARATED.search(line))


def _says_ra_previewers(line: str) -> bool:
    return bool(_RA_MARKER.search(" ".join(re.sub(r"[^a-z]+", " ", line.lower()).split())))


class PreviewList(NamedTuple):
    """The addresses a preview list names: full previewers reach every
    placeholder; RA previewers only RA Leave's RA pages and the landing.
    An address in both is a full previewer."""

    full: frozenset[str]
    ra: frozenset[str]


def _first_address(line: str) -> str | None:
    match = _LIST_ITEM.match(line)
    if match is None:
        return None
    word = match.group(1)
    if word.startswith("`"):
        word = word[1:].split("`", 1)[0]
    # Trailing punctuation first, so `<a@b.edu>.` loses the full stop and
    # then its brackets (findings L4).
    word = word.rstrip(".,;:").strip("<>").rstrip(".,;:")
    return word.lower() if _ADDRESS.fullmatch(word) else None


def _leaves_comment_open(text: str) -> bool:
    """Whether ``text``, read outside a comment, ends inside one."""
    while (start := text.find(_OPEN)) >= 0:
        end = text.find(_CLOSE, start + len(_OPEN))
        if end < 0:
            return True
        text = text[end + len(_CLOSE) :]
    return False


def _closes_fence(match: re.Match[str] | None, fence: tuple[str, int]) -> bool:
    marker, indent = fence
    return bool(
        match
        and len(match.group(1)) <= max(3, indent)
        and match.group(2)[0] == marker[0]
        and len(match.group(2)) >= len(marker)
        and not match.group(3).strip()
    )


def parse_preview_list(text: str) -> frozenset[str]:
    """Every address a preview list names, in either section."""
    full, ra = parse_preview_sections(text)
    return full | ra


def parse_preview_sections(text: str) -> PreviewList:
    """The addresses a preview list names, folded, by section: each
    top-level list item whose first word is an address, under the
    "RA previewers" heading or not. Indented lines, comments and fenced
    code are not read, so a heading in them changes no section.

    One pass, line by line. Fences are matched on the raw line, so a
    comment never opens or closes one, and inside a fence nothing is a
    comment. Comments only ever remove: a line is read up to its first
    `<!--`, and nothing on a line that ends a comment is read."""
    full: set[str] = set()
    ra: set[str] = set()
    in_ra = False
    fence: tuple[str, int] | None = None  # the opener's marker and indent
    in_comment = False
    for line in text.expandtabs(4).splitlines():
        match = _FENCE.match(line)
        if fence is not None:
            if _closes_fence(match, fence):
                fence = None
            continue
        if in_comment:
            end = line.find(_CLOSE)
            if end >= 0:
                in_comment = _leaves_comment_open(line[end + len(_CLOSE) :])
            continue
        if match and not (match.group(2)[0] == "`" and "`" in match.group(3)):
            fence = (match.group(2), len(match.group(1)))
            continue
        head, opened, tail = line.partition(_OPEN)
        if opened:
            in_comment = _leaves_comment_open(_OPEN + tail)
        if address := _first_address(head):
            (ra if in_ra else full).add(address)
        elif _LIST_ITEM.match(head) is None and _says_ra_previewers(head):
            in_ra = True
        elif _ENDS_SECTION.match(head):
            in_ra = False
        elif in_ra and head[:1] not in (" ", "") and _is_distribution_line(head):
            ra.update(word.lower() for word in _ANGLED.findall(head) if _ADDRESS.fullmatch(word))
    return PreviewList(frozenset(full), frozenset(ra - full))


_NOBODY = PreviewList(frozenset(), frozenset())


@lru_cache(maxsize=4)
def preview_lists(path: Path) -> PreviewList:
    """The addresses the preview list at ``path`` names, by section. Read
    once per process, so a change ships with a deployment. No file, or one
    that cannot be read, names nobody."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _NOBODY
    except (OSError, UnicodeDecodeError):
        log.warning("residential preview list unreadable; admitting only the super-admin")
        return _NOBODY
    lists = parse_preview_sections(text)
    log.info(
        "residential preview list: %d address(es), %d RA-only",
        len(lists.full) + len(lists.ra),
        len(lists.ra),
    )
    return lists


def preview_addresses(path: Path) -> frozenset[str]:
    """Every address the preview list at ``path`` names."""
    full, ra = preview_lists(path)
    return full | ra


def _named(identity: Identity, listed: frozenset[str]) -> bool:
    return any(
        address is not None and address.strip().lower() in listed
        for address in (identity.mail, identity.upn, identity.email)
    )


def is_previewer(identity: Identity | None, path: Path | None = None) -> bool:
    """The platform super-admin, or an account whose mail, sign-in name
    (UPN) or address the preview list (`PREVIEW_FILE` unless given)
    names."""
    if identity is None:
        return False
    if identity.is_super_admin:
        return True
    return _named(identity, preview_lists(path or PREVIEW_FILE).full)


def is_ra_previewer(identity: Identity | None, path: Path | None = None) -> bool:
    """An account the preview list names under "RA previewers" only: it
    reaches RA Leave's RA pages and the landing (author, 2026-11-09)."""
    if identity is None or is_previewer(identity, path):
        return False
    return _named(identity, preview_lists(path or PREVIEW_FILE).ra)


def placeholders_previewers_only(request: Request) -> None:
    """Placeholder screens show sample data and enforce no access rules
    yet. On a local run (`APP_ENV=local`) they answer anyone; deployed,
    only a previewer (`is_previewer`), and 404 for everyone else, until
    the items that wire them. A router depends on this until then."""
    if is_local():
        return
    if not is_previewer(current_identity(request)):
        raise HTTPException(status_code=404)


def ra_pages_previewers(request: Request) -> None:
    """The gate for RA Leave's RA pages and the landing: a previewer, or
    an RA previewer (author, 2026-11-09); 404 for everyone else."""
    if is_local():
        return
    identity = current_identity(request)
    if not (is_previewer(identity) or is_ra_previewer(identity)):
        raise HTTPException(status_code=404)


def ra_preview_only(request: Request) -> bool:
    """Whether this request is an RA previewer's, who sees the landing as
    an RA and no viewer to switch to."""
    return not is_local() and is_ra_previewer(current_identity(request))


#: Areas that are the account's, not places: they sit in the account menu,
#: as Review Robin's Settings and Admin do (author, 2026-11-02).
ACCOUNT_AREAS = frozenset({"Sys admin"})


def split_areas[A: Mapping[str, object]](areas: Iterable[A]) -> tuple[tuple[A, ...], tuple[A, ...]]:
    """The switcher's places and the account menu's entries, from one list
    of areas (`docs/header_chrome.md` §3, §4)."""
    places = tuple(a for a in areas if a["label"] not in ACCOUNT_AREAS)
    account = tuple(a for a in areas if a["label"] in ACCOUNT_AREAS)
    return places, account


def top_line(unit_name: str | None) -> str:
    """The bar's top line (`docs/header_chrome.md` §6, RRW segment 20D):
    the top-level Unit's name when it is set, else the workspace default,
    `CORDWARE_INSTITUTION_NAME`; empty means no top line. Until segment 1B
    item 4 stores the Unit, each application passes its sample's."""
    return (unit_name or "").strip() or institution_name()


def initials(label: str) -> str:
    parts = [p for p in label.replace("@", " ").split() if p[:1].isalpha()]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


# The desktop-oriented pages of `residentialapps/spec/applications.md`
# ("Pages"), by path prefix relative to the app's mount: they keep the
# page's full width rather than two of its three columns (author,
# 2026-11-08), their wide tables being the point of them. A prefix
# covers its pages beneath it, as /rosters/ does a person's page.
DESKTOP_PAGES: Mapping[str, tuple[str, ...]] = {
    "residentialops": (
        "/ra-leave/admin/",
        "/ra-leave/staff/precinct",
        "/ra-events/admin/",
        "/rosters/",
        "/sys-admin/",
    ),
    "supportlogs": ("/sys-admin/",),
}


def desktop_oriented(app_key: str, path: str) -> bool:
    """Whether `path`, relative to the app's mount, is a desktop-oriented
    page."""
    return any(
        path == prefix.rstrip("/") or path.startswith(prefix.rstrip("/") + "/")
        for prefix in DESKTOP_PAGES.get(app_key, ())
    )

"""Every rendered table sits in a ``.table-scroll`` wrapper.

``.table-scroll`` is ``overflow-x: auto`` (``base.html``): a table wider
than its card scrolls *inside* the card instead of pushing the whole
document sideways. Before 19O Item 8 it was applied four times, each
time reactively, after someone noticed a page scrolling — Instruments,
Assignments, Invitations, Responses — and each application left the rest
of the app as it found it.

Measured at that point, in Chromium against a session with every tag
slot and profile link filled: **seven of eleven operator pages pushed
the document sideways**, Relationships from 1100px down and the Sessions
lobby, Archive, Reviewers, Reviewees from 900. ``spec/ui_elements.md``
§10 said this could not happen — it reserved the wrapper for tables
"wider than [their] card by construction" and ended "a roster that
measures inside its card goes without". No roster measured inside its
card below 1100px.

**The rule is now uniform, which is the point.** The alternative was a
width threshold, and nothing in a template knows a rendered width; the
judgment that produced four reactive fixes is exactly what cannot be
written down. A wrapper on a table that never overflows costs nothing —
verified: table geometry at 1400px is byte-identical across all eleven
operator pages before and after the sweep, and the twelve page/width
combinations that scrolled sideways stopped, with none newly broken.

So this asks one question with no exceptions list: is there a
``.table-scroll`` ancestor? An exceptions list would be the judgment
call coming back in a form nobody re-measures.
"""

from __future__ import annotations

import pathlib
import re
from html.parser import HTMLParser

TEMPLATES = pathlib.Path(__file__).resolve().parents[2] / "app" / "web" / "templates"

#: A ``<table>`` inside a comment or a script is documentation, not markup.
#: Several templates explain the sortable-table contract by quoting it.
_NON_MARKUP = (
    re.compile(r"\{#.*?#\}", re.S),           # Jinja comment
    re.compile(r"<!--.*?-->", re.S),          # HTML comment
    re.compile(r"<script\b.*?</script>", re.S | re.I),
    re.compile(r"<style\b.*?</style>", re.S | re.I),
)

#: Jinja statements and expressions, blanked before parsing.
#:
#: ``html.parser`` takes ``{`` and ``%`` as legal tag-name characters, so
#: the house idiom ``<table{% if group.is_group %} class="…"{% endif %}>``
#: — no space before the tag — parses as an element named ``table{%`` and
#: never reaches ``handle_starttag``'s ``tag == "table"``. The table is not
#: reported unwrapped; it is not seen at all. That is a **false pass**, and
#: it was live: ``reviewer/review_surface.html``'s response table, the
#: widest in the app, was invisible to the first version of this check.
_JINJA = (re.compile(r"\{%.*?%\}", re.S), re.compile(r"\{\{.*?\}\}", re.S))

#: A ``<table>`` start tag as written, for reconciling against the parse.
_RAW_TABLE = re.compile(r"<table\b", re.I)

#: A ``<table>`` inside a string literal — a table built in JavaScript.
#: Distinguished from the several JS *comments* that quote the sortable
#: contract (``//   <table data-rrw-sortable="{cookie-key}">``) by the
#: opening quote, which only a literal has.
_BUILT_TABLE = re.compile(r"""['"]<table\b""")

#: Where a script-built table is written, and so what must carry the
#: wrapper. There is no server-rendered ``<table>`` for the sweep to wrap,
#: and stripping ``<script>`` — which the parse must do, or every quoted
#: example becomes a finding — takes these with it.
_BUILT_TABLE_HOSTS = {
    "operator/instruments_index.html": "data-new-model-band2-preview",
}

#: The one table that goes without, and why.
#:
#: ``.shaper-preview-table`` is flattened to ``display: block; width: 100%``
#: with its cells as wrapping flex children (``base.html``), and its own
#: ``.shaper-preview-scroll`` container sets ``overflow-x: visible`` with the
#: reason written beside it: the row *wraps to a second line* "rather than
#: scrolling horizontally". It is a table in name only and cannot exceed its
#: container, so a scroller there would re-add what that rule removed.
#: Anchored to a CSS decision, not to a judgment about width.
_NOT_LAID_OUT_AS_A_TABLE = "shaper-preview-table"

_VOID = frozenset(
    "area base br col embed hr img input link meta param source track wbr".split()
)


def _blank(match: re.Match[str]) -> str:
    """Replace a stripped span with its own newlines.

    Deleting it outright shifts every line number after it, which made a
    first pass at this check report ``review_surface.html``'s table 80
    lines above where it lives. A failure naming the wrong line is worse
    than no failure: it sends the reader to innocent markup.
    """
    return "\n" * match.group(0).count("\n")


class _TableFinder(HTMLParser):
    """Records each ``<table>`` and whether a ``.table-scroll`` encloses it."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._stack: list[tuple[str, str]] = []
        self.tables: list[tuple[int, bool]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = dict(attrs).get("class") or ""
        if tag == "table":
            # Token match, not substring: `no-table-scroll` is not a wrapper.
            wrapped = any(
                "table-scroll" in cls.split() for _, cls in self._stack
            ) or _NOT_LAID_OUT_AS_A_TABLE in classes.split()
            self.tables.append((self.getpos()[0], wrapped))
        if tag not in _VOID:
            self._stack.append((tag, classes))

    def handle_endtag(self, tag: str) -> None:
        # Unwind to the matching open tag; templates close branches inside
        # ``{% if %}`` arms, so an unmatched close must not desync the stack.
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index][0] == tag:
                del self._stack[index:]
                return


def _markup(path: pathlib.Path) -> str:
    """The template with its non-markup and its Jinja tags blanked."""
    text = path.read_text()
    for pattern in _NON_MARKUP + _JINJA:
        text = pattern.sub(_blank, text)
    return text


def _scan(path: pathlib.Path) -> list[tuple[int, bool]]:
    text = _markup(path)
    if not _RAW_TABLE.search(text):
        return []
    finder = _TableFinder()
    finder.feed(text)
    return finder.tables


def _all_tables() -> dict[pathlib.Path, list[tuple[int, bool]]]:
    return {p: t for p in sorted(TEMPLATES.rglob("*.html")) if (t := _scan(p))}


def test_the_scan_finds_the_tables() -> None:
    """Guards the check itself.

    Every assertion below is over what ``_scan`` returns, so a parser that
    silently found nothing — a renamed directory, a stricter strip, an
    exception swallowed — would pass all of them while checking nothing.
    """
    found = _all_tables()

    assert len(found) >= 20, f"only {len(found)} templates with a table"
    assert sum(len(t) for t in found.values()) >= 30


def test_the_parser_sees_every_table_that_is_written() -> None:
    """The check's real failure mode: a table it cannot see.

    A table reported unwrapped is a loud, fixable failure. A table the
    parser never reaches is a silent pass, and the first version of this
    file had one — ``<table{% if ... %}`` parses as an element named
    ``table{%``. Counting what is written against what was parsed is the
    only assertion that catches the next such idiom, whatever it is.
    """
    mismatched = []
    for path in sorted(TEMPLATES.rglob("*.html")):
        text = _markup(path)
        written = len(_RAW_TABLE.findall(text))
        parsed = len(_scan(path))
        if written != parsed:
            mismatched.append(f"{path.relative_to(TEMPLATES)}: "
                              f"{written} written, {parsed} parsed")

    assert not mismatched, (
        "a <table> was written but not parsed, so the wrapper check never "
        "saw it:\n  " + "\n  ".join(mismatched)
    )


def test_a_script_built_table_has_a_wrapped_host() -> None:
    """The gate's blind spot, named rather than left.

    The parse strips ``<script>`` bodies, so a table assembled in
    JavaScript is invisible to every other check here — removing the
    wrapper from its host left all of them green. ``rebuildPreview`` in
    ``instruments_index.html`` writes a ``table-layout: fixed`` table with
    operator-set column widths, which is the shape that overflows.
    """
    builders = {
        str(path.relative_to(TEMPLATES)): len(_BUILT_TABLE.findall(path.read_text()))
        for path in sorted(TEMPLATES.rglob("*.html"))
        if _BUILT_TABLE.search(path.read_text())
    }

    assert builders, "no script-built tables found — has the idiom moved?"
    assert set(builders) == set(_BUILT_TABLE_HOSTS), (
        "a template builds a <table> in JavaScript and this file does not "
        f"name where it lands: {sorted(set(builders) - set(_BUILT_TABLE_HOSTS))}"
    )
    for name, marker in _BUILT_TABLE_HOSTS.items():
        text = (TEMPLATES / name).read_text()
        # The *start tag*, not the first mention: the same attribute names
        # a dozen CSS selectors further up, and a first-occurrence locator
        # read one of those instead — the positional-anchor mistake this
        # item has now made three times.
        host = re.search(rf"<[a-zA-Z]+[^>]*\b{re.escape(marker)}\b[^>]*>", text)

        assert host, f"{name}: no element carries `{marker}`"
        classes = re.search(r'class="([^"]*)"', host.group(0))
        assert classes and "table-scroll" in classes.group(1).split(), (
            f"{name}: the host for its script-built table(s) "
            f"(`{marker}`) has no `.table-scroll`:\n  {host.group(0)}"
        )


def test_the_scan_can_tell_wrapped_from_unwrapped() -> None:
    """Guards the detector, which the sweep above cannot.

    Every template now passes, so a ``_TableFinder`` that reported
    *everything* wrapped would be indistinguishable from a correct one:
    hard-coding ``wrapped = True`` survived the other two checks in this
    file. The only way to see that is a table known to be unwrapped.
    """
    wrapped = _TableFinder()
    wrapped.feed('<div class="card"><div class="table-scroll">'
                 "<table><tr><td>x</td></tr></table></div></div>")
    unwrapped = _TableFinder()
    unwrapped.feed('<div class="card"><table><tr><td>x</td></tr></table></div>')
    # A sibling is not an ancestor: the wrapper has to enclose the table.
    sibling = _TableFinder()
    sibling.feed('<div class="table-scroll"></div>'
                 "<table><tr><td>x</td></tr></table>")
    # A class that merely contains the name is not the class.
    lookalike = _TableFinder()
    lookalike.feed('<div class="no-table-scroll">'
                   "<table><tr><td>x</td></tr></table></div>")
    # One class among several still counts.
    among = _TableFinder()
    among.feed('<div class="card table-scroll wide">'
               "<table><tr><td>x</td></tr></table></div>")

    assert [w for _, w in wrapped.tables] == [True]
    assert [w for _, w in unwrapped.tables] == [False]
    assert [w for _, w in sibling.tables] == [False]
    assert [w for _, w in lookalike.tables] == [False]
    assert [w for _, w in among.tables] == [True]


def test_the_scan_reports_the_line_the_table_is_on() -> None:
    """A failure has to send the reader to the right markup.

    A first pass stripped comments by deleting them, which shifted every
    line after — it named line 173 of ``review_surface.html``, where the
    table is on 253.
    """
    finder = _TableFinder()
    text = "\n".join(["{# a comment", "spanning", "three lines #}", "<table></table>"])
    for pattern in _NON_MARKUP:
        text = pattern.sub(_blank, text)
    finder.feed(text)

    assert [line for line, _ in finder.tables] == [4]


def test_every_table_sits_in_a_table_scroll_wrapper() -> None:
    unwrapped = [
        f"{path.relative_to(TEMPLATES)}:{line}"
        for path, tables in _all_tables().items()
        for line, wrapped in tables
        if not wrapped
    ]

    assert not unwrapped, (
        "a <table> with no `.table-scroll` ancestor:\n  "
        + "\n  ".join(unwrapped)
        + "\n\nWrap it: <div class=\"table-scroll\"> ... </div>. The wrapper "
        "keeps a wide table's overflow inside its card instead of scrolling "
        "the whole page sideways (spec/ui_elements.md section 10). There is "
        "no width threshold and no exceptions list — a template cannot know "
        "a rendered width, and the wrapper costs a narrow table nothing."
    )

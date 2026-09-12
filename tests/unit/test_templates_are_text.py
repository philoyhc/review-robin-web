"""No template carries a NUL byte. Segment 19L Item 4.

A single NUL anywhere in a file makes ``grep`` classify the whole file as
binary: instead of printing matching lines it emits ``Binary file … matches``.
``operator/instruments_index.html`` carried one — a composite-key separator
written as the raw byte rather than an escape — and it is the largest template
in this repository, so every plain ``grep`` against its ~3,700 lines returned
something that looked like nothing.

**This guard exists because that cost three wrong findings in one day**
(2026-09-12). Two were caught on re-check. The third was not caught by the
author of the search at all:

    grep -rn "beforeunload" app/ spec/ docs/ | grep -v Binary

The only match in ``app/`` was in that template, so grep emitted the
``Binary file …`` line — and the ``| grep -v Binary``, added to tidy the
output, deleted it. The search reported nothing, "nothing" was written up as a
finding, and a design discussion was built on a feature's supposed absence
until a screenshot of it working arrived.

*A check whose output-tidying step removes the disconfirming evidence is worse
than no check: it returns a confident negative rather than a silence.*

**Why a guard rather than a note.** A NUL is invisible everywhere a human
would look — it renders as nothing in a diff, in an editor, and in a browser —
so review cannot catch it. The alternative was a line in ``CLAUDE.md`` telling
every future reader to pass ``-a``, which is a standing instruction to remember
something in place of removing the thing to remember.

**What this does not do.** It says nothing about other control characters:
tabs and their kin are ordinary in templates. NUL is singled out because it is
the one that reclassifies a file.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TEMPLATES = REPO / "app" / "web" / "templates"


def test_no_template_contains_a_nul_byte() -> None:
    """Read as bytes, deliberately — a text-mode read can mask the thing."""
    offenders = []
    for path in sorted(TEMPLATES.rglob("*.html")):
        data = path.read_bytes()
        if b"\x00" in data:
            line = data[: data.index(b"\x00")].count(b"\n") + 1
            offenders.append(
                f"{path.relative_to(REPO)}: {data.count(chr(0).encode())} "
                f"NUL byte(s), first at line {line}"
            )
    assert not offenders, (
        "a NUL byte makes grep treat the whole file as binary, so searches "
        "against it silently return nothing. Write the character as a "
        "\\u0000 escape instead — identical to the JavaScript engine, and "
        "the file stays text:\n  " + "\n  ".join(offenders)
    )


def test_the_separator_that_caused_this_is_still_an_escape() -> None:
    """The specific line, pinned so a revert is loud rather than silent.

    The general guard above would also catch a reverted raw byte. This one
    names the place, so the failure says *which* line and *why* it is spelled
    the way it is, rather than leaving the next author to rediscover that the
    escape was deliberate and re-"simplify" it.
    """
    page = (TEMPLATES / "operator" / "instruments_index.html").read_text()
    assert ".join('\\u0000')" in page, (
        "the cohort-preview composite-key separator is no longer written as "
        "a \\u0000 escape. The value is correct — a separator that cannot "
        "occur in roster data — but writing it as a raw NUL turns this "
        "template binary to grep (19L.4)"
    )

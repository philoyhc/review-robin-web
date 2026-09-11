"""The preview-count sentence the seven table pages share
(Segment 19I Item 10; rewritten for 19J.5).

**What it used to be.** Before Item 10 the seven pages carrying a row
preview — Reviewers, Reviewees, Relationships, Observers, Assignments,
Invitations, Responses — reported their counts four different ways.
Item 10 made it one sentence with four states, distinguishing a
**filter** (rows excluded — they do not match, so "more not shown"
would be a lie) from a **cap** (rows withheld — the operator needs to
know before reading the table as complete).

**What 19J.5 made it.** The cap stopped being a truncation and became
a page size. Where a pager renders, the operator can reach every row
and a sentence saying so is the noise the quiet case exists to avoid —
the strip already states the position. So the sentence stopped being
the table's caption and became **the filter's**:

===========================  ==============================================
State                        Sentence
===========================  ==============================================
filter active, under the cap ``Showing 37 reviewers.``
filter active, capped        ``Showing 500 of 900 reviewers, 400 more
                             not shown.``
no filter, paged             *(nothing — the pager says where you are)*
no filter, not yet paged     ``Showing first 200 of 10,000 assignments;
                             9,800 more not shown.``
===========================  ==============================================

The roster total went with the change. Under the filter branch ``of
M`` can only mean the matching pool, so the word ``matching`` that
Item 10 introduced to tell two pools apart has nothing left to
disambiguate, and the denominator that used to say how far the filter
narrowed is the info card's job rather than this sentence's.

**``paged`` is transitional and has a removal date.** It marks a view
whose pager is live, so nothing is withheld. 19J.5 wires the pages one
rung at a time; a page that has not had its rung yet still truncates
for real and still owes the operator the old notice. When the last
rung lands, no caller passes ``paged=False`` on an unfiltered view,
that branch is dead by construction, and it goes — along with this
paragraph. ``tests/unit/test_preview_count_line.py`` carries the
assertion that enforces it.
"""

from __future__ import annotations

__all__ = ["preview_count_line"]



def _agree(count: int, noun: str) -> str:
    """Singularize ``noun`` for a count of exactly one.

    Needed only since 19J.5. The old sentence put the noun against the
    *pool* — ``Showing 1 of 2 reviewers.`` — where the plural was
    always right. The filtered sentence puts it against the count, and
    ``Showing 1 reviewers.`` is the commonest case there is: an
    operator searching for one person.

    A trailing ``s`` covers every noun these pages pass — reviewers,
    reviewees, relationships, observers, assignments — and
    ``test_preview_count_line.py`` pins all five, so a future noun this
    rule would mangle fails a test rather than reaching an operator.
    """
    if count == 1 and noun.endswith("s"):
        return noun[:-1]
    return noun


def preview_count_line(
    *,
    shown: int,
    pool: int,
    noun: str,
    is_filtered: bool,
    paged: bool = False,
) -> str | None:
    """Compose the count line for a preview table, or ``None``.

    ``shown`` is how many rows the table holds and ``pool`` how many
    the view could hold — the matching set when a filter is active,
    the whole roster otherwise. ``noun`` is the plural thing being
    counted from the operator's point of view, which is not always the
    row's own type: the Invitations table is one row per reviewer and
    says ``reviewers``, and Responses says ``reviewees``.

    ``is_filtered`` is the route's own filter flag — the same one that
    suppresses the pager, deliberately, so the two affordances cannot
    disagree about which mode the page is in. It is **not** derived
    from ``shown < pool`` here: a filter that happens to match every
    row is still a filtered view, and reports as one.
    """
    withheld = max(pool - shown, 0)

    if is_filtered:
        if withheld == 0:
            return f"Showing {shown:,} {_agree(shown, noun)}."
        return (
            f"Showing {shown:,} of {pool:,} {noun}, "
            f"{withheld:,} more not shown."
        )

    # Unfiltered. A paged view reaches everything, so the pager speaks
    # and this says nothing.
    if paged or withheld == 0:
        return None
    return (
        f"Showing first {shown:,} of {pool:,} {noun}; "
        f"{withheld:,} more not shown."
    )

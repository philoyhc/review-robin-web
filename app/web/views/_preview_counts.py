"""The one preview-count sentence the seven table pages share
(Segment 19I Item 10).

Before this module the seven pages carrying a row preview —
Reviewers, Reviewees, Relationships, Observers, Assignments,
Invitations, Responses — reported their row counts four different
ways: two positions, two CSS classes, and on Assignments a second
``…and X more not shown.`` line below the table. Worse, the one
sentence they did share said two different things depending on
which pool had shrunk.

**Why the branches.** A table's visible rows can be short of the
whole roster for two unrelated reasons, and conflating them
misleads:

- a **filter** excluded rows — those rows are not withheld, they do
  not match, so "more not shown" would be a lie;
- a **cap** truncated the window — those rows *are* withheld, and
  the operator needs to know before they read the table as complete.

So the sentence names the pool its numerator was drawn from, says
``matching`` exactly when that pool is the filtered set rather than
the whole roster, and adds the withheld clause only when the cap
actually bit:

===========================  ==============================================
State                        Sentence
===========================  ==============================================
capped, unfiltered           ``Showing first 200 of 1,240 reviewers;
                             1,040 more not shown.``
capped, filtered             ``Showing first 500 of 900 matching
                             reviewers; 400 more not shown.``
filtered, under the cap      ``Showing 3 of 1,240 reviewers.``
unfiltered, under the cap    *(nothing — see below)*
===========================  ==============================================

The quiet case returns ``None`` rather than ``Showing 6 of 6``,
which is noise: a table showing everything needs no caption. That
rule predates this module (Segment 19I Item 4) and is preserved.
"""

from __future__ import annotations

__all__ = ["preview_count_line"]


def preview_count_line(
    *,
    shown: int,
    matching: int,
    total: int,
    noun: str,
) -> str | None:
    """Compose the count line for a preview table, or ``None``.

    ``shown`` is how many rows the cap window holds, ``matching``
    how many survived the filter, and ``total`` how many the
    session holds in all — so ``shown <= matching <= total``.
    ``noun`` is the plural thing being counted from the operator's
    point of view, which is not always the row's own type: the
    Invitations table is one row per reviewer and says
    ``reviewers``, and Responses says ``reviewees``.

    Returns ``None`` when the table shows everything there is,
    because a caption that says so is noise.
    """
    capped = shown < matching
    filtered = matching < total

    if not capped and not filtered:
        return None

    if not capped:
        # The filter narrowed the table but the window held it all.
        # ``total`` is the pool, so no ``matching`` and no withheld
        # clause — the excluded rows do not match, they are not
        # being kept back.
        return f"Showing {matching:,} of {total:,} {noun}."

    # The cap bit. Name the pool it truncated: the matching set when
    # a filter is active, the whole roster otherwise.
    pool = matching if filtered else total
    qualifier = "matching " if filtered else ""
    withheld = pool - shown
    return (
        f"Showing first {shown:,} of {pool:,} {qualifier}{noun}; "
        f"{withheld:,} more not shown."
    )

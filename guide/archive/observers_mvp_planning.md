# Observers — MVP planning history (archived 2026-06-02)

Historical record of the framing that led to the Observer
Collation MVP shipped 2026-06-02 (#1799 → #1806). Carved out
of `guide/observers.md` once the wiring was live and that
file slimmed to a current operating reference.

The current contract — storage shape, token design, where
the wiring stands, cohort-consumer routes — lives in
`guide/observers.md`. This file is for the *why*, not the
*what ships today*.

## Design reframe (2026-06-02)

### Two scenarios are real

**Scenario A — Universal observers** see the whole session
(department head, auditor, programme admin). The operator
already has Extract data + Zip-all bundles; a participant-
facing surface is mostly redundant. If a surface is wanted,
download-only is the cleanest shape.

**Scenario B — Partitioned observers** see one cohort (tutors
per tutorial group, mentors per cohort). This is the group
that genuinely benefits from a distinct observer role rather
than the operator emailing CSVs.

### Even Scenario B has two focuses

A partitioned observer might be monitoring **either**:

- **Responses about the partition** — what reviewers said
  about *the reviewees in this cohort*. (Tutor monitoring
  their tutees' feedback.)
- **Responses by the partition** — what *the reviewers in
  this cohort* wrote about others. (Peer-review class where
  reviewers are graded on the quality of their feedback.)

A cells-in-a-table surface would need a focus-switcher to
support both, with each switch landing on a differently-
shaped table. That's a lot of UI to maintain for one
participant role.

### Conclusion — observers = download-access role

All lines of reasoning point at the same conclusion:

> **Observers are participants other than the operator who
> get the ability to download a configured range of data
> about the session.**

The `/me/sessions/{id}/collation` surface should be, in the
first instance, a **download index** — a list of the data
the observer is entitled to, with per-file download links.
Not a render surface, not a cells-in-a-table view.

> **What actually shipped** — the surface is a *download
> index plus summary*: per-instrument 3-row tables
> (reviewer-side aggregates / reviewee-side aggregates /
> conditional download), not a bare file list. The
> aggregates give the observer enough at-a-glance signal
> that they often don't need to download; the download is
> the escape hatch for downstream analysis.

### What Raw vs Anonymized *operationalizes* as

A refinement to the existing 3 × 2 Band 3 chip grid: the
operator-facing labels stay, but Anonymized gets a concrete
shape that means more than "hide the identification cells":

| Mode | What it means in the downloaded data |
|---|---|
| **Raw** | Identification is the individual's name / email. The same identification the operator sees. |
| **Anonymized** | Identification is a **stable machine token** (e.g. `R-a3f8b2c1` for a reviewer, `E-9d4e7f10` for a reviewee). The token is consistent across rows and across reloads but doesn't disclose name / email. |
| **Summarized** | No per-individual rows — per-instrument aggregates only (mean / median / min / max / frequencies, the W16 primitives). |

This makes Anonymized meaningfully different from
Summarized: the consumer sees per-individual structure but
not per-individual identity. Useful when an observer needs
to count "how many distinct reviewers gave low scores"
without knowing who they are.

## MVP definition (2026-06-02)

The first cut of the observer feature was scoped:

### 1. Cohort assignment by tag matching

The operator can **assign each observer to a cohort** by
**tag matching** against the reviewer / reviewee rosters.
Match shape is per-observer, stored as JSON in a new
`observers.cohort_rule` column (see `guide/observers.md`
"Match-axis schema — decided" for the current contract).
The materialised cohort = the set of reviewers and/or
reviewees whose chosen field matches the observer's rule.

This lives on the Observers Setup page (operator side); the
observer themselves never sees the match config.

### 2. Observer surface — `/me/sessions/{id}/collation`

For each **visible instrument** the observer's cohort
participates in, the page renders **one table per instrument**
with three rows:

- **Row 1 — Reviewer stats.** Summary aggregates over the
  cohort's *reviewers* (mean / median / min / max for
  numerical; per-choice frequencies + percentages for List;
  total + average length for String). Same primitives as
  the existing W16 "Anonymized summaries" mode for reviewees.
- **Row 2 — Reviewee stats.** Same shape, computed over the
  cohort's *reviewees*. Two rows means the observer sees
  both the "what reviewers in my cohort were saying"
  perspective and the "what reviewers said about reviewees
  in my cohort" perspective without needing a focus
  switcher on the UI.
- **Row 3 — Download.** The third row carries a **download
  button flushed right in the last column** (rightmost
  column), per visible instrument. What gets downloaded
  depends on the instrument's Band 3 identification mode:
  - Band 3 = **Raw** → download row 3's button gives the
    operator-style identified per-instrument CSV (the
    cohort-scoped slice).
  - Band 3 = **Anonymized** → download gives the same CSV
    with names / emails replaced by stable tokens and the
    tag columns dropped (per the token-design decisions).
  - Band 3 = **Summarized** → no row-3 download; rows 1 + 2
    are the only data shape the operator's policy allows
    for this instrument.
- **CSV shape.** One CSV per instrument, following the
  existing **By-instrument** extract model
  (`app/services/extracts/by_instrument_extract.py`),
  scoped to the observer's cohort. Reuses the helper; the
  cohort filter shipped as an extra `row_filter` keyword
  parameter (per-row predicate, not the set-based
  `cohort_filter` originally sketched here — see PR #1804
  for the OR-correctness reasoning).

The page is a **download index plus summary** — not a full
cells-against-policy table. Rows 1 + 2 give the observer
enough at-a-glance signal that they often don't need to
download; row 3 is the escape hatch for downstream analysis.

## Implementation path (when the work resumed)

Sequencing the MVP defined above, as it actually shipped:

1. **Schema migration** — add `observers.cohort_rule`
   (`sa.JSON()`, nullable). Pydantic schema for the rule
   shape alongside. ✅ PR #1787.
2. **Cohort materialiser service** — given an observer + a
   session, evaluate `cohort_rule` against the reviewer +
   reviewee rosters and return the in-cohort reviewer ids +
   reviewee ids. Compute at request time; no junction
   table. ✅ PR #1800.
3. **Token helper** (`participant_token`) — pure function
   over `(session_id, role, individual_id) + salt`. No
   persistence. ✅ PR #1799.
4. **By-instrument extract — cohort filter parameter** —
   extend `serialize_by_instrument` with an optional row
   filter (predicate) + token swap for Anonymized
   identification. ✅ PR #1802 + #1804.
5. **`/me/sessions/{id}/collation` body** — per-instrument
   table: rows 1 + 2 carry the W16 aggregate primitives
   (`summarize_field`) scoped to the cohort's reviewers /
   reviewees; row 3 carries the conditional download
   button. One per visible instrument. ✅ PR #1803.
6. **Operator-side Observers Setup configurator** — UI for
   setting the per-observer cohort rule. ✅ PR #1789.
7. **Reshape the Band 3 observer row** — the 2026-06-02
   tightening (#1805 / #1806) restricts Observer / Session-
   ongoing to off / Anonymized summaries, leaving the full
   four-mode set for `after_release`. Per-row downloads
   only open once the response-release window does. ✅

The "Operator decoder" token widget on the Observers Setup
page (originally sketched alongside the other items) is
deferred — tracked in `guide/clean_up.md` item 15. The
`pair_context.*` left-side rules + cross-roster
`operand_tag` ops are also deferred (`guide/clean_up.md`
items 13 + 14).

## Implications for the existing operator surfaces (as drafted)

The pre-MVP sketch of how the new pieces would interact
with existing surfaces:

- **Band 3 visibility editor.** The 3 × 2 chip grid keeps
  its `observer` row — the Raw / Anonymized / Summarized
  pick that the MVP's row 3 download branches on. **What
  shipped:** the Observer row stays; the Session-ongoing
  cell tightened to off / Anonymized summaries only (#1805
  / #1806) once the surface was live and the use-case
  framing settled.
- **`/me/sessions/{id}/collation`.** Renders the per-
  instrument table, not a bare file list. The route gate
  stays (`require_observer_in_session`), the chrome stays.
- **Observers Setup page.** Adds the per-observer Cohort
  match rule editor. Concrete shape — a Band 1 Link 2-style
  multi-rule editor with AND/OR combinator — landed via
  the placeholder-then-wire ladder (#1772-#1782 placeholder,
  #1789 wire).

The pre-MVP "W17 + W5 (paused)" notes about retiring the
cross-reviewee table sketch are now moot — the surface
shipped per the framing above.

## Configurator lives on the Observers Setup page (as drafted)

The pre-MVP framing for *why* the cohort lives on the
Observers Setup page rather than Band 3:

- The Band 3 chip grid is a per-instrument × per-audience ×
  per-window cell-rendering matrix. It's the right shape for
  the identification mode (Raw / Anonymized / Summarized)
  but not for the per-observer cohort.
- An observer's cohort is **per-observer**, not
  per-instrument. The Band 3 grid has no per-observer axis.
- The Observers Setup page already has the operator looking at
  the roster, the tags, the status. Adding the cohort axis
  on the same page keeps the operator's workflow cohesive.

What shipped follows that framing exactly.

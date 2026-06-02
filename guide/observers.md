# Observers — participant role + collation surface

Standing notes for the **observer** participant role: who they
are, the data model, the surfaces, and the wiring tail that's
still to ship.

## Status

**Paused 2026-06-01, reframed 2026-06-02.** Operator-side
observer plumbing is live (roster Setup page, Quick Setup
slot, Extract Setup row, bundle inclusion, per-session enable
toggle, friendly-label resolver, visibility-policy column)
but the participant-facing collation surface
(`/me/sessions/{id}/collation`) renders only the placeholder
chrome — no body. The reframe below replaces the
collation-table sketch with a download-only model.

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

### Token design — decisions (2026-06-02)

- **Shape: short hash.** Opaque prefix-and-hex form like
  `R-a3f8b2c1` / `E-9d4e7f10`. Hides insertion order and
  roster size; readable enough to talk about in support
  cases.
- **Scope: per-session.** Same individual → same token
  across all consumers of the same session. Observers
  comparing notes can correlate; that's accepted because
  observers are operator-trusted in this product.
  Per-audience scrambled tokens would be a future tightening
  if needed.
- **Storage: compute, do not persist.** Hash inputs are
  `(session_id, role, individual_id) + salt`; ``Reviewer.id``
  / ``Reviewee.id`` already exist as session-local stable
  PKs. **No new table, no new column** for the token
  mechanism itself.

  ```python
  def participant_token(
      session_id: int, role: str, individual_id: int
  ) -> str:
      raw = f"{session_id}:{role}:{individual_id}"
      digest = hashlib.blake2b(raw.encode(), digest_size=4).hexdigest()
      prefix = role[0].upper()  # "R" / "E" / "O"
      return f"{prefix}-{digest}"
  ```

- **Operator decoder.** The hash is one-way; reverse a token
  by re-hashing every roster row and matching. Cheap at
  roster sizes ≤ 1000. Could surface as a "decode token"
  widget on the Observers Setup page (paste `R-a3f8b2c1`,
  get back name + email) without any persistence.
- **Anonymized hides the tags too.** Beyond the obvious
  partitioning fact (i.e. the cohort the observer was scoped
  to), tag columns drop from the rendered / downloaded
  Anonymized rows. The use scenario assumes tags narrow
  down to workable groups; they don't identify on their own,
  but combined with other data they could deanonymize.
  Operator's responsibility to set the cohort wide enough
  that the surviving tag isn't a single-person bucket.
- **Reviewee `/results` keeps the em-dash treatment.**
  Tokens are only useful when the consumer wants to run
  downstream analysis on multi-row data. A reviewee on their
  own `/results` page has one identity (themselves) and no
  analysis use case; dashes stay the right rendering for
  Anonymized there.

## MVP definition (2026-06-02)

The first cut of the observer feature is now scoped:

### 1. Cohort assignment by tag matching

The operator can **assign each observer to a cohort** by
**tag matching** against the reviewer / reviewee rosters.
Match shape is operator-configurable (decided when the work
opens — see the three options under "Match-axis open
question" below; lean is per-session pick), and the
materialised cohort = the set of reviewers and/or reviewees
whose chosen tag axis equals the observer's tag.

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
    tag columns dropped (per the token-design decisions
    above).
  - Band 3 = **Summarized** → no row-3 download; rows 1 + 2
    are the only data shape the operator's policy allows
    for this instrument.
- **CSV shape.** One CSV per instrument, following the
  existing **By-instrument** extract model
  (`app/services/extracts/by_instrument_extract.py`),
  scoped to the observer's cohort. Reuse the helper; pass
  the cohort filter as an extra argument.

The page is a **download index plus summary** — not a full
cells-against-policy table. Rows 1 + 2 give the observer
enough at-a-glance signal that they often don't need to
download; row 3 is the escape hatch for downstream analysis.

### Open: match-axis schema

- **Hardcoded** to `observer.tag_1 == reviewee.tag_1` (and
  the symmetric reviewer side). Zero schema, zero UI. The
  operator just has to ensure observer-tag values are drawn
  from the same vocabulary as the reviewee tag axis they
  want to match. Cheapest path; fine for the first cut.
- **Operator-picked** per session: one new column on
  `sessions` like `observer_match_field VARCHAR(32)` storing
  `"reviewee.tag_1"` / `"reviewee.tag_2"` / `"reviewer.tag_1"`
  / etc. Plus a small UI on the Observers Setup page (or on
  Session Edit Details) to pick the axis. Slight schema
  cost, much more flexible.
- **Operator-picked per observer**: a column on `observers`
  carrying the match-field choice for that row alone. Most
  flexible; per-observer focus axis becomes natural too
  (some observers watch reviewees, others watch reviewers).
  Largest schema + UI cost.

Lean direction TBD; the cheapest path keeps everything in
existing columns, and the richer path is one column away.

Combined with Band 3's identification mode pick, the matrix
becomes:

- **Cohort** (who's in scope) — defined per-observer on the
  Observers page (or, in the cheapest path, derived from
  the hardcoded `observer.tag_1` ↔ `reviewee.tag_1` match).
- **Identification** (Raw / Anonymized tokens / Summarized
  aggregates) — defined per-instrument on Band 3.

These two axes are orthogonal: the cohort says *which rows
are mine*, the Band 3 mode says *how identified are the
rows I get to see*.

### Configurator lives on the Observers Setup page

The right home for "what does observer X get to download" is
**a dedicated configurator on the Observers Setup page**, not
the Band 3 visibility table.

Reasons:

- The Band 3 chip grid is a per-instrument × per-audience ×
  per-window cell-rendering matrix. It's the right shape for
  the identification mode (Raw / Anonymized / Summarized)
  but not for the per-observer cohort.
- An observer's cohort is **per-observer**, not
  per-instrument. The Band 3 grid has no per-observer axis.
- The Observers Setup page already has the operator looking at
  the roster, the tags, the status. Adding the cohort axis
  (match-tag picker + focus picker) on the same page keeps
  the operator's workflow cohesive.

### Implications for the existing operator surfaces

- **Band 3 visibility editor.** The current 3 × 2 chip grid
  has an `observer` row. Once the new configurator lands,
  that row's role is unclear. Two options:
  (a) drop the observer row from Band 3 entirely (the per-
  instrument cell-render policy is reviewee-only);
  (b) keep it but as the "default mode" for the summarized
  aggregates the observer downloads — orthogonal to the
  per-observer scope.
- **`/me/sessions/{id}/collation`.** Renders the download
  index, not a cross-reviewee table. The route gate stays
  (`require_observer_in_session`), the chrome stays, the
  body becomes a list of files.
- **Observers Setup page.** Adds a per-observer
  configurator — likely a small "scope" cell or expandable
  row carrying: focus (reviewees / reviewers / both),
  partition (whole session / matched by tag), file kinds
  allowed (responses CSV / per-instrument CSVs / shaped
  CSVs / setup bundle / etc.). Concrete shape is a design
  call when this re-opens.
- **W17 + W5 (paused).** The cross-reviewee table sketch is
  retired. The replacement is the download-index +
  configurator above; the supporting service module if
  needed is a thin file-list builder rather than the
  cell-rendering `build_observer_collation_context`
  originally proposed.

## Implementation path (when the work resumes)

Sequencing the MVP defined above:

1. **Resolve the match-axis schema** (the three options in
   "Open: match-axis schema" above). Lean is per-session
   pick — one new column on `sessions`.
2. **Cohort materialiser service** — given an observer + a
   session, return the in-cohort reviewer ids + reviewee ids.
   Compute at request time; no junction table.
3. **Token helper** (`participant_token`) — pure function
   over `(session_id, role, individual_id)`. No persistence.
4. **By-instrument extract — cohort filter parameter** —
   extend `serialize_by_instrument` with an optional cohort
   filter (or a thin wrapper that applies it). Reuse the
   token helper to swap identification when Band 3 says
   Anonymized.
5. **`/me/sessions/{id}/collation` body** — per-instrument
   table: rows 1 + 2 carry the W16 aggregate primitives
   (`_summarize_field`) scoped to the cohort's reviewers /
   reviewees; row 3 carries the conditional download
   button. One per visible instrument.
6. **Operator-side Observers Setup configurator** — UI for
   setting the per-observer cohort tag value (and the per-
   session match axis once that decision lands). A small
   "decode token" widget alongside, for support cases.
7. **Reshape the Band 3 observer row** — the current 3 × 2
   chip grid's observer row stays as the Raw / Anonymized /
   Summarized pick that the MVP's row 3 download branches on.
   No retire / repurpose needed — it does exactly the job
   the MVP requires.

When that work scopes, fold this file into a
`segment_22_observers.md` plan and link from
`guide/todo_master.md`'s Upcoming list.

## Where the wiring stands

What's shipped (live in production):

- **Schema** — `observers` table, `observer.*` audit events,
  `sessions.observers_enabled` toggle.
- **Roster** — Setup-Observers page (CRUD + bulk + delete-all
  + Upload + Operator-actions row + Danger Zone) shipped
  W10 / PR #1706.
- **Quick Setup Observers slot** — Session Home + new-session
  form both upload a CSV with the same shape as the Setup
  page (W12 / PR #1754). Renders only when
  `observers_enabled` is on.
- **Extract Setup Observers row + bundle** — per-row CSV
  download (`observers.csv`) + inclusion in the Zip-all
  bundle, gated on the same toggle (W13 / PR #1755).
- **Per-instrument visibility policy** — operators can
  author Raw / Anonymized / Summarized for the `observer`
  audience on each instrument's Band 3 visibility editor
  (W15 + the per-window mode pair columns from S14).
- **`/me/sessions/{id}/collation` placeholder route** — page
  renders the reviewer-surface chrome with the caption
  "Observer view of the session"; gated on
  `require_observer_in_session` (W3 / P6, PR #1713). No
  body content yet.
- **Cross-role lobby support** — observers appear on
  `/me/` with the amber `observer` role pill if they're on
  any session's roster (W18, polish through #1715). Their
  role-navigator chip strip links to `/me/sessions/{id}/collation`.

## Paused work items (now scoped by the MVP above)

- **W17 — Observer collation surface body.** Reshape to the
  per-instrument table (rows 1 = reviewer stats, row 2 =
  reviewee stats, row 3 = conditional download button) per
  the MVP definition. The original cross-reviewee
  cell-rendering sketch retires.
- **W5 — `app/services/collation.py` service.** Two thin
  helpers: (a) cohort materialiser
  (`observer + session → reviewer_ids, reviewee_ids`); (b)
  per-instrument stats builder that reuses W16's
  `_summarize_field` over the cohort. The originally-sketched
  `build_observer_collation_context` shrinks to a thin
  page-shape composer.

## Cross-references

- `guide/archive/participant_model_upgrade.md` — design rationale +
  the full audience taxonomy (§3.1 observer scope, §7
  collation render shape).
- `guide/archive/participant_model_remainder.md` — outstanding
  participant-model items overall; observer-side items
  filed here once this stub took ownership.
- `spec/audience_and_identity_model.md` — authoritative
  audience taxonomy.
- `spec/setup_pages.md` — Observers Setup page contract.
- `app/services/visibility_policies.py::resolve_mode` —
  the resolver W17 calls.
- `app/web/views/_reviewee_results.py::_summarize_field` —
  the per-data-type aggregation primitives W5 will reuse.

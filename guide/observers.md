# Observers — participant role + collation surface

Operating reference for the **observer** participant role:
who they are, the storage shape that backs the cohort match
rule, the token design that backs the Anonymized download,
and the routes the consumer side talks to.

The MVP planning history (Design reframe, Implementation
path, "Implications for the existing operator surfaces"
sketch) lives in
`guide/archive/observers_mvp_planning.md` — useful for the
*why*, but not the source of truth for *what ships today*.

## Status

**MVP shipped 2026-06-02.** Operator-side plumbing was live
through the participant-model rollout; the consumer side —
cohort materialiser, per-instrument stats builder,
participant-token helper, by-instrument cohort filter, and
the collation surface body itself — landed in a five-PR
ladder (#1799 → #1803) plus three follow-up tightenings
(#1804 per-row cohort predicate + filename naming, #1805
Band 3 valid-mode tightening, #1806 chip-cycle tightening).

Today `/me/sessions/{id}/collation` renders the per-instrument
3-row table (reviewer-side aggregates / reviewee-side
aggregates / conditional CSV download), and
`.../collation/instruments/{instrument_id}.csv` streams the
cohort-scoped slice in whichever identification mode Band 3
authored.

Deferred items live in `guide/clean_up.md` (items 13-16) —
`pair_context.*` left-side rules, cross-roster `operand_tag`,
the operator-side decode-token widget, and a stats-row
cohort-scope review.

## Match-axis schema — decided (2026-06-02)

**Per-observer JSON column.** `observers.cohort_rule`:

```python
cohort_rule: Mapped[dict[str, Any] | None] = mapped_column(
    JSON, nullable=True
)
```

Follows the existing instrument-assignment-rule precedent
(`session_rule_sets.rules_json` — `sa.JSON()`, list of rule
dicts, typed in-memory shape in `app/schemas/rules.py`). The
Cohort match rule editor is multi-rule with an AND / OR
combinator from day one, so the storage shape is a wrapper —
not a bare predicate — mirroring Band 1 Link 2's idiom:

```json
{
  "combinator": "AND",
  "rules": [
    {"field": "reviewer.tag1", "op": "IS THE SAME AS", "operand_tag": "observer.email", "operand_value": ""},
    {"field": "reviewee.tag1", "op": "IS", "operand_tag": "", "operand_value": "math"}
  ]
}
```

- `combinator` — `"AND"` / `"OR"`; how the per-cell verdicts
  merge.
- Each `rules[]` entry:
  - `field` — canonical key from the editor's first dropdown
    (`reviewer.tag1` / `reviewer.tag2` / … / `reviewee.tag3` /
    `pair_context.tag1` …). Vocabulary in
    `ALLOWED_LEFT_FIELDS` (matches the assignment-engine
    field set, restricted to tag columns).
  - `op` — the UI label as-is: `"IS THE SAME AS"` /
    `"IS DIFFERENT FROM"` / `"IS"` / `"IS NOT"` / `"CONTAINS"` /
    `"DOES NOT CONTAIN"`. Engine-side translation happens at
    evaluation time (same Link 2 pattern).
  - `operand_tag` — canonical key from the second dropdown
    (`observer.name` / `observer.email` / `observer.tag1` or
    any roster attribute). Used by the two cross-attribute
    ops; empty string otherwise.
  - `operand_value` — literal string from the text input.
    Used by `IS` / `IS NOT` / `CONTAINS` / `DOES NOT CONTAIN`;
    empty string otherwise.

`NULL` cohort_rule = the operator hasn't authored anything
for this observer yet (distinct from a saved
`{"combinator": "AND", "rules": []}` which is explicit
"empty"). The materialiser and the per-row predicate both
treat a `NULL` rule as "no cohort scope" — the surface
shows the muted "No cohort is configured" message and the
CSV download 404s.

Pydantic validation lives in
`app/schemas/observer_cohort_rule.py` (`CohortRule` per cell,
`CohortRuleSet` for the wrapper); the editor reuses Band 1's
predicate vocabulary.

Combined with Band 3's identification mode pick, the matrix
is:

- **Cohort** (who's in scope) — defined per-observer on the
  Observers page via the `cohort_rule` JSON column.
- **Identification** (Raw / Anonymized tokens / Summarized
  aggregates) — defined per-instrument on Band 3. Observer
  Session-ongoing accepts only off or Anonymized summaries
  per the 2026-06-02 tightening (PR #1805 / #1806); per-row
  downloads open once `after_release` does.

These two axes are orthogonal: the cohort says *which rows
are mine*, the Band 3 mode says *how identified are the
rows I get to see*.

## Token design — decisions (2026-06-02)

Implementation in `app/services/participant_tokens.py`.

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
- **Storage: compute, do not persist.** Hash inputs are an
  env-level salt (`PARTICIPANT_TOKEN_SALT` — defaulted for
  local + tests) mixed with the session's `created_at` ISO
  timestamp, then `(role, individual_id)`. `Reviewer.id` /
  `Reviewee.id` already exist as session-local stable PKs.
  **No new table, no new column** for the token mechanism
  itself.
- **Operator decoder — `participant_tokens.csv`.** The hash
  is one-way; reverse a token by re-hashing every roster row
  and matching. Cheap at roster sizes ≤ 1000. Shipped as a
  CSV download from the Extract data tab's `Token keys` card
  (and the intro card's `Token keys` chip on the Zip-all
  bundle) rather than a paste-a-token widget — same lookup
  use case with no JS, gated on `observers_enabled`. Closes
  `guide/clean_up.md` item 15.
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
  (W15 + the per-window mode pair columns from S14). Since
  2026-06-02 the Session-ongoing slot is tightened to
  ``None`` / ``summarized`` only (#1805 / #1806).
- **Cross-role lobby support** — observers appear on
  `/me/` with the amber `observer` role pill if they're on
  any session's roster (W18, polish through #1715). Their
  role-navigator chip strip links to `/me/sessions/{id}/collation`.
- **Cohort match rule editor + persistence** —
  `observers.cohort_rule` JSON column (#1787) +
  `CohortRuleSet` validator + `observers_service.set_cohort_rule`
  writer + the `observer.cohort_rule_assigned` audit event
  (#1788) + the per-observer editor on the Observers Setup
  page (multi-rule + AND/OR combinator + cross-attribute /
  literal operands; #1789) + read-back into the editor on
  selection + the friendly summary in the table's Cohort
  column (#1790). View helpers live in
  ``app/web/views/_observers.py``.
- **W17 — Observer collation surface body** —
  `/me/sessions/{id}/collation` renders the per-instrument
  3-row table (Row 1 reviewer-side headcount badge / Row 2
  reviewee-side headcount badge / conditional download), one
  card per visible-to-observer instrument. Composes the
  cohort materialiser (#1800), the per-instrument stats builder
  (#1801), and the by-instrument extract's cohort filter +
  Anonymized token swap (#1802 + #1804). Cohort-empty and "no
  instruments visible right now" branches render their own
  muted-paragraph messages.
- **W5 — `app/services/collation.py`** + cohort materialiser
  (`app/services/observer_cohort.py`) shipped with #1800 +
  #1801, reformed to the partition model (clean_up item 16):
  ``materialize_cohort_assignments`` walks per-(observer,
  instrument) assignments via the per-row predicate
  ``assignment_matches_cohort`` and returns the in-cohort
  assignment id set + the two side-distinct counts.
  ``build_cohort_stats_for_instrument`` runs one aggregate
  against the pool — Row 1 + Row 2 share the same
  ``field_cells`` + ``response_count``; only the
  ``distinct_count`` headcount badge differs per row. The CSV
  download uses the same ``assignment_matches_cohort``
  predicate (PR #1804) so surface stats + CSV stay in sync.
  Per-instrument stats reuse W16's `summarize_field` (promoted
  from underscore-private in the same PR).
- **Token helper + Anonymized identification** — shipped via
  ``app/services/participant_tokens.py`` (#1799) +
  ``serialize_by_instrument(identification="anonymized")``
  (#1802). Anonymized downloads swap reviewer / reviewee
  names for per-session opaque tokens and blank emails + tag
  columns so the only identifier is the token.

## Cohort-consumer routes

- ``GET /me/sessions/{id}/collation`` — observer surface body.
- ``GET /me/sessions/{id}/collation/instruments/{instrument_id}.csv``
  — per-instrument CSV download. Filename pattern is
  ``<observer_email>_<instrument_slug>[_anon].csv``; the
  ``_anon`` suffix only applies in Anonymized mode.
  Identification mode follows Band 3 (`raw` / `anonymized`);
  `summarized` returns 404 (no per-row download is offered
  when the operator picked the aggregate view).

## Cross-references

- `guide/archive/observers_mvp_planning.md` — Design reframe
  + MVP definition + Implementation path + Implications.
  Historical context; not the source of truth for what
  ships today.
- `guide/archive/participant_model_upgrade.md` — design
  rationale + the full audience taxonomy (§3.1 observer
  scope, §7 collation render shape).
- `guide/archive/participant_model_remainder.md` —
  outstanding participant-model items overall.
- `guide/clean_up.md` — all four observer-side deferrals
  (items 13, 14, 15, 16) closed.
- `spec/audience_and_identity_model.md` — authoritative
  audience taxonomy.
- `spec/setup_pages.md` — Observers Setup page contract
  including the Cohort match rule editor.
- `spec/visibility_policy.md` — Band 3 modes, including
  the tightened Observer / Session-ongoing constraint.
- `app/services/visibility_policies.py::resolve_mode` —
  the resolver the collation surface calls per instrument.
- `app/web/views/_reviewee_results.py::summarize_field` —
  the per-data-type aggregation primitives the stats rows
  reuse.

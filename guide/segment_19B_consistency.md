# Segment 19B — Consistency remediation

> **Started 2026-08-19.** The code-level sibling of Segment 19A
> (documentation hygiene). Where 19A keeps `spec/` and `docs/`
> current, 19B keeps the **code** internally consistent — it works
> through the drift catalogued in `guide/consistency_audit.md`.

## Charter

The 2026-08-19 consistency audit (`guide/consistency_audit.md`) swept
four seams — service / route / template / view-adapter — for places
where Review Robin Web does the **same conceptual thing in more than
one way**: the same business operation invoked through divergent
service APIs, the same HTTP action exposed under divergent
conventions, the same derived value computed twice, the same user
gesture presented through divergent affordances. It found **28
findings** (6 High / 10 Medium / the rest Low), each anchored to
`path:line`, with a batched remediation order.

19B lands that remediation in reviewable slices, in the audit's
recommended order. Each slice cites the audit's finding ids so the
catalogue stays the index of record.

## Slices

### Item 1 — S1–S5: service-layer identity + dedup — ✅ done 2026-08-19

The first, highest-value batch — the service-layer findings, which
were the only ones carrying a genuine correctness risk (auth-adjacent
identity comparison) rather than pure maintenance drift.

- **S1 — one instrument label.** Deleted the divergent
  `app/services/validation.py::_instrument_label` (it fell back to the
  internal `name`); `validation.py` now imports the canonical
  `app.services.instruments._instrument_label`, whose fallback is
  `Instrument_{id}`. An instrument with no `short_label` now reads the
  same across validation messages, audit copy, and operator UI.
  *(Test `tests/unit/test_validation_per_instrument.py` updated: its
  `_add_instrument` helper now sets `short_label`, matching how
  production instruments actually acquire an operator-facing label.)*

- **S2 / S3 / S4 — one email-identity home.** New
  `app/services/email_identity.py` holds:
  - `EMAIL_RE` — the email-shape regex, previously copied verbatim in
    five modules (participants / reviewers / reviewees / observers /
    csv_imports).
  - `looks_like_email(value)` — the "is this a well-formed email?"
    predicate, previously split between a strict `fullmatch` (the
    surface-reachability gate) and a `"@" in value` heuristic (import
    time).
  - `normalize_email(value)` — `strip().casefold()`, the canonical
    case-insensitive comparison key.

  Every identity-match site now folds through `normalize_email`:
  the roster uniqueness gates (`reviewers`/`reviewees`/`observers`
  `_email_taken` / `_identifier_taken`, converted from SQL
  `func.lower` to a session-bounded in-Python scan so the fold matches
  the access gates), the participant access gates (`app/web/deps.py`),
  the cross-role lobby (`routes_reviewer/_shared.py::build_role_chips`,
  whose three role branches now use one convention instead of mixing
  SQL `lower` with Python `casefold`), the Validate-page duplicate
  checks, the CSV importers + relationships CSV match, the
  self-review classifier, the session-rehydrate + responses-import
  matchers, and the rule engine. `str.casefold` (not `str.lower`) is
  the Unicode-correct fold, so write-time uniqueness and read-time
  access can no longer disagree.

  *Deliberate scope note:* the **global** `users`-table lookup
  (`app/services/users.py`) stays on SQL `func.lower` — it can't load
  the whole table into Python, and it doesn't participate in the
  per-session roster write-vs-gate hazard S2 is about.

- **S5 — one bulk status-flip.** New
  `app/services/roster_bulk.py::bulk_set_status` replaces the four
  byte-identical `_bulk_set_status` copies in reviewers / reviewees /
  observers / relationships; each caller now supplies only what
  genuinely differs (model, status normaliser, `*OperationError`
  class, entity noun).

  Also folded in the S8 doc-fix (the `create_reviewer` docstring
  claimed a "case-sensitive" duplicate check that was always
  case-insensitive).

  Verification: full suite green (2,680 passed, 17 skipped); ruff
  clean. No schema/migration change. Behaviour change is limited to
  the casefold-vs-lower distinction (identical for ASCII; casefold is
  the more correct fold for the rare non-ASCII address) and the S1
  label fallback.

## Still open

The remaining audit findings, in the audit's batched order:

- **Service dedup tail (S6, S7)** — the status-normaliser /
  active-predicate duplication and the "count responses for a field
  id" query triplicate. Pure maintenance; fold in when next touching
  those files.
- **Route-convention sweep (R1–R11).** Two design decisions to settle
  **first**: (a) is the extract-data REST/JSON/PATCH style a blessed
  AJAX exception or should it + the instrument AJAX endpoints converge
  on one contract (R1 + R4)? (b) the `delete` vs `remove` verb rule
  (R6). Then the mechanical nits and the two-URL consolidations.
- **UI-vocabulary sweep (U1–U8).** Spec-backed and largely mechanical:
  Save→Secondary, banner Cancel→`.btn alert`, one delete-confirm
  mechanism (U3 carries real safety weight — do it deliberately), drop
  the no-op `.btn primary` token, one "Clear" label, one abandon-edits
  verb. Refresh `spec/operator_button_audit.md` in the same slice.
- **View-adapter dedup (V1–V6).** `instrument_heading` reimplemented
  inline (V1 — pairs naturally with the S1/V4 instrument-label work),
  the progress-pill macro (V2), the user-display-label property (V3),
  and the smaller predicate/pluralization dedup (V5, V6).

## Hard dependencies

- **None.** Item 1 shipped standalone. The route + UI decisions
  (R1 / R6) gate their own slices but nothing else.

## Doc impact

- `guide/consistency_audit.md` is the finding index — cite finding ids
  from each slice; leave the audit itself as the frozen catalogue.
- `guide/todo_master.md` carries the at-a-glance 19B entry.
- `docs/status.md` gets a timeline row per shipped slice.

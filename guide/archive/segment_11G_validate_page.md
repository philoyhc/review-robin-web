# Segment 11G — Validate page

Stub. Implementation plan for the Operations-row **Validate** tab
(`/operator/sessions/{id}/validate`). Today the page ships on v2
(per Segment 11A) but as a thin read-only list of
`ValidationIssue` rows — useful, but the operator has to leave
the page to act on every issue. 11G makes the page work for its
job: **help the operator find and fix errors so the session can
activate cleanly.**

The catalog framing: `guide/todo_master.md` "Upcoming" item 3 —
"polish per the latest operator-UI direction: clearer error /
warning / info pillification, lifecycle-aware framing, deeper
integration with the Next Action card on Home."

The functional contract is in
**`spec/operator_ui_concept.md:244-252`** (page placement,
read-only, severity pills + per-issue list) and the lifecycle-
state copy in **`spec/session_home.md:136-146`** (which Next
Action verbs the page sits behind). This guide adds the page's
*body shape* — what the read-only deep-dive actually shows now
that there's a whole page to work with.

## Status

Planning. Sized as **4 PRs** in dependency order. PR A and PR B
are independently shippable; PR C and PR D both build on the
rule-registry refactor PR B introduces.

1. **PR A — Page layout + Setup readiness matrix + lifecycle
   framing.** Replace the thin issue list body with a structured
   layout: a top **Readiness summary card**, the existing issue
   list (still using the existing partial), and lifecycle-aware
   intro copy. No service-layer changes.
2. **PR B — Rule registry refactor + per-issue fix-link
   plumbing.** Refactor `validate_session_setup` into a
   registered-rule list; each rule emits issues that carry a
   `fix_url` and (where it makes sense) a `fix_anchor`. The
   issue list partial picks up the new "Fix on Reviewers
   Setup ↗" affordances.
3. **PR C — Severity filter chips + group-level summary +
   per-rule "why" disclosure.** Quality-of-life work on top of
   PR B's registry: filter the list to errors-only / warnings-
   only / info-only via chips that flip a `?severity=` query
   param; per-source group headers carry their own count
   summary; each rule gets an optional `<details>` "Why this
   check exists" disclosure.
4. **PR D — Activate-warns detour from Home's Next Action
   card.** When the Next Action card on Home offers Activate on
   a `validated` session that still has warnings, clicking
   Activate 303s to `/validate?activate=1` rather than firing
   the activate POST inline. The Validate page surfaces a
   prominent confirmation banner ("This session has 2
   warnings. Acknowledge and activate, or cancel to address
   them first.") with `.btn.alert` Cancel + `.btn.danger-solid`
   Acknowledge per `spec/domain_assumptions.md`. Removes the
   `acknowledge_warnings` checkbox from the Next Action card
   itself.

## Why this scope — find and fix

The current page tells the operator *what* is wrong. 11G makes
it tell them **what is wrong, where to fix it, and how big the
problem is**:

- **Find.** A Setup-readiness matrix gives the operator
  at-a-glance "here's the state of every setup area" before
  they even read the issue list. Severity filter chips collapse
  long lists. Group-level counts let the operator triage
  ("Reviewers has 0 errors but 3 warnings — leave it for now;
  Instruments has 1 error — start there.")
- **Fix.** Every issue carries a deep-link to the Setup page
  that owns it, with a fragment that scrolls the operator to
  the offending row where possible. The lifecycle framing tells
  them what state they're in and what's next ("All errors are
  clear. Activate from the Next Action card on Session Home.")
- **Acknowledge.** When activation needs operator
  acknowledgment of warnings, the ceremony moves out of the
  cramped Next Action card on Home and onto a full-width
  confirmation banner here, where the warnings themselves are
  visible inline rather than summarised in one line.

## Scope

In:

### Page layout (PR A)

Replace `session_validate.html`'s thin body with a structured
layout. Cards stack DOM-order (mobile) and pair into the
`.bottom-grid` two-column treatment on desktop:

1. **Readiness summary card (top, full-width).** New card. The
   page's at-a-glance verdict and severity counts:
   - **Verdict line.** Bold, colour-coded:
     - "Ready to activate." (`accent-green`) when zero errors.
     - "Has 3 errors." (`accent-red`) when errors exist.
     - "Ready to activate with 2 warnings." (`accent-amber`)
       when zero errors but warnings.
   - **Severity counts row.** Three pills, always rendered
     (zero counts inclusive — operators learn the row's
     position):
     `pill-error N · pill-empty M · pill-count K` for
     error / warning / info.
   - **Last validated.** Today validation runs live on every
     GET. Render "Validated just now" — sets expectations that
     re-running is free and refresh-driven.
   - **Lifecycle-aware secondary line.**
     - `draft`, errors clear: "Activate from the Next Action
       card on Session Home."
     - `draft`, errors present: "Resolve the errors below
       before activating."
     - `validated`: "Setup is validated. Activate from Session
       Home." (+ warning-acknowledgment line if warnings exist
       and PR D has shipped — see below.)
     - `ready`: "This session is live. Setup is locked.
       Revert to draft on Session Home to make changes."
     - `closed`: "Session closed on {date}. This is a snapshot
       of the final setup state."

2. **Setup-coverage matrix (top, full-width, sits below the
   readiness summary).** A small read-only table mirroring the
   Setup row of the chrome:
   ```
   Session name          ✓
   Session code          ✓
   Reviewers             8
   Reviewees             13
   Instruments           2  · response fields configured
   Assignments           104  · full-matrix
   Email template        Default (no overrides)
   Help contact          Set
   ```
   - Each row carries a passive count or a check / cross
     glyph; rows with issues attached get a quiet inline
     `pill-error N` / `pill-empty N` next to the count, linked
     to the matching anchor in the issue list below
     (`#issue-source-reviewers`).
   - The matrix is not a duplicate of the issue list — it's
     the **inventory**, the issue list is the **diagnostic**.
     The matrix is useful even when the issue list is empty:
     it's the operator's "here is the shape of my session"
     reference card.
   - View-shape adapter: `views.build_setup_coverage(session,
     issues)` packages the matrix rows from the existing
     count helpers (`csv_imports.existing_reviewer_count`,
     `existing_reviewee_count`,
     `existing_assignment_count`, plus a small new
     `instruments.session_field_count(session)` helper if
     it doesn't exist yet) and merges in the issue counts
     per source.

3. **Issue list (full-width, below the matrix).** Keeps the
   existing `validation_results.html` partial as its body;
   PR B and PR C extend the partial in place rather than
   replacing it.

4. **Activate-confirmation banner (conditional, top of body
   above the readiness summary; PR D only).** When the page
   is reached via `?activate=1`, this banner renders first and
   auto-scrolls into view per the `banner-scroll-target`
   convention. See PR D for shape.

### Rule registry refactor (PR B)

The current `validate_session_setup` is one ~120-line function.
PR B refactors it into a small registered-rule list so each
rule's metadata is introspectable from the page:

```python
@dataclass(frozen=True)
class ValidationRule:
    key: str                     # "reviewers.duplicate_email"
    source: str                  # "reviewers"
    severity: Severity
    why: str                     # one-paragraph rationale,
                                 # surfaced via PR C's <details>
    fix_url: Callable[[ReviewSession], str]
    fix_anchor: Callable[[ReviewSession, ValidationIssue],
                         str | None] = lambda *_: None
    check: Callable[[Session, ReviewSession],
                    Iterable[ValidationIssue]]
```

`validate_session_setup` becomes:
```python
def validate_session_setup(db, session) -> list[ValidationIssue]:
    issues = []
    for rule in REGISTERED_RULES:
        for issue in rule.check(db, session):
            issue.fix_url = rule.fix_url(session)
            issue.fix_anchor = rule.fix_anchor(session, issue)
            issue.rule_key = rule.key
            issues.append(issue)
    return issues
```

Rule list, mirroring today's checks and adding a few cheap
extensions:

| `key` | `source` | `severity` | `fix_url` |
|---|---|---|---|
| `session.no_name` | session | error | `/operator/sessions/{id}/edit` |
| `session.no_code` | session | error | `/operator/sessions/{id}/edit` |
| `reviewers.empty` | reviewers | error | `/operator/sessions/{id}/reviewers` |
| `reviewers.duplicate_email` | reviewers | error | `/operator/sessions/{id}/reviewers` (anchor `#reviewer-row-{id}` per duplicate) |
| `reviewees.empty` | reviewees | error | `/operator/sessions/{id}/reviewees` |
| `reviewees.duplicate_id` | reviewees | error | `/operator/sessions/{id}/reviewees` (anchor as above) |
| `instruments.no_fields` | instruments | error | `/operator/sessions/{id}/instruments#instrument-{id}` |
| `assignments.no_mode` | assignments | warning | `/operator/sessions/{id}/assignments` |
| `email_template.no_help_contact` | email_template | info | `/operator/sessions/{id}/edit` (new — flags "no help contact set; reviewers will see the placeholder") |
| `instruments.no_display_fields` | instruments | warning | `/operator/sessions/{id}/instruments#instrument-{id}` (new — instrument has response fields but no display fields, reviewer pages will be sparse) |

The two new rules are cheap (read-only checks against existing
columns) and surface real footguns operators have hit;
intentionally `info` / `warning` not `error` so they don't
block activation.

The `fix_anchor` returns the per-issue scroll target where it
makes sense — "Row 5: duplicate email 'foo@bar'" gets an
anchor at the row, not just the page. Setup pages today carry
`id="reviewer-row-{id}"` / `id="reviewee-row-{id}"` /
`id="instrument-{id}"` anchors per their tables; PR B
audits each link target and adds the anchor where missing.

Service-layer behaviour preserved: `list[ValidationIssue]` is
still the return type, `Severity` enum unchanged, the
`csv_imports` helpers that emit `ValidationIssue` are
untouched (they use the schema directly and aren't part of the
session-setup rule set).

### Issue partial extensions (PR B)

`operator/partials/validation_results.html` extends per-issue
markup:
- Each `<li>` gains an `id="issue-{rule_key}-{n}"` so the URL
  fragment can scroll to a specific issue.
- A "Fix on {Setup page name} ↗" anchor on each issue,
  rendered right-aligned within the `<li>`. The link target
  is `issue.fix_url + (issue.fix_anchor or '')`. The trailing
  arrow is a `↗` literal (the same convention the chrome
  uses for "leaves this page" links).
- Each per-source group header (`<h3>`) gets an
  `id="issue-source-{source}"` so the readiness matrix can
  link directly to the section.

### Severity filter chips + group-level summary (PR C)

Above the per-source groups in the issue list, a row of three
filter chips:
```
All issues (8)  [ Errors only (3) ]  [ Warnings only (4) ]  [ Info (1) ]
```
- Implemented as anchor links flipping a `?severity=` query
  param (`?severity=error` / `warning` / `info`; absent =
  all). No JS — server-side filter, page reload, fragment
  preserved.
- Currently-active chip carries `aria-current="page"` and a
  visual outline.
- The "Errors only (3)" count reflects what *would render* if
  clicked, not the total — so the operator can see at a
  glance how many of each severity exist.
- Per-source group headers get a small inline count summary
  that respects the filter: "Reviewers (2 errors, 1 warning)
  — show all 3" or "Reviewers (2 errors)" when filtered.

### Per-rule "why this check" disclosure (PR C)

Each `<li>` gains a `<details>` with `<summary>` "Why this
check?" expanding to the rule's `why` paragraph. Examples:

- `reviewers.duplicate_email`: "Reviewer email is the join key
  the invitation flow uses. Duplicates would cause the second
  reviewer's invite to overwrite the first, and Activate
  would fail loudly. Required to be unique."
- `assignments.no_mode`: "An active session with no assignment
  mode means reviewers see an empty review surface and have
  nothing to do. Generate assignments before activating, or
  proceed knowing reviewers will see no work to complete."
- `email_template.no_help_contact`: "Reviewer-facing emails
  include a 'Questions? Contact …' line that falls back to a
  generic placeholder when help contact is unset. Setting one
  improves the reviewer experience but isn't required."

Default-collapsed; operator opens it the first time they hit a
rule they don't understand. The `<details>` element is native;
no JS.

### Activate-warns detour (PR D)

Today, when a `validated` session has warnings, the Next Action
card on Home renders an `acknowledge_warnings` checkbox inline
above the Activate button. Two problems:
- The card is half-width; warning text in the card itself is
  cramped and tends to be summarised to "Acknowledge warnings
  and activate" with no detail of what's being acknowledged.
- The ceremony lives in two places: the Validate page lists
  the warnings; the Home card asks for acknowledgment without
  showing them.

PR D moves the acknowledgment to Validate:

1. **Next Action card on Home** when state is `validated` and
   warnings exist:
   - Primary button: "Activate Session"
   - Click → 303 to `/operator/sessions/{id}/validate?activate=1`
     (no POST yet; the activate POST happens from the Validate
     page after acknowledgment).
   - The `acknowledge_warnings` checkbox is **removed** from
     this card.
   - Warning count surfaces as a small line under the primary
     button: "2 warnings — review on Validate before
     activating."
2. **Validate page when reached via `?activate=1`** (must be
   `validated` lifecycle; otherwise redirect to the page
   without the param). At the top of the body, above the
   readiness summary, an inline confirmation banner per
   `spec/domain_assumptions.md`:
   ```
   ┌──────────────────────────────────────────────────────┐
   │ ⚠ Acknowledge warnings to activate                   │
   │                                                      │
   │ This session has 2 warnings. Activating will start   │
   │ the live review with these conditions:               │
   │   • No assignment mode set — reviewers will see an   │
   │     empty surface.                                   │
   │   • Instrument 'Final Review' has no display fields. │
   │                                                      │
   │            [ Cancel ]  [ Acknowledge and activate ]  │
   └──────────────────────────────────────────────────────┘
   ```
   - `.banner.banner-warning` per spec assumption convention,
     with `banner-scroll-target` for auto-scroll.
   - Cancel (`.btn.alert`) links to `/validate` (clean URL),
     no acknowledgment, no activate.
   - Acknowledge-and-activate (`.btn.danger-solid`) submits
     to `POST /operator/sessions/{id}/activate` with
     `acknowledge_warnings=true`. Same POST handler the Home
     card used to call directly.
3. **Validated session with no warnings**: Activate from Home
   stays direct (POST without the detour). The detour fires
   only when warnings need acknowledgment.
4. **Validated session with errors** (somehow validated but
   re-validation surfaced new errors — possible if data
   shifted between validations): the detour banner becomes a
   `.banner.banner-error` ("Errors appeared since this session
   was validated. Resolve them and re-validate.") with Cancel
   only; acknowledge-and-activate is suppressed.

The activate-with-warnings POST handler today already accepts
`acknowledge_warnings=true`; PR D doesn't change the service
layer, only the UI ceremony around the POST.

Out (deferred):

- **New validation rules** beyond the two cheap additions in
  PR B. Cross-entity rules ("assignments reference deleted
  reviewers", "reviewer X has no assignments") are catalogued
  but each is its own scope. Each maps to one new
  `ValidationRule` registration in the registry — no plan-
  level guidance needed.
- **Persisting validation snapshots.** Today the page runs
  validation live on every GET; that's cheap (small queries,
  no I/O beyond the DB) and matches the spec's "Validation
  never mutates" guarantee. A persisted snapshot makes sense
  only if validation grows expensive enough to cache; not now.
- **Auto-fix affordances.** "Generate assignments" inline on
  the `assignments.no_mode` warning would duplicate the
  Assignments Setup page's primary action. Stick to deep-
  links; let the Setup pages own the fix UX.
- **Validation history / audit log.** Each validation run is
  ephemeral; we don't audit reads. If "see the last validation
  run before this re-validation flipped X warning to Y" ever
  becomes a need, that's a Segment 12 (audit retention)
  concern.
- **Reviewer-by-reviewer drill-in** ("which reviewers have
  zero assignments?"). That's Operations / Monitoring's job,
  not pre-flight Validate.
- **Batch issue-resolution.** "Fix all duplicate emails by
  keeping the first." Out — destructive bulk mutations belong
  on the Setup pages with their own confirmation chrome.

## Proposed PR sequence

### PR A — Page layout + Setup-coverage matrix + lifecycle framing

**Goal.** A useful page even before the rule refactor lands.
The readiness summary, the inventory matrix, and the
lifecycle-aware intro all surface from existing primitives.

- Replace the body of `session_validate.html` with the new
  three-card layout (readiness summary → setup-coverage
  matrix → existing issue list partial).
- New `views.build_validate_context(db, session)` adapter
  returning the verdict, severity counts, last-validated
  marker, lifecycle copy variant, and the setup-coverage
  rows. Reuses `validate_session_setup` verbatim and the
  existing count helpers.
- New CSS class `.card.readiness-summary` for the verdict
  card; the inline severity-counts row reuses the existing
  `.pill-{severity}` palette.
- Lifecycle copy lookup table in
  `views.validate_lifecycle_copy(session_status, has_errors,
  has_warnings)` — pure function, easy to unit-test.
- Tests:
  - Each lifecycle state renders the right secondary line.
  - Verdict line colour-codes correctly across error /
    warning / clean cases.
  - Setup-coverage matrix renders correct counts and links
    each row to the right issue-list anchor when issues
    exist for that source.
  - Empty-issues case renders "Ready to activate" verdict
    and the matrix without per-row issue counts.

### PR B — Rule registry + per-issue fix-link plumbing

**Goal.** Every issue carries a "fix on …" deep-link. Service-
layer is now extensible without re-editing one big function.

- New `ValidationRule` dataclass + `REGISTERED_RULES` list in
  `app/services/validation.py`. `validate_session_setup`
  rewrites to iterate the registry; service-layer signature
  unchanged (still returns `list[ValidationIssue]`).
- Migrate today's seven checks one-for-one into the registry,
  each with its `fix_url` / `fix_anchor` / `why` strings.
- Add the two new rules: `email_template.no_help_contact`
  (info) and `instruments.no_display_fields` (warning).
- Add `fix_url` / `fix_anchor` / `rule_key` fields to
  `ValidationIssue` (Pydantic model — defaults to None for
  back-compat; `csv_imports`-emitted issues continue to omit
  them, which the partial handles by suppressing the "Fix"
  link).
- Audit Setup-page templates for missing row-anchor `id`s and
  add them where the registry's `fix_anchor` calls expect
  them. Reviewers and reviewees tables already have
  `#reviewer-row-{id}` / `#reviewee-row-{id}`; instruments
  page already has `#instrument-{id}` per Segment 10D. No
  template changes expected; verify.
- Extend `operator/partials/validation_results.html`:
  - `<li>` carries `id="issue-{rule_key}-{n}"`.
  - Right-aligned "Fix on {label} ↗" anchor when
    `issue.fix_url` is set.
  - Per-source `<h3>` carries `id="issue-source-{source}"`.
- Tests:
  - Every rule in `REGISTERED_RULES` produces issues whose
    `fix_url` resolves to a real route (test by dispatching
    against the FastAPI app's URL map).
  - Per-issue anchor IDs are unique across a fully-populated
    session.
  - Duplicate-email issue's `fix_anchor` points at the row
    of the duplicate (not the page top).
  - The two new rules fire on the right shapes
    (`no_help_contact` when help-contact is null;
    `no_display_fields` when an instrument has response
    fields but no display fields).

### PR C — Severity filter chips + group counts + "Why" disclosure

**Goal.** Triage support for big issue lists; rule rationale
in-line for self-service.

- Filter chips above the `.card.issues` body, four anchors
  with `?severity=` query-param. Active chip styled per
  spec (visual outline + `aria-current="page"`).
- View adapter PR A introduced extends to honour
  `?severity=` and emit pre-filtered issue list + per-source
  filtered counts.
- Per-source group `<h3>` gains an inline count summary that
  respects the filter.
- Each rule's `why` paragraph surfaces inside a default-
  collapsed `<details>` per `<li>`.
- Tests:
  - `?severity=error` filters the list to errors and
    updates per-source counts.
  - `?severity=` (empty) renders all.
  - `<details>` elements default-collapsed; toggling them is
    a client-only concern (no test coverage needed).

### PR D — Activate-warns detour from Home

**Goal.** Move the warning-acknowledgment ceremony out of the
cramped Next Action card and onto Validate, where the warnings
are visible.

- Remove the `acknowledge_warnings` checkbox from the
  Next Action card on Home (`session_detail.html`'s
  `validated`-state branch). Replace with the small
  warning-count line under the primary button.
- Change the Activate button on the Next Action card from a
  POST submit (when warnings exist) to a 303-redirect anchor
  to `/validate?activate=1`. The no-warnings path keeps the
  direct POST.
- New rendering branch in the Validate page: when
  `?activate=1` and lifecycle is `validated`, render the
  `.banner.banner-warning` activate-confirmation banner at
  the top with the inline list of warnings + Cancel +
  Acknowledge-and-activate buttons.
- New rendering branch when `?activate=1` and there are
  errors: `.banner.banner-error` with Cancel only.
- Acknowledge-and-activate POST hits the existing activate
  handler with `acknowledge_warnings=true`; on success 303
  to Session Home with no flash banner (the lifecycle pill
  flipping to `ready` is the canonical signal, per the
  reviewer-surface convention adopted in 11J).
- Cancel returns to `/validate` (clean URL); auto-scroll
  doesn't fire on the dismissed page since no
  `banner-scroll-target` exists.
- Tests:
  - `validated` session with warnings: Home Activate click
    → 303 → Validate `?activate=1` renders the banner.
  - Acknowledge-and-activate POST flips the session to
    `ready`, audit event still fires.
  - Cancel from the banner returns to clean URL with no
    state change.
  - `validated` session with no warnings: Home Activate
    click POSTs directly (no detour).
  - Errors-since-last-validation case: banner is the error
    variant, acknowledge button is suppressed.
  - Ineligible-state guard: `?activate=1` on a `draft` /
    `ready` / `closed` session redirects to `/validate`
    without the param (no banner).

## Implementation pointers

- **Live validation on GET** is the right default; don't add
  a snapshot table. The current `validate_session_setup` is
  a handful of cheap selects; benchmark on a 1000-reviewer /
  1000-reviewee fixture before deciding otherwise.
- **Rule keys are stable.** Once a rule's `key` is in
  production audit logs (when 11K's audit-event detail
  schema lands and Activate's `acknowledge_warnings` event
  carries the rule keys), changing the key is a migration.
  Pick names that read well in audit detail — dotted-source
  prefix matches the existing audit-event convention.
- **`ValidationIssue` schema bump.** Adding `fix_url`,
  `fix_anchor`, `rule_key` is additive; `csv_imports.py`
  call sites that don't set them get the defaults. No
  Pydantic v1/v2 surprises here — already on Pydantic 2.
- **Banner Cancel-return.** PR D's banner uses the standard
  `?` (clean URL) Cancel-return pattern from
  `spec/domain_assumptions.md`; the banner has a unique
  `id="activate-confirm-banner"` so the
  `banner-scroll-target` script in `base.html` brings it
  into view.
- **Setup-page anchor audit.** PR B should grep each Setup
  page template for the row anchors the rule registry
  promises. Today's three known ones (reviewer-row,
  reviewee-row, instrument) are present per Segment 10D's
  rebuild; verify rather than trust.
- **Don't overload the page with affordances.** The "find
  and fix" framing pulls in tempting features (bulk fix,
  inline rule muting, "ignore for now" toggles). Resist.
  This page is a diagnostic; mutations stay on the Setup
  pages.

## Out of scope (cross-references)

- **Audit-event `detail` schema convention** — Segment 11K.
  When 11K lands, the Activate-with-warnings audit event
  picks up `{"rule_keys": ["assignments.no_mode", …]}` so
  the audit log records exactly which warnings the operator
  acknowledged. PR D ships with whatever shape the audit
  event has today; the detail-schema upgrade is 11K's job.
- **Cross-entity validation rules** beyond what 11G ships
  (assignment-references-deleted-reviewer, reviewer-with-no-
  assignments, instrument-with-no-assignments). Each is one
  rule registration per the registry shape PR B introduces.
- **Real-time validation as the operator edits Setup pages.**
  The page re-runs validation on every visit; live feedback
  on Setup pages themselves is an existing concern owned by
  those pages' own per-form validation.
- **Validate page on the reviewer surface side** — pre-submit
  required-field gates. That's `routes_reviewer.submit_review`'s
  responsibility (the missing-required card from 11D
  follow-on) and shares no code with this page.
- **Run Session card on Home.** Out — Home has no "Run
  Session" card today; the Next Action card carries every
  lifecycle button. If a future Home redesign introduces a
  separate Run Session card, PR D's flow re-attaches there
  trivially.

## Test impact

- New `tests/integration/test_session_validate_page.py`
  covering each PR's surface. Lifecycle-state intro copy,
  setup-coverage matrix, fix-link rendering, severity
  filter, "Why" disclosure presence, activate-detour banner.
- New `tests/unit/test_validation_rules.py` covering the
  registry: every `ValidationRule` instance has a non-empty
  `key`, `why`, and a `fix_url` callable that returns a
  resolvable URL; rule keys are unique within the registry.
- Existing `tests/unit/test_validation.py` (assuming it
  exists; otherwise gain it) keeps its shape — the
  service-layer return type is unchanged, so the rule-by-
  rule tests already exercise `validate_session_setup`.
- One new fixture: a session in each lifecycle state +
  combinations of (clean, has-warnings-only, has-errors,
  has-errors-and-warnings) for the matrix tests. Live in
  `tests/conftest.py` if reusable across the file.

## Doc impact

- `guide/todo_master.md` — move 11G from **Upcoming** to
  **Done** once PR D ships; cross-reference 11K (audit
  detail upgrade for the Activate event) and the deferred
  cross-entity rules.
- `docs/status.md` — timeline entry per PR.
- `spec/operator_ui_concept.md:244-252` — extend the
  `/validate` entry past the current three bullets to name
  the readiness summary, setup-coverage matrix, severity
  filter, and the activate-detour from Home. Describe the
  page in terms of the four cards rather than "deep-dive of
  every issue."
- `spec/session_home.md:136-146` — the `validated`-with-
  warnings row's "Run Session" card flow updates: the
  `acknowledge_warnings` checkbox moves out, the warning
  count becomes a passive line, the Activate click 303s
  to `/validate?activate=1` instead of POSTing directly.
- No new spec doc — this guide doubles as the spec for the
  page's body shape until the layout proves stable enough
  to promote into `operator_ui_concept.md`.

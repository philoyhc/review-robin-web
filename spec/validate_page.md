# Validate page — spec

**The find-and-fix readiness surface.** Inventories every setup
issue the session has and offers per-issue "Fix on X ↗" deep-
links that drop the operator onto the specific row that
triggered the check.

The Validate page sits in the Operations row and is
the canonical pre-activation gate. The operator iterates on
errors here until the readiness report passes; the Activate
button on the Workflow card then flips `validated → ready`.

Cross-references:

- **`app/services/validation.py`** — rule registry +
  orchestrator (`validate_session_setup`,
  `REGISTERED_RULES`).
- **`app/schemas/validation.py`** — `ValidationIssue` +
  `Severity` enum.
- **`app/web/views/_validate.py`** — view-shape adapters
  (`build_validate_context`, `SetupCoverageRow`,
  `SeverityChip`, `IssueSourceGroup`).
- **`app/web/templates/operator/session_validate.html`** +
  **`partials/validation_results.html`** — rendering.
- **`spec/lifecycle.md`** — how validation feeds the
  `mark_validated` / `activate_session` transitions.
- **`spec/operator_ui_concept.md`** §5 — page taxonomy
  (Operations row).

---

## 1. Page identity

| Field | Value |
|---|---|
| Page name | Validate |
| URL | `GET /operator/sessions/{id}/validate` |
| Template | `app/web/templates/operator/session_validate.html` |
| Operations row position | #2 — after Assignments, before Invitations. (Previews sat between them until it retired at 19Q Item 1.) |
| Audience | Operator (`require_session_operator`). |

The page is reachable in every lifecycle state. It's read-only
(no mutating routes), so it doesn't carry a lock card; it just
inventories the current session against the rule set.

**Query params:**

- `?severity=<error|warning|info>` — severity-chip filter. The
  setup-coverage grid always renders the full picture; only the
  issue list below is filtered.
- `?activate=1` — Activate-warns detour. The Workflow card's
  Activate button 303s here when warnings exist; the page
  renders an inline "Acknowledge and activate" banner instead
  of the bare issue list. On ineligible states (not `validated`)
  or when there is nothing to acknowledge, the route drops the
  param and 303s to the clean URL.

---


**Documented in the Guide.** `/guide`'s **Check readiness** section
(`guide.html`, section key `validate`) tells an operator what this page
is for, that its issues carry "Fix on … ↗" deep links, that warnings are
acknowledged at activation rather than cleared here, and that the body
below the Workflow card is read-only. Those four claims are this page's
contract restated for an operator — change one here and that section is
the second place to edit.

## 2. Page body (top to bottom)

### 2.0 Chrome + Workflow card

Like every Operations-row page, the Validate page renders the
two-row session chrome (top-nav + setup-status strip) followed by
the full-width **Workflow card** (`next_action_card.html`, per
`spec/workflow_card.md`) at the top of the body, above the
Activate banner. The Workflow card carries the Prepare / Activate
lifecycle actions; the Validate page body below it is the
read-only readiness inventory.

### 2.1 Activate banner (state-conditional)

Renders **only** when the operator arrives via `?activate=1`.
Two variants:

- **Warnings present** — `banner-warning` with copy:
  *"Acknowledge warnings to activate"* + the list of warning
  messages. Carries an "Acknowledge and activate" POST button
  (sends `acknowledge_warnings=true` to `/activate`) and a
  Cancel link back to the page without `?activate=1`.
- **Errors present** — `banner-error` with copy:
  *"Errors appeared since this session was validated"* +
  the list of error messages. Carries a Cancel link only;
  errors are a hard block.

Both variants carry `banner-scroll-target` + the
`activate-confirm-banner` id so the auto-scroll script jumps
to them on load.

### 2.2 Setup coverage card

A 4-column grid of `{label, status, error-count pill, warning-
count pill}` rows summarising the session's setup state at a
glance. Each row's anchor link (`#issue-source-{source}`) jumps
to the matching group in the Issues card below.

Coverage rows are derived from rules + session state by
`_setup_coverage_rows` in `app/web/views/_validate.py`. The
canonical row order:

One row per `label` emitted by `_setup_coverage_rows`, in the
order it emits them:

1. **Session name** — the name, or `—`. Carries the
   `session`-source issue counts.
2. **Session code** — the code, or `—`. No counts of its own.
3. **Reviewers** — count, with the `reviewers`-source counts.
4. **Reviewees** — count, with the `reviewees`-source counts.
5. **Observers** — count, with the `observers`-source counts.
   **Only when `observers_enabled`**: a session with observers
   switched off has no roster to summarise, and a permanently
   blank row is one the operator learns to skip. Eight rows
   without it, nine with.
6. **Instruments** — count, or `—`.
7. **Assignments** — `{count} · {mode}`, or the count, or `—`.
8. **Email template** — *Custom overrides* / *Default (no
   overrides)*. No counts.
9. **Help contact** — *Set* / `—`. No source, so it never
   badges and never links.

**Three rows this list used to name do not exist.** It opened
with a composite *"Session metadata (name / code / description
/ deadline / help contact)"* where the code emits **Session
name** and **Session code** as separate rows and nothing for
description or deadline; and it ended with **Relationships**
and an **Activation readiness** row carrying `_verdict(...)`.
`_verdict` is computed and reaches
`ValidateContext.verdict_line` / `.verdict_class`, but no
template reads either — the verdict the operator sees is the
lifecycle copy above the grid. Enumerated against the code at
19Q Item 7's close, after a first pass retired two of the
three and left the composite standing, which then duplicated
help contact.

Every issue `source` that can raise an error has a row here, or
its findings badge nothing on the grid — see §7 step 5. Observers
became such a source at 19Q Item 7 and gained this row with it.

Each row's status string is a short prose summary (e.g.
*"5 reviewers"*, *"2 instruments, 3 + 4 fields"*) — the
operator scans the grid for the at-a-glance picture, then
drills into Issues for diagnostics.

### 2.3 Severity filter chip strip

Renders only when at least one issue exists. Four chips:

| Chip | URL state | Counts |
|---|---|---|
| All | no `?severity=` param (default) | total |
| Errors | `?severity=error` | error count |
| Warnings | `?severity=warning` | warning count |
| Info | `?severity=info` | info count |

The active chip carries `aria-current="page"` + `.active`
styling. Clicking a chip is a GET — server-side filter, no JS
state.

### 2.4 Issues card

Groups issues by `(gate, source)` — an `<h2 id="gate-{gate}">`
*"Setup gate"* / *"Operations gate"* heading (setup always first),
and within it an `<h3>` per source (e.g. `session`, `reviewers`,
`instruments`) with an inline `{count_summary}` aside. A source
whose rules span both gates appears under each, so the source
headings are not unique; the `id="issue-source-{source}"` anchor
renders on the **first** appearance only, keeping the Setup
coverage matrix's deep-link target stable. Gates come from
`gate_for_rule_key` in `app/web/views/_validate.py`; within a
gate, source order follows `REGISTERED_RULES`.

Each issue renders:

- **Severity pill** (`pill-error` / `pill-warning` / `pill-info`).
- **Row number** (when the issue points at a specific roster
  row, e.g. *"Row 12: …"*).
- **Field name** in `<code>` (when the issue points at a column,
  e.g. `<code>email</code>`).
- **Message** — the rule's per-row diagnostic.
- **"Why this check?"** disclosure (`<details>`) — expands to
  reveal the rule's `why` paragraph, sourced from
  `ValidationRule.why`.
- **"Fix on {fix_page_label} ↗"** deep-link — anchored at
  `{fix_url}{fix_anchor or ""}`. Drops the operator onto the
  Setup page with the offending row scrolled into view via the
  anchor (e.g. `#reviewer-row-7` on the Reviewers page).

Each `<li>` carries `id="issue-{rule_key}-{loop.index}"` so
inbound links from the Setup coverage card or external bookmarks
can target a specific issue.

When the severity filter is active and matches nothing, the
Issues card renders an empty-state line: *"No issues match the
current severity filter."*

---

## 3. The rule registry

`REGISTERED_RULES: tuple[ValidationRule, ...]` in
`app/services/validation.py`. One entry per check, evaluated in
declared order. Adding a rule is a single registry edit.

### 3.1 `ValidationRule` shape

```python
@dataclass(frozen=True)
class ValidationRule:
    key: str            # Stable identifier, e.g. "reviewers.duplicate_email".
    source: str         # Group label for the Issues card, e.g. "reviewers".
    severity: Severity  # error / warning / info.
    why: str            # One-paragraph rationale shown in the disclosure.
    fix_url: Callable[[ReviewSession], str]
                        # Builds the absolute URL to the page that fixes it.
    fix_page_label: str # Button copy, e.g. "Edit reviewers".
    check: Callable[[Session, ReviewSession, ValidationInputs],
                    Iterable[ValidationIssue]]
                        # Yields the actual diagnostics.
```

The `check` function yields raw `ValidationIssue` instances; the
orchestrator stamps `rule_key`, `fix_url`, `fix_page_label`, and
`why` onto each one. Per-issue `fix_anchor` is set inside the
`check` (e.g. the duplicate-email rule sets the anchor to the
first duplicate row's `#reviewer-row-{id}`).

**`ValidationInputs` is the third argument, and a check reads what
it needs from there rather than querying for it** (19R Item 5). It
carries what more than one check loads — the instrument list, the
three rosters, the per-instrument response-field /
visible-response-field / display-field presence, and the included
counts per instrument — plus `active_reviewees`, the roster filtered
in Python. Checks each deciding independently what "the session's
instruments" means is how two of them come to disagree after someone
edits one; one load per run is what stops that. A load only one check
makes stays in that check.

It is built **once per report run and never cached** — a check must
not see a roster older than the request that asked. `db` stays in
the signature for the loads a single rule still owns.

### 3.2 The registered rules

| `key` | `source` | Severity | What it catches |
|---|---|---|---|
| `session.no_name` | session | error | Missing `ReviewSession.name`. |
| `session.no_code` | session | error | Missing `ReviewSession.code`. |
| `reviewers.empty` | reviewers | error | Zero reviewer rows. |
| `reviewers.duplicate_email` | reviewers | error | Same email appears on 2+ reviewer rows. |
| `reviewees.empty` | reviewees | error | Zero reviewee rows. |
| `reviewees.duplicate_id` | reviewees | error | Same `email_or_identifier` appears on 2+ reviewee rows. |
| `reviewees.unreachable_for_results` | reviewees | warning | At least one active reviewee has a non-email `email_or_identifier` — those reviewees can never reach `/me/sessions/{id}/results` because identity matching requires an email-shaped identifier. One umbrella issue carrying the count; Fix link deep-links to the Reviewees Setup page. Severity is warning (non-blocking), gate is `setup`. |
| `observers.duplicate_email` | observers | error | Same email appears on 2+ observer rows. `uq_observer_session_email` refuses a second row on write — observers carry the only DB-level uniqueness of the three rosters — so this reports a row predating the constraint, or one written by a path around the services. The page's job is to report, and observers were the one roster it had nothing to report with (19Q Item 7). |
| `reviewers.cross_roster_identity` | reviewers | error | A reviewer's email is held in another roster under a *different* name. |
| `reviewees.cross_roster_identity` | reviewees | error | As above, for a reviewee. |
| `observers.cross_roster_identity` | observers | error | As above, for an observer. |
| `instruments.no_fields` | instruments | error | At least one instrument has zero response fields. |
| `instruments.no_rule_pinned` | instruments | warning | **Inert by design** — raises no findings, and must not be revived as written: a NULL `rule_set_id` is never "not set up", because every instrument defaults to the synthetic Full Matrix on untouched Band 1. `instruments.no_visible_response_fields` below covers the readiness gap. The key stays registered so audit history remains addressable. |
| `instruments.no_visible_response_fields` | instruments | warning | An instrument has zero `visible=True` `InstrumentResponseField` rows — reviewers would see an empty page even though assignments exist. Toggle a response-field chip in Band 2 to make a field visible. |
| `assignments.no_included_pairs` | assignments | warning | Sum of `included_count` across every instrument is zero — never generated, or every row deactivated. |
| `assignments.reviewer_missing` | assignments | warning | A reviewer has no assignment rows at all (pinned rule excluded them, or they joined the roster after the last Generate). |
| `assignments.reviewer_missing_for_instrument` | assignments | warning | A reviewer is present on some instruments but missing on others — a partial review surface on a multi-instrument session. |
| `assignments.instrument_empty` | assignments | warning | An instrument has zero assignment rows — invisible to every reviewer. |
| `email_template.no_help_contact` | email_template | info | Session has no `help_contact` set (advisory; reviewer-facing emails still send). |
| `instruments.no_display_fields` | instruments | warning | At least one instrument has zero display fields beyond the always-on identity column. |
| `instruments.stale_generated` | instruments | warning | One per instrument whose materialised rows have fallen out of step with what the engine would produce now — the pinned rule changed, or the rosters or relationships moved after Generate. The verdict is the engine's own reconcile diff, and since 19R Item 2 it may be served from a stamped cache rather than recomputed on the spot — it still agrees with what Generate would do, under the conditions `spec/assignments.md` § *Staleness* states: the stamp covers every input the diff reads, and Generate writes the fresh verdict through. A never-generated instrument is **not** flagged here: a run would insert its whole fan-out, and an always-on warning is one the operator learns to ignore — the `assignments.*` empty rules carry that case. |
| `instruments.zero_included` | instruments | warning | Instrument has `generated_count > 0` but `included_count == 0` (operator bulk-deactivated rows). |

#### Cross-roster identity — three rules, one generator

One mailbox under two names is one person recorded twice, and
nothing downstream can tell which spelling is right: results,
collation and the reviewer's own surface all key on the email.
Reviewer / reviewee overlap itself is legitimate and stays so — a
self-review is exactly that — as long as the name agrees.

The write paths refuse such a pair
(`csv_imports.cross_table_identity_conflict`, from every
create / edit service and every roster importer); these rules
find the pairs a session already held when they started refusing.

- **Both sides are reported**, each under its own roster with its
  own row anchor, because neither row is known to be the wrong
  one. Hence three registered rules over one generator rather
  than one session-wide rule: a `ValidationRule` carries a single
  `fix_url` for every issue it emits, so one rule would send two
  of every three findings to the wrong roster page.
- **A within-roster pair is not reported here.** Two reviewers on
  one mailbox is `reviewers.duplicate_email`'s finding alone; one
  problem must not read as two under one heading.
- **A row that cannot disagree is skipped** —
  `csv_imports.is_comparable_identity`, the same predicate the
  write guards apply: an identifier with no `@` (an anonymous
  reviewee handle is not a mailbox) and a row with no name
  (`Observer.display_name` is nullable, and a missing name is not
  a different one).
- **Comparison** is `normalize_email` on the mailbox and exact on
  the stored name. Exact means case-sensitive; it is never
  whitespace-sensitive, because every path trims a name before
  storing it.

Severity guidance:

- **`error`** — blocks `mark_validated` and `activate_session`.
- **`warning`** — blocks `activate_session` unless the operator
  passes `acknowledge_warnings=true`. Doesn't block
  `mark_validated`.
- **`info`** — advisory only. Never blocks; flagged for the
  operator's awareness.

---

## 4. `ValidationIssue` schema

```python
class ValidationIssue(BaseModel):
    severity: Severity
    source: str
    row_number: int | None = None
    field: str | None = None
    message: str
    detail: dict[str, Any] | None = None
    # Stamped by the orchestrator from the rule's metadata:
    rule_key: str | None = None
    fix_url: str | None = None
    fix_anchor: str | None = None
    fix_page_label: str | None = None
    why: str | None = None
```

`severity` is the `Severity` enum (`error` / `warning` / `info`).
`is_blocking` is a derived predicate — `severity is
Severity.error`.

The five fix-link fields (`rule_key`, `fix_url`, `fix_anchor`,
`fix_page_label`, `why`) default to `None` so issues emitted
outside the registry (e.g. `csv_imports`-time validation
errors) render without a Fix link. Issues emitted from
`REGISTERED_RULES` always carry the full set.

---

## 5. Orchestrator + view adapter

### 5.1 Service — `validate_session_setup(db, session)`

Runs every registered rule against the session. Returns
`list[ValidationIssue]` in registry order (which becomes the
canonical issue order for grouping + display).

The orchestrator builds one `ValidationInputs` (§3.1) before the
loop and hands it to every rule, so the inputs more than one check
needs are read once per run. Each rule's
`check(db, session, inputs)` yields raw issues; the orchestrator
stamps `rule_key`, `fix_url`, `fix_page_label`, and `why` from the
rule metadata, preserving any per-issue `fix_anchor` the check set
itself.

**The report never issues one of its own queries twice**, and
`tests/integration/test_readiness_report_cost.py` enforces it. The
one exception is the reload `assignments.staleness_by_instrument`
performs inside its own engine, pinned there by a second test.

**The Validate page builds the report once.** The route runs the
orchestrator for its own issue table and passes the result to
`views.build_workflow_card_context(..., issues=...)` rather than
letting the card run it again; every other page that hosts the card
leaves that argument `None` and the builder runs it itself. The
hand-off is per request, never a cache.

### 5.2 View adapter — `build_validate_context(...)`

Lives in `app/web/views/_validate.py`. Takes the issue list +
the current `?severity=` filter + the session, returns a
`ValidateContext` dataclass with:

- `setup_coverage` — `list[SetupCoverageRow]` for the 4-col grid.
- `severity_chips` — `list[SeverityChip]` with per-chip count
  and `is_active`.
- `issue_groups` — `list[IssueSourceGroup]` of issues
  post-filter, grouped by `source` in registry order.
- `filtered_issue_count` — total after the severity filter.
- `error_count` / `warning_count` / `info_count` — pre-filter
  totals used by the chip strip.
- `severity_filter` — the current `?severity=` value (or
  `"all"`).

The chip-strip card hides itself when all three counts are 0
(no issues at all → no filter needed). The Issues card hides
when filtered count is 0 AND no filter is active.

### 5.3 Lifecycle integration

The Validate page is read-only — it doesn't write any state. The
two lifecycle gates that consume its output are:

| Gate | Service | Behaviour |
|---|---|---|
| `?validated=1` on Session Home GET | `mark_validated(...)` (per `spec/lifecycle.md` §2.1) | Flips `draft → validated` iff `len(errors) == 0`. Warnings + info are advisory at this step. |
| `POST /activate` | `activate_session(...)` (per `spec/lifecycle.md` §2.4) | Flips `validated → ready` iff `len(errors) == 0` and (no warnings OR `acknowledge_warnings=true`). |

The activate-warns detour banner (§2.1) is the only operator
surface for the `acknowledge_warnings=true` POST.

---

## 6. Deep-link anchors

`fix_url` is built by the rule's `fix_url(session)` callable;
`fix_anchor` is set per-issue by the `check` function when
the issue points at a specific row. Conventions:

| Source | Anchor pattern | Set by check |
|---|---|---|
| `reviewers` (row-specific) | `#reviewer-row-{id}` | `_check_reviewers_duplicate_email` |
| `reviewees` (row-specific) | `#reviewee-row-{id}` | `_check_reviewees_duplicate_id` |
| `observers` (row-specific) | `#observer-row-{id}` | `_check_observers_duplicate_email` |
| any roster (row-specific) | that roster's row anchor | `_cross_roster_identity_issues`, via the three `*.cross_roster_identity` rules |
| `instruments` (row-specific) | `#instrument-{id}` | per-rule |
| Whole-page rules | empty anchor — `fix_url` lands the operator on the right page without scrolling. |

The Setup pages render the matching anchor ids on their preview-
table `<tr>` elements (e.g. `id="reviewer-row-{id}"`), so the
fragment-jump lands the operator on the offending row. The
auto-scroll script doesn't fire on the destination page — the
natural fragment-jump handles it.

---

## 7. Adding a new rule

1. Write a `_check_<source>_<predicate>` function in
   `app/services/validation.py`. Signature:
   `(db: Session, review_session: ReviewSession, inputs: ValidationInputs)
   -> Iterable[ValidationIssue]`.
   Yield zero or more `ValidationIssue` instances. **Read the
   rosters, the instruments and the per-instrument field presence
   from `inputs`** (§3.1) — a check that loads one of those itself
   fails the no-duplicate guard in
   `tests/integration/test_readiness_report_cost.py`. If the rule
   needs something no other check needs, load it in the check; if a
   second check later needs the same thing, move it into
   `load_validation_inputs`.
2. If the issue points at a specific row, set
   `issue.fix_anchor = "#<page>-row-{id}"` and make sure the
   target page renders the matching `<tr id="...">`.
3. Add a `ValidationRule(...)` entry to `REGISTERED_RULES` with the
   stable `key`, group `source`, `severity`, `why` paragraph,
   `fix_url` callable, and `fix_page_label`. **Position is a
   contract** — §2.4 derives within-gate source order from it — so put
   the rule where it belongs among its siblings rather than at the end
   if those differ.
4. **Add its row to §3.2's table at the same position.**
   `tests/unit/test_doc_conventions.py` derives that table's `key`
   column from `REGISTERED_RULES` and fails on order as well as on
   membership, so a rule registered without a row fails CI. The check
   exists because a rule appended to the table where the code inserted
   it stayed wrong from W8 through a corpus sweep and a `spec-writer`
   pass (19R Item 6).
5. Add a unit test that constructs a session matching the rule's
   trigger and asserts the rule yields exactly one issue with
   the expected `rule_key`, severity, and (where applicable)
   `fix_anchor`.
6. Add the rule to the per-source row in `_setup_coverage_rows`
   if the operator needs to see it on the at-a-glance grid.

`rule_key` is the stable identifier — once shipped, treat it as
a public surface. Renaming requires a migration (audit-event
references would otherwise dangle).

---

## 8. Out of scope (deliberate)

- **Reviewer-side response validation** — handled inline by the
  reviewer surface's per-field constraints (`min` / `max` /
  `step`, `setCustomValidity`); not part of the Validate page.
- **Cross-session validation** — rules consider one session at a
  time. Cross-session checks would belong to the system-admin
  surface (`app/web/routes_operator/_sys_admin.py`), not to this
  registry.
- **Validation-time fixes** — the page only reports. Operators
  fix issues on the Setup pages the deep-links target; the
  Validate page itself doesn't carry edit affordances.
- **Custom rules from operators** — the registry is a code-side
  construct. Operators can't define their own rules.
- **Validation history** — each run is read-only and stateless;
  the page doesn't persist a snapshot. Audit events
  (`session.validated`) record the run's outcome.

---

## 9. Implementation principles

1. **Rules are data.** Each check is a function + a registry
   entry. Adding, removing, or reordering rules is a registry
   edit. The orchestrator doesn't hard-code rule names.

2. **Stable `rule_key`s.** Once a rule ships, treat its key as a
   public surface. The audit log references it; renaming is a
   migration.

3. **`fix_url` + `fix_anchor` are the deep-link contract.** Setup
   pages must render the matching `<tr id="...">` anchors. The
   contract lives in both directions; breaking the anchor
   convention on a Setup page silently breaks the Fix link.

4. **`why` is for operators, not developers.** Write the rationale
   in operator-readable prose. Don't reference internal column
   names or service paths; reference the operator surface.

5. **Severity is meaningful.** `error` blocks activation; `warning`
   requires acknowledgment; `info` is advisory. Choose
   deliberately — over-using `warning` makes the
   acknowledgment ceremony noisy and trains the operator to
   click through.

6. **Read-only surface.** The Validate page never writes. Every
   mutation lives on a Setup page reached via the Fix deep-link;
   the page itself is purely diagnostic.

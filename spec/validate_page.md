# Validate page — spec

**The find-and-fix readiness surface.** Inventories every setup
issue the session has and offers per-issue "Fix on X ↗" deep-
links that drop the operator onto the specific row that
triggered the check. Shipped in Segment 11G.

The Validate page sits in the Operations row (post-15D) and is
the canonical pre-activation gate. The operator iterates on
errors here until the readiness report passes; the Activate
button on Session Home then flips `validated → ready`.

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
| Operations row position | #2 (between Validate and Previews — actually #1; Previews is #3 post-15D Assignments insert) |
| Audience | Operator (`require_session_operator`). |

The page is reachable in every lifecycle state. It's read-only
(no mutating routes), so it doesn't carry a lock card; it just
inventories the current session against the rule set.

**Query params:**

- `?severity=<error|warning|info>` — severity-chip filter. The
  setup-coverage grid always renders the full picture; only the
  issue list below is filtered.
- `?activate=1` — Activate-warns detour. Session Home's
  Activate button 303s here when warnings exist; the page
  renders an inline "Acknowledge and activate" banner instead
  of the bare issue list.

---

## 2. Page body (top to bottom)

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

1. Session metadata (name / code / description / deadline /
   help contact).
2. Reviewers (count + duplicate-email count).
3. Reviewees (count + duplicate-id count).
4. Relationships (count, optional).
5. Instruments (count + per-instrument field count).
6. Assignments (mode + count).
7. Email template (default + overrides).
8. Activation readiness (overall verdict from
   `_verdict(error_count, warning_count)`).

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

Groups issues by `source` (e.g. `session`, `reviewers`,
`instruments`), one group heading per source with an inline
`{count_summary}` aside. Each issue renders:

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
    check: Callable[[Session, ReviewSession], Iterable[ValidationIssue]]
                        # Yields the actual diagnostics.
```

The `check` function yields raw `ValidationIssue` instances; the
orchestrator stamps `rule_key`, `fix_url`, `fix_page_label`, and
`why` onto each one. Per-issue `fix_anchor` is set inside the
`check` (e.g. the duplicate-email rule sets the anchor to the
first duplicate row's `#reviewer-row-{id}`).

### 3.2 Current rules (10 registered)

| `key` | `source` | Severity | What it catches |
|---|---|---|---|
| `session.no_name` | session | error | Missing `ReviewSession.name`. |
| `session.no_code` | session | error | Missing `ReviewSession.code`. |
| `reviewers.empty` | reviewers | error | Zero reviewer rows. |
| `reviewers.duplicate_email` | reviewers | error | Same email appears on 2+ reviewer rows. |
| `reviewees.empty` | reviewees | error | Zero reviewee rows. |
| `reviewees.duplicate_id` | reviewees | error | Same `email_or_identifier` appears on 2+ reviewee rows. |
| `instruments.no_fields` | instruments | error | At least one instrument has zero response fields. |
| `assignments.no_mode` | assignments | error | `assignment_mode` not set (no rule-based generation has run, no manual upload). |
| `email_template.no_help_contact` | email_template | info | Session has no `help_contact` set (advisory; reviewer-facing emails still send). |
| `instruments.no_display_fields` | instruments | warning | At least one instrument has zero display fields beyond the always-on identity column. |

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
outside the registry (e.g. legacy `csv_imports`-time validation
errors) render without a Fix link. Issues emitted from
`REGISTERED_RULES` always carry the full set.

---

## 5. Orchestrator + view adapter

### 5.1 Service — `validate_session_setup(db, session)`

Runs every registered rule against the session. Returns
`list[ValidationIssue]` in registry order (which becomes the
canonical issue order for grouping + display).

Each rule's `check(db, session)` yields raw issues; the
orchestrator stamps `rule_key`, `fix_url`, `fix_page_label`,
and `why` from the rule metadata, preserving any per-issue
`fix_anchor` the check set itself.

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
   `(db: Session, review_session: ReviewSession) -> Iterable[ValidationIssue]`.
   Yield zero or more `ValidationIssue` instances.
2. If the issue points at a specific row, set
   `issue.fix_anchor = "#<page>-row-{id}"` and make sure the
   target page renders the matching `<tr id="...">`.
3. Append a `ValidationRule(...)` entry to `REGISTERED_RULES`
   with the stable `key`, group `source`, `severity`, `why`
   paragraph, `fix_url` callable, and `fix_page_label`.
4. Add a unit test that constructs a session matching the rule's
   trigger and asserts the rule yields exactly one issue with
   the expected `rule_key`, severity, and (where applicable)
   `fix_anchor`.
5. Add the rule to the per-source row in `_setup_coverage_rows`
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
  time. A future "system admin" surface (Segment 16) might add
  cross-session checks.
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

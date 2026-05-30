# Review Robin Web — Functional Specification

> **Technology-neutral functional contract.** This document
> describes **what** Review Robin Web (RRW) is meant to do, in
> user- and concept-level terms — not **how** it is built. It
> supersedes the pre-implementation draft archived at
> `guide/archive/functional_spec.md` (retired 2026-05-11), which
> read as a forward-looking "destination" rather than a working
> contract.
>
> Implementation details (URLs, code modules, data types, frameworks)
> live in the per-page / per-subsystem specs alongside this file,
> and in `docs/status.md` for ship-state. Cross-references are
> noted in [§19 Reading guide](#19-reading-guide).
>
> **Currency.** Aligned with the system as of 2026-05-22. The
> functional contract is stable; ship-state may move ahead.

---

## Table of contents

1. [Purpose and framing](#1-purpose-and-framing)
2. [Functional goals](#2-functional-goals)
3. [Non-goals](#3-non-goals)
4. [User roles](#4-user-roles)
5. [Core concepts](#5-core-concepts)
6. [Session lifecycle](#6-session-lifecycle)
7. [Identity and authentication](#7-identity-and-authentication)
8. [Per-session metadata and settings](#8-per-session-metadata-and-settings)
9. [Operator workflows](#9-operator-workflows)
10. [Reviewer experience](#10-reviewer-experience)
11. [Invitations and email](#11-invitations-and-email)
12. [Data export](#12-data-export)
13. [Validation](#13-validation)
14. [Reconciling regeneration](#14-reconciling-regeneration)
15. [Audit and logging](#15-audit-and-logging)
16. [Retention, archive, and deletion](#16-retention-archive-and-deletion)
17. [Permissions and access control](#17-permissions-and-access-control)
18. [Glossary](#18-glossary)
19. [Reading guide](#19-reading-guide)

---

## 1. Purpose and framing

Review Robin Web is a system for **configuring, distributing,
collecting, monitoring, and exporting structured review data**
across multiple participants in a single review cycle.

A *review cycle* (called a **session**) is the unit of work.
Within a session, an operator defines a roster of **reviewers**
(the people who give feedback) and **reviewees** (the people who
receive it), then configures one or more **instruments** (review
forms) and an **assignment** matrix that maps reviewers to
reviewees per instrument. The system invites the reviewers, hosts
each reviewer's dense tabular review surface, collects responses,
and exports a complete dataset for downstream analysis.

RRW exists to produce a **clean, complete, auditable dataset for
downstream analysis**. It performs no substantive analysis of the
review data itself; that is left to the data consumer's tool of
choice.

The system replaces older file-passing models (one workbook per
reviewer, mailed around) with a **server-hosted online review
artefact**. The artefact remains tabular, because the core use case
is high-density structured review: a reviewer evaluating many
reviewees on many fields, in one sitting, where horizontal scanning
across reviewees is essential.

---

## 2. Functional goals

The system must:

1. Allow authorised operators to **configure a review session** end
   to end (metadata, rosters, instruments, assignments, templates,
   schedules).
2. Allow operators to **populate** the reviewer and reviewee
   rosters and the pairwise relationships between them, either by
   CSV bulk import or by inline per-row entry.
3. **Generate individualised online review surfaces** based on the
   session configuration, one per reviewer.
4. **Invite reviewers** by email — a templated, per-reviewer
   message carrying a unique sign-in link — and **send reminders**
   on a schedule the operator configures.
5. Present reviewers with a **dense tabular review form** that
   shows one row per reviewee (or one row per group, for
   group-scoped instruments), columns for operator-chosen context
   ("display") fields and operator-chosen response fields, and
   per-cell input controls keyed to each response field's data
   type.
6. **Save** reviewer-entered data durably and let reviewers return
   to update or complete their work until they explicitly
   **submit**, after which the system records submission timestamps
   and continues to allow corrections until the session closes.
7. Let the operator **monitor** invitation engagement and response
   completion in real time, both per-reviewer and per-reviewee.
8. **Validate** session setup against a documented readiness
   checklist, surfacing every blocking error and every advisory
   warning, with deep links from each issue to the page that fixes
   it.
9. **Activate** a session in a single operator action — a
   transition that moves the session from `draft`/`validated` into
   `ready`, opens the reviewer surface for writes, and (when
   schedules are configured) triggers the timed dispatch of
   invitations and reminders.
10. **Export** the session as CSV — five per-entity files
    (reviewers, reviewees, relationships, settings, responses) plus
    a per-instrument response file in the zip-all bundle and an
    audit-events file behind the sys-admin gate.
11. **Archive** and (separately) **purge** sessions whose work is
    done, with manual operator control and per-session retention
    overrides.
12. Maintain an **append-only audit log** of every mutation, every
    state transition, every email send attempt, and every
    administrative action, exportable as CSV for compliance review.
13. Honour a **single canonical timezone per session** for every
    display surface (operator and reviewer) and every per-session
    CSV extract, with the sys-admin audit-log viewer as the
    deliberate UTC exception.
14. Provide **system-administrator surfaces** for workspace
    governance (operator allowlist), cross-session diagnostics, and
    per-session audit-log inspection.

---

## 3. Non-goals

The system does not:

- **Analyse the data it collects.** Statistical aggregation,
  scoring rubrics, dashboards, normalisation, leaderboards — none
  of this lives in RRW. The export is the deliverable.
- **Host non-tabular review forms.** Free-form questionnaire
  builders, branching logic, or non-grid layouts are out of scope.
  The unit of review is a row × column grid.
- **Run cross-session analytics.** The lobby lists sessions; it
  does not aggregate metrics across them.
- **Manage participants as cross-session accounts.** Reviewers and
  reviewees are session-scoped rosters; there is no global
  participant directory and no per-reviewer profile history.
- **Substitute for an institutional identity provider.** The
  system trusts the identity layer to authenticate operators and
  reviewers; it does not run its own password store.
- **Provide a customisable brand chrome per session.** The visual
  shell is consistent across deployments; operators customise
  *content* (session name, instructions, contact info, friendly
  labels) but not visual *style* (colours, logos, layout).
- **Send mass-marketing email.** Invitations and reminders are
  transactional and per-reviewer; the system has no concept of
  broadcast lists, unsubscribes, or campaigns.

---

## 4. User roles

Four roles interact with the system. The first three are
authenticated users; the fourth is a target audience but not an
in-system actor.

### 4.1 System administrator

Workspace-level governance. A sys-admin can:

- **Manage the operator allowlist** — promote workspace members to
  operator status, revoke operator status, delete users entirely.
- **Manage per-session owners** — add or remove a co-owner from
  any session in the workspace, even ones they do not personally
  operate.
- **Bulk-remove a user from all sessions** they appear on
  (departure cleanup).
- **View cross-session diagnostics** — a Sessions Diagnostics
  surface that lists every session in the workspace with summary
  state.
- **Read the per-session audit log viewer** for any session.
- **Download the audit-events CSV** for any session.

The sys-admin role is workspace-wide. It is not implied by being
an operator on every session; it is a separate flag.

### 4.2 Operator

The principal in-app actor. Operators are workspace members on the
operator allowlist; they may own zero or more sessions. An
operator can:

- **Create new sessions** they automatically own.
- **Be added as a co-owner** to other operators' sessions.
- **Configure every aspect** of sessions they own: metadata,
  rosters, instruments, relationships, assignments, email
  templates, schedules, settings.
- **Validate and activate** sessions they own.
- **Send invitations and reminders** (manual or via schedule)
  using their own configured email-send credentials.
- **Monitor** invitation and response activity on sessions they
  own.
- **Download all per-session extracts** for sessions they own.
- **Pause** an activated session (revert to draft), edit, then
  re-activate.
- **Archive and unarchive** sessions they own.
- **Purge and archive** a session they own (operator-triggered
  hard delete of responses + rosters + audit log).
- **Manage their own operator settings** — email-send credentials,
  default display timezone, personal library of reusable Response
  Type Definitions and RuleSets.

Operators do **not** see other operators' sessions in their lobby
unless they have been added as a co-owner. Sys-admins reach
non-owned sessions through the Sessions Diagnostics surface.

### 4.3 Reviewer

A session-scoped participant — the person who fills in the review
form. Reviewers can:

- **Sign in** through institutional identity or through a unique
  invitation link.
- **See a dashboard** of sessions they are invited to.
- **Open a session's review surface** and see one row per
  reviewee (or per group) for each instrument they are assigned to.
- **Save draft responses** at any time during the session's
  accepting-responses window.
- **Submit** their work to lock in a "complete" state on the
  operator's monitoring surfaces.
- **Continue editing** previously-submitted responses while the
  session remains open — submission is a status marker, not a
  lock.
- **Clear all** their responses with explicit confirmation (a
  per-reviewer destructive action).
- **Download** a CSV of their own response history once the
  session is fully submitted.

Reviewers do **not** see other reviewers' responses, do not see
session configuration, and have no operator affordances.

### 4.4 Downstream data consumer

The audience for the export. Not an in-system actor; treated as
the target of the extract files. Their analysis happens outside
RRW. The export contract (column order, encoding, completeness,
determinism) is designed for this consumer.

---

## 5. Core concepts

### 5.1 Session

The top-level unit. A session represents one review cycle and
carries every other entity inside it.

**User-supplied fields:** name, code (stable short identifier
unique per operator), description, deadline, display timezone,
help contact, scheduled activation timestamp (optional), invite
offsets and reminder offsets (optional), archive offset (optional),
retention overrides (optional).

**System-derived fields:** lifecycle status, created-at, modified-
at, created-by, activated-at, current schedule resolution.

A session **owns** its instruments, rosters (reviewers,
reviewees, relationships), assignments, response rows, invitation
rows, audit events, and email-template overrides. Deleting a
session cascades to all of these.

### 5.2 Reviewer

A person who gives feedback in this session. Reviewers are
session-resident — they exist only within the session they were
imported into; there is no cross-session reviewer table.

**User-supplied fields:** name, email (used for identity matching
and invitation delivery), up to three free-form tags, status
(active or inactive).

**System-derived fields:** unique within-session row id, created-
at, updated-at.

### 5.3 Reviewee

A person being reviewed. Reviewees do not sign in to RRW; they
are the *subjects* of evaluation, not participants. Reviewees,
like reviewers, are session-resident.

**User-supplied fields:** name, email or other identifier (used as
the unique within-session key — institutions that don't use email
identifiers can substitute student ID, employee number, etc.),
photo / profile link, up to three free-form tags, status.

**System-derived fields:** unique within-session row id,
timestamps.

### 5.4 Relationship

A row of pairwise context tags between a reviewer and a reviewee
in this session.

**User-supplied fields:** reviewer email, reviewee email, up to
three pair-context tags, status.

**System-derived fields:** timestamps.

Relationships exist to carry context the *pair* shares — for
example, "morning interview", "Team A", "Workshop 3" — that the
rule engine can pivot on and that display fields can surface to
the reviewer. A relationship row is optional; absence means the
default empty tag set.

### 5.5 Instrument

A review form attached to a session. A session always has at
least one instrument; multiple instruments allow multiple
distinct review surfaces (e.g., "Skills assessment" and
"Behavioural notes") in the same session.

**User-supplied fields:** name (operator-internal handle), short
label (≤32 characters, reviewer-facing — appears on the per-page
nav button and the H2 title), friendly description (≤2000
characters, reviewer-facing — appears as subtitle below the H2),
mode (per-reviewee vs group-scoped), pinned rule (which RuleSet
selects the assignment universe), accepting-responses flag,
visibility-when-closed flag, ordered list of response fields,
ordered list of display fields with per-field include/exclude and
sort-priority annotations.

**System-derived fields:** the materialised assignment rows the
pinned rule produces, the cached eligible-pair count, the
per-instrument fan-out copies for group-scoped instruments.

A session may have any number of instruments. Each instrument
defines its own response fields, display fields, sort defaults,
rule, and group mode independently of the others.

### 5.6 Response Type Definition (RTD)

A reusable definition of one *kind* of response — its data type,
its validation rules, its rendering as an input control.

**User-supplied fields:** name (e.g., `Likert5`, `1-to-5dec`,
`Short_text`, `Yes_no`), data type (String / Integer / Decimal /
List), min, max, step, list options, description.

**System-derived fields:** per-session id; one of 10 default
seeds materialised into every newly-created session
(`Long_text` / `Short_text` / `Yes_no` / `Grade` / `Likert5` /
`100int` / `0-to-2int` / `1-to-5int` / `1-to-5half` /
`1-to-5dec`).

Operators may add custom RTDs to a session or to their personal
library; library RTDs auto-copy into new sessions the operator
creates. Seeded RTDs are spec-locked — they cannot be edited or
deleted; the operator copies them ("Save as") to customise.

### 5.7 Response Field

A column on an instrument — one question the reviewer answers
per reviewee row.

**User-supplied fields:** field key (machine-friendly id, often
auto-derived from label), friendly label, the RTD it references,
required flag, help text, visibility flag, order within the
instrument.

**System-derived fields:** the inputs that render in each row's
cell (a text input, a number input, a select, etc.) — driven by
the referenced RTD's data type.

### 5.8 Display Field

A column on an instrument that shows *context about the reviewee*
to the reviewer — read-only, derived from existing roster /
relationship data, not collected by this review.

Display fields draw from **seven sources**:

1. The reviewee's name.
2. The reviewee's email or identifier.
3. The reviewee's photo / profile link.
4. The reviewee's tag 1 / tag 2 / tag 3.
5. The pair-context tag 1 / tag 2 / tag 3 from the relationship
   row matching `(reviewer, reviewee)`.

For each display field on each instrument, the operator chooses
which source feeds it, an optional friendly-label override, an
include/exclude flag, an order, and (for the operator-side
default) a tri-state sort-priority slot.

The reviewee's name and email are always present (cannot be
turned off); the other five sources are opt-in.

### 5.9 Assignment

A row linking a reviewer, a reviewee, and an instrument — the
unit "this reviewer will review this reviewee on this
instrument".

**Fields:** reviewer id, reviewee id, instrument id, include flag
(used by the assignment-regeneration reconciler), self-review
flag (computed: true when reviewer.email matches reviewee.email,
case-insensitive).

Assignments are produced by the assignment-generation step from
the instrument's pinned rule against the active roster. They are
not user-edited row by row; the operator changes them by changing
the rule or the rosters and regenerating.

### 5.10 Response

A reviewer's answer to one response field for one assignment.

**Fields:** assignment id, response field id, value (typed
according to the RTD), saved-at, submitted-at.

A response row is created the first time a reviewer enters a
value into that cell; clearing the value back to empty deletes
the row. Submission stamps every populated cell's `submitted_at`
in one atomic action.

For group-scoped instruments, one logical group answer fans out
to one response row per group member, all carrying the same
value. Reads collapse the fan-out back to one row per
`(instrument, group_key)` for monitoring, extracts, and the
reviewer surface.

### 5.11 Rule and RuleSet

A **rule** is a predicate over `(reviewer, reviewee)` pairs that
selects which pairs are eligible for an instrument. A **RuleSet**
is a named bundle of rules.

Rule predicates can match against reviewer tags, reviewee tags,
pair-context tags, the reviewer's self-pairing relationship, the
reviewee's self-pairing relationship, and the include flag.

A RuleSet is either **seeded** (system-provided, spec-locked,
copyable but not editable in place) or **personal** (operator-
authored, editable, optionally saved to the operator's library
for reuse across future sessions). Three seeded RuleSets always
exist in a new session: a full-matrix everyone-reviews-everyone
rule, an exclude-self-review variant, and an empty starter.

Each instrument **pins exactly one RuleSet**. Pinned rules drive
assignment generation per instrument; the operator changes a
rule by editing it (personal) or by saving-as-then-editing
(seeded).

### 5.12 Invitation

A per-reviewer, per-session record carrying a unique sign-in
token.

**Fields:** reviewer id, hashed token (the raw token is never
stored — it lives only inside the email body sent to the
reviewer), created-at, sent-at, opened-at, status.

An invitation is created when the operator (or auto-send
schedule) issues invitations for the session; it is opened when
the reviewer first redeems the link.

### 5.13 Audit event

An immutable record of one mutation or noteworthy read.

**Fields:** event type (enumerated), severity (info / warning /
error), summary text, actor id (operator id, system, or null),
session id, created-at (UTC), correlation id (request-scoped),
structured detail (a JSON envelope — one of `changes`,
`snapshot`, `counts`, or `set_changes`).

Every mutating service writes one or more audit events. Event
types follow a `subject.verb` convention (e.g.,
`session.activated`, `responses.saved`, `invitation.opened`,
`instrument.fields_reordered`, `reviewers.imported`).

### 5.14 Workspace

The deployment-level container. One RRW deployment serves one
workspace. The workspace holds the operator allowlist, the
sys-admin allowlist, and every session.

### 5.15 Email Outbox

The append-only ledger of every send attempt. Each row carries
the recipient, the merged subject and body, the kind
(invitation / reminder / responses-received), the correlation
ids for idempotency, and the status of the dispatch attempt.
The outbox is written *before* dispatch is attempted, so a
crash mid-dispatch leaves the queue recoverable.

---

## 6. Session lifecycle

A session moves through a small set of states. State drives what
the operator can do, what the reviewer sees, and how the system
treats the session in lobby and extract surfaces.

| State | Display label | Meaning |
|---|---|---|
| `draft` | Draft | Setup is open. Operator may edit any aspect. Reviewer surface is closed. |
| `validated` | Validated | Setup has been validated and passed all blocking checks. Setup is still open. Any setup mutation auto-invalidates back to `draft`. |
| `ready` | Activated | Reviewer surface is open and accepting responses. Setup is locked. Operator may pause back to `draft`. |
| `archived` | Archived | Session is filed away; not shown in the main lobby. No data deleted. Can be unarchived (returns to `draft`). |
| `expired` | Expired | Reserved terminal state for deadline-passed sessions. Not in active use today. |

### 6.1 Transitions

- **`draft → validated`**: Operator runs Validate Setup; the
  validation engine passes with no blocking errors.
- **`validated → draft`** (auto-invalidate): Any setup mutation
  (roster import, instrument edit, rule change, assignment
  regenerate) automatically flips the session back to `draft`.
  This is silent and invariant; the operator does not opt in.
- **`validated → ready`** (activate): Operator clicks Activate
  Session, possibly via the super-button (Generate → Validate →
  Activate). If warnings exist, the operator must explicitly
  acknowledge them; if blocking errors exist, the transition is
  refused.
- **`ready → draft`** (pause / revert): Operator clicks Pause
  Session. The operator must tick a confirmation checkbox; the
  reviewer surface closes; responses are preserved.
- **`draft ↔ archived`**: Operator archives from the lobby
  (any non-`ready` state can archive); operator unarchives from
  the archived-sessions child page (returns to `draft`).

The reviewer surface is open for writes **only in `ready`**. In
every other state the reviewer surface still loads, but inputs
render disabled and the Save / Submit / Clear affordances are
hidden.

### 6.2 Editable vs locked semantics

In `draft` and `validated`, every setup page is fully editable.
In `ready`, every setup page renders with a prominent yellow
"lock" card explaining that the session is open for responses
and offering a one-click Pause action. While locked, upload
affordances and destructive-action cards are hidden; form
controls inside builders are disabled.

The Edit Session Details page is also lifecycle-gated — its
form fields refuse changes that would alter the deadline,
timezone, or rosters of an active session unless the operator
first pauses.

### 6.3 Lazy deadline closure

When the deadline passes, the system **lazily closes** each
instrument on the first request that observes the past-deadline
state. Closure flips each instrument's `accepting_responses` to
false and emits one `instrument.closed reason=deadline` audit
event per instrument. After closure the reviewer surface remains
viewable (read-only) for the configured visibility window.

---

## 7. Identity and authentication

### 7.1 Operator identity

Operators sign in through the deployment's institutional identity
provider — typically a single-sign-on integration with the
workspace's directory. The system trusts the identity layer to
authenticate and passes through identity headers carrying the
operator's email and display name.

Operator email is the join key against the workspace allowlist;
only allowlisted emails reach operator surfaces. Non-allowlisted
authenticated users see an access-denied page.

A development fallback (fake auth) supplies a configured email
and name when no real identity layer is available; this is
disabled in deployed environments.

### 7.2 Reviewer identity

Reviewers sign in through the same institutional identity layer.
Two entry paths exist:

- **Direct session link** (`/me/sessions/{id}`). The signed-
  in user's email must case-insensitively match an active
  reviewer row on that session. Mismatch produces a friendly
  account-mismatch banner pointing the user at their account-debug
  page.

- **Unique invitation link** (`/me/invite/{token}`). The
  token is per-reviewer, per-session, one-shot redemption to a
  durable session URL. The token is hashed at rest — only the
  hash is stored; the raw token lives only in the email body.
  Redemption matches token → reviewer, checks the signed-in user's
  email matches the invited reviewer's email, stamps `opened_at`
  on first visit (idempotent), emits `invitation.opened`, and
  forwards to the session.

Reviewers can access only the sessions they are listed in.

### 7.3 Workspace allowlist

The workspace allowlist is the gate between authenticated
identity and operator capability. A user is one of:

- **Not allowlisted** — authenticated but cannot reach operator
  routes; sees an access-denied page.
- **Operator** — can create sessions and is automatically the
  owner of sessions they create; can be added as co-owner to
  other operators' sessions.
- **Sys admin** — operator privileges plus workspace governance
  capability.

The allowlist is managed in the sys-admin surface; promotion,
demotion, and removal are audit-logged.

### 7.4 Session ownership

Each session has one or more **operator owners**. Ownership is
managed on the session's Owners card on the Edit Session Details
page (visible to existing owners and to sys-admins). An owner
can add another allowlisted operator as a co-owner; an owner can
remove a co-owner. The last owner cannot be removed; a sys-admin
must transfer ownership first.

Sys-admins can manage any session's owners via the per-session
ownership management page in the sys-admin surface.

---

## 8. Per-session metadata and settings

A session carries metadata that the operator edits on the
session's Create / Edit Session Details form, plus per-session
preferences accessible from setup pages or operator settings.

### 8.1 Identity fields

- **Name** — free-form display label.
- **Code** — short stable identifier, unique per operator. Used as
  the filename prefix for every CSV extract (`{code}_kind.csv`)
  and as the operator's primary short-form reference.
- **Description** — optional long-form description; appears in
  reviewer-facing pre-open and post-close UI and in the session
  detail card.
- **Help contact** — free-form contact string surfaced to the
  reviewer.

### 8.2 Time fields

- **Deadline** — wall-clock datetime in the session's display
  timezone. Used by validation, by the auto-archive offset, and
  by the lazy deadline-closure observer.
- **Display timezone** — IANA timezone identifier. Resolution
  order at every render is: session zone → creating operator's
  default zone → UTC. Captured as a snapshot of the creating
  operator's default at session create time; not a live link.
  Honoured by every per-session surface, both operator and
  reviewer, and by every per-session CSV extract. The single
  exception is the audit-events CSV and the sys-admin audit
  viewer, which are deliberately UTC.

### 8.3 Schedule fields

The session optionally carries scheduled-event anchors and
offsets:

- **Scheduled activation timestamp** — moment at which a
  `validated` session auto-promotes to `ready`.
- **Invite offsets** — comma-separated durations (e.g., `0h`,
  `-1d`) anchored on the scheduled activation. Each offset
  triggers one auto-send of invitations.
- **Reminder offsets** — comma-separated durations anchored on
  the deadline. Each offset triggers one auto-send of
  reminders.
- **Archive offset** — duration anchored on the deadline at
  which the session auto-archives (currently inert pending
  pilot demand).
- **Retention exception** / **retention overrides** — per-
  session retention policy overrides (inert pending pilot
  demand).

The Edit Session Details form previews every resolved schedule
moment in a chronological "Schedule timeline" sub-card: Start
(scheduled activation), invite fires, End (deadline), reminder
fires.

### 8.4 Email-template fields

Each session carries operator-editable email templates with
per-field reset-to-default:

- **Invitation template** — subject and body. Merge tags:
  `$reviewer_name`, `$session_name`, `$deadline`,
  `$help_contact`, `$invite_url`.
- **Reminder template** — subject and body. Same merge tags
  minus `$invite_url`.
- **Responses-received template** — subject and body sent to
  the reviewer when they submit. Merge tags: `$reviewer_name`,
  `$session_name`, `$deadline`, `$help_contact`,
  `$submitted_at`.

A per-template enable/disable switch governs whether the
auto-send-on-submit responses-received email fires.

### 8.5 Friendly labels

The session also carries operator-editable display labels for
the 12 in-scope slots that flow through every reviewer- and
operator-facing surface:

- Reviewer tag 1 / 2 / 3
- Reviewee tag 1 / 2 / 3
- Reviewee photo / profile link slot
- Pair-context tag 1 / 2 / 3
- Reviewer identity slot
- Reviewee identity slot

Friendly labels rename the *display text* shown for these slots;
the underlying machine field name does not change. Changing a
label flows through the reviewer surface, the operator preview,
every CSV import preview and download, and the schedule-timeline
caption.

### 8.6 Self-review behaviour

Each session carries a **self-reviews active** flag. When true,
self-review pairs (reviewer reviewing themselves on a given
instrument) participate in the review surface; when false, they
are inactive in bulk. Per-pair include overrides apply
post-flip. The flag is editable only in `draft` / `validated`.

### 8.7 Per-operator settings

Distinct from per-session settings, each operator owns:

- **Email-send credentials** — host, port, username, password,
  display name, encryption mode. The password is encrypted at
  rest with a deployment-managed key. Email send happens
  "as the operator who initiated" — there is no shared
  workspace-level sender.
- **Default display timezone** — falls in when a new session is
  created.
- **Personal library of RTDs and RuleSets** — operator-curated
  reusable artefacts that auto-copy into newly-created sessions.

The operator's settings page also supports clear/reset of each
section.

A full catalogue of every persisted setting lives in
`spec/settings_inventory.md`.

---

## 9. Operator workflows

### 9.1 Lobby management

The Sessions lobby (`/operator/sessions`) lists every session the
operator owns. The lobby shows session name, code, created-by,
created-at, deadline, timezone (compact GMT-offset per row),
status, and tag chips per session.

Each row carries a checkbox; ticking opens an **inline row
expander** for single-row actions (rename, tag edit, deadline
adjust, archive, delete, duplicate, purge and archive). Multiple
tickings open the bulk-action variant of the expander.

The lobby supports:

- **Sort** on any column header (cookie-persisted).
- **Free-text search** filtering the visible rows.
- **Tag-filter strip** with an AND/OR mode chip and a clickable
  chip per tag (LocalStorage-persisted).
- **Bulk delete** of selected sessions (confirm-gated).
- **Bulk archive** of selected sessions.
- **Per-row clone** in two flavours: *full duplicate* (deep-copy
  rosters + responses + assignments + setup) and *config shell*
  (metadata + email templates + instruments + rules; no rosters,
  no responses).

The **archived-sessions child page** (`/operator/sessions/archived`)
mirrors the main lobby for sessions in `archived` state, with an
expander offering Unarchive, Download (extract), and Delete bulk
actions.

### 9.2 Create session

The Create Session form (`/operator/sessions/new`) asks for the
core metadata: name, code, timezone, deadline, description,
help contact.

The form **gates submit on Name + Code** being non-empty
(commit 9cfb70e, 2026-05-22). On submit, the session is created
as `draft`, the operator is set as the first owner, and the
operator lands on the **Edit Session Details** page to fill in
any remaining fields. The same redirect-to-Edit pattern applies
to the Sessions-lobby Clone action.

### 9.3 Session Home

The Session Home page (`/operator/sessions/{id}`) is the
operator's primary working surface for a session. It carries:

- **Workflow card** at the top (full width) — the lifecycle-
  driven card explaining the current state and offering the
  single most-important next action(s). The card frame is
  constant (H2 "Workflow", accent-blue border, height grows
  to fit); the contents differ across the ten lifecycle states
  (see [§9.7](#97-validation-and-activation)).
- **Session Details card** in the left column of the bottom
  grid — read-mostly metadata, the resolved Schedule timeline
  sub-card, and an Edit button to open the Edit Session
  Details sub-page.
- **Quick Setup card** in the right column — a four-slot
  surface (Reviewers / Reviewees / Relationships / Session
  settings) carrying one CSV upload affordance per slot plus a
  "Submit all" action that chains the imports in dependency
  order.
- **Extract Data card** below Quick Setup — five live CSV
  download tiles (Reviewers, Reviewees, Relationships, Settings,
  Responses) plus an inert zip-all bundle footer (the zip
  itself ships as part of the response-flavour follow-on).

The **Danger Zone card** (Delete Data + Delete Session) was
moved off Session Home into the bottom-right of the Edit Session
Details page on 2026-05-22 — destructive operations cluster
with the other edit affordances rather than competing for
attention on Home.

### 9.4 Edit Session Details

The Edit Session Details sub-page (`/operator/sessions/{id}/edit`)
opens from the Session Home Session Details card's Edit button.
It is a `.bottom-grid` split:

- **Left column** — the full metadata edit form (name, code,
  description, deadline, timezone, help contact, scheduled
  activation timestamp, invite offsets, reminder offsets), with
  inner half-width cards for the **Schedule timeline** preview
  and the **Owners** card.
- **Right column, bottom** — the **Danger Zone** card:
  - **Delete Data** — wipes every reviewer response in the
    session while preserving setup. Confirmation-checkbox gated.
    Always available, regardless of session state.
  - **Delete Session** — removes the session entirely.
    Confirmation-checkbox gated. Visible-but-disabled in
    `ready` (operator must pause first); the route also enforces
    the gate server-side as the source of truth.

### 9.5 Populate rosters

Three Setup pages share an identical chrome shape: Reviewers,
Reviewees, Relationships.

Each page offers:

- **Stats info card** at the top — high-level row counts
  (number of active rows, "Fields with data" pills showing
  which optional columns carry any non-empty value across the
  roster).
- **Friendly-label editor card** — inline editors for the
  display labels of this entity's tag and identity slots.
- **Operator-actions card** — a search + status-filter strip
  and a selection-driven row of bulk and per-row actions
  (Edit, Inactivate, Activate, Add new row, Search, Clear).
  In Edit / Add mode an inline Save + Cancel pair replaces the
  row of selection-driven buttons.
- **Preview table** — every row in the roster (paginated by
  search + filter), with sortable headers, column-visibility
  toggles for the three optional tag columns and the
  photo-link column, and a trailing **Updated** timestamp.
- **Upload card** below the table — CSV file input + Upload
  submit; replaces the roster wholesale on success.
- **Danger Zone card** below the upload — Delete All (confirm-
  gated, wipes the whole roster).

The Reviewers page collects: name, email, tag 1 / 2 / 3.
The Reviewees page collects: name, email_or_identifier, tag 1 /
2 / 3, photo link.
The Relationships page collects: reviewer email, reviewee email,
pair-context tag 1 / 2 / 3, status.

CSV import is **wipe-and-replace**: on each upload the whole
existing roster is dropped and the new file's rows take its
place. Validation errors block the import wholesale — partial
loads do not happen.

### 9.6 Configure instruments

The Instruments page (`/operator/sessions/{id}/instruments`)
is a consolidated per-instrument editor.

**All Instrument Status card** sits at the top, full-width:
deadline pill, accepting-responses pill row (one per
instrument), visibility-when-closed pill row, bulk Open/Close
and Show/Don't-show actions, and a Preview Instrument button
linking into the Previews hub.

Below it, one **per-instrument card** per instrument, each
carrying:

- **Identity row** — short label, operator-internal name,
  rule picker (current pinned RuleSet + eligible-pair count),
  accepting-responses toggle, visibility-when-closed toggle.
- **Display Fields table** — one row per included display
  field, with Source / Friendly Label / Include / Order / Sort
  controls. The seven D6 sources are choosable; reviewee name
  and email are always present.
- **Response Fields table** — one row per response field,
  with Field Key / Friendly Label / Type (RTD picker) /
  Required / Order. Type is editable on add but locked once
  the field has saved responses (matches the validation
  guarantees).
- **Response Fields Help table** — per-field help text and
  visibility flag (full-width below the field-builder grid).
- **Action row** — Save / Cancel / Edit (mutually exclusive
  state machine; only one instrument can be in edit mode at
  a time), Add new instrument, Add group instrument,
  Replicate (clones the current instrument's content into a
  new instrument after this one), Delete this instrument
  (cascade-confirm-gated; blocked when there is only one
  instrument).

The **Response Type Definitions card** lives below all per-
instrument cards: a full catalogue of every RTD in the
session with operator add / edit / delete. Editing an RTD
re-derives validation on every response field that references
it. Deleting an RTD that is referenced by any response field
shows a cascade-warning banner and is blocked until the
referencing fields are removed.

### 9.7 Configure assignments

The Assignments page (`/operator/sessions/{id}/assignments`) is
on the Operations row of the chrome. It carries:

- **Per-instrument status card** — one block per instrument,
  showing type (Individual / Group), pinned RuleSet, generated
  pair count, per-instrument self-review toggle (locked while
  `ready`), per-instrument "Show in preview table" filter
  checkbox.
- **Self-reviews card** — session-wide self-reviews-active
  toggle.
- **Operator-actions card** — search box + Search-by
  dropdown (All / Reviewer / Reviewee) + bulk Inactivate /
  Activate / Show-pair-row controls.
- **Assignments preview table** — every materialised pair,
  with reviewer identity + tag columns, reviewee identity +
  tag columns, pair-context tag columns, Include checkbox,
  Instrument column, sortable headers, column-visibility
  toggles.

Assignments are not edited row by row. The operator changes
which pairs exist by changing the rule (in Band 1 of an
instrument card on the Instruments page; the standalone Rule
Builder sub-page retired in Wave 5 PR 5.1) or the rosters and
**regenerating** via the Workflow card's Prepare action. See
[§14](#14-reconciling-regeneration) for what regeneration
preserves.

### 9.8 Validation and activation

The Workflow card on Session Home (and on every Operations-row
page as chrome) drives the lifecycle. Its ten states are
spelled out in `spec/workflow_card.md`; functionally they
cascade:

1. **Draft, rosters empty** — short-circuit state. Body explains
   the next step (populate rosters); no Primary action.
2. **Draft, populated, pre-generate** — Activate-Session super-
   button runs Generate → Validate → Activate in one click.
3. **Draft, generated, no errors** — Primary action is Activate
   Session (no detour). Secondary actions: See validation
   details, See previews.
4. **Draft, generated, blocking errors** — Primary action is See
   validation details (promoted because the operator must look
   at the errors before they can proceed).
5. **Validated, no errors, no warnings** — Activate Session is
   live; Revert to draft is a Secondary action.
6. **Validated, warnings only** — Activate Session detours
   through `/validate?activate=1` for warning acknowledgement.
7. **Activated, pre-invitations** — Manage Invitations is the
   Primary action; the second body section carries the Pause
   Session affordance with its own confirm checkbox.
8. **Activated, mid-cycle** — Monitor Responses is the
   Primary; Pause stays available.
9. **Activated, post-deadline** — visible-but-disabled controls;
   reviewer surface read-only.
10. **Closed / archived** — terminal; surfaces remain readable;
    Edit and most destructive actions are inert.

The **Validate page** (`/operator/sessions/{id}/validate`) is the
read-only deep-dive: setup-coverage grid (per section, per
issue), severity-filter chips, grouped issue list with per-issue
"Why this check?" disclosure and "Fix on {page} ↗" deep-links to
the offending row.

**Activation** flips `validated → ready` in one transaction:
every instrument's `accepting_responses` is set true, the
activation audit event fires, and (if a scheduled-activation
moment is set) `context.trigger="scheduled"` is recorded on the
event. Once active, the reviewer surface opens.

### 9.9 Manage invitations

The Invitations page (`/operator/sessions/{id}/invitations`) is
a reviewer-centric Operations-row tab.

- **Info card** at the top — eight lifecycle counters
  (eligible reviewers, invitations created / sent / pending,
  reminders sent / pending, completed / incomplete reviews).
- **Auto-send caption** — explains how the next invitation
  and reminder fires will resolve given the current schedule
  configuration, including any skipped reasons.
- **Filter card** — Status dropdown + free-text search +
  Apply / Clear.
- **Invitations table** — one row per reviewer carrying:
  reviewer name + email, email status (sent / queued / not
  sent), email-sent timestamp, per-reviewer engagement
  (opened / first-response / submitted), required-fields-
  filled count, last-reminder timestamp, per-row Send /
  Send-reminder / Regenerate actions (lifecycle-gated).

The chrome's session top-nav bar carries a **four-state
Invitations pill** — `Not created`, `Not sent`, `Partially
sent`, `All sent` — reflecting the session-wide invitation
status at a glance (commit 49f1875, 2026-05-22). Splitting
this from a single "Invitations" pill replaced the old binary
present-or-absent indicator.

### 9.10 Monitor responses

The Responses page (`/operator/sessions/{id}/responses`) is a
reviewee-centric Operations-row tab.

- **Info card** — counts of reviewees with responses, without
  responses, total reviewees.
- **Filter card** — search + status filter.
- **Responses table** — one row per reviewee, with name +
  email, coverage status (complete / adequate / at-risk /
  none), reviewers-completed count over total assigned, last-
  response timestamp.

A per-row drill-in opens a per-reviewee detail view showing
each reviewer's status for that reviewee.

The Responses page is monitoring-only; per-cell response
content is not readable here — that channel is the Extract
Data download.

### 9.11 Previews

The Previews hub (`/operator/sessions/{id}/previews`) is an
Operations-row tab carrying a per-instrument *operator's view*
of what each reviewer will see. The page mirrors the reviewer
surface (display columns, response columns, tag chips, photo
links) so the operator can sanity-check the instrument before
activating.

### 9.12 Extract data

The Extract Data card on Session Home (and the equivalent
operator-facing surface inside the chrome) offers five live CSV
downloads per session:

- **Reviewers** — roster columns.
- **Reviewees** — roster columns.
- **Relationships** — pair tags + status.
- **Settings** — full session-wide configuration round-trip.
- **Responses** — long-format reviewer × reviewee × instrument
  response data.

Each tile shows the live row count; tiles for empty rosters
grey their Download button. Filenames follow
`{session_code}_{kind}.csv`. A zip-all bundle footer collects
all five files plus per-instrument response CSVs into a single
`{code}_bundle.zip`. The **audit-events CSV** is deliberately
not on this card; it lives behind the sys-admin gate.

Full export contracts: see [§12](#12-data-export).

### 9.13 Operator settings

The operator's Settings page (`/operator/settings`) carries:

- **Email-send credentials** — host, port, username, password
  (encrypted at rest), display name, encryption mode (TLS,
  STARTTLS, none).
- **Default display timezone** — IANA picker with a worked-
  example preview.
- **Library RTDs card** — every RTD the operator has saved to
  their personal library, with per-row delete and per-row
  "in N sessions" count.
- **Library RuleSets card** — every RuleSet the operator has
  saved to their personal library, with the same per-row
  affordances.

### 9.14 Sys admin surface

The sys-admin surface is workspace-scoped and reachable from
the chrome's user menu. It carries:

- **Accounts Management** — workspace allowlist with per-row
  promote / demote / delete actions and a bulk toolbar.
- **Sessions Diagnostics** — cross-workspace listing of every
  session with summary state.
- **Per-session Owner Management** — add / remove operator
  co-owners on any session.
- **Per-session Audit Log viewer** — filter strip + pretty-
  printed detail expander over the session's audit-events
  history.
- **Audit-events CSV download** per session.

---

## 10. Reviewer experience

### 10.1 Access

A reviewer reaches their work through one of two entry points
(see [§7.2](#72-reviewer-identity)):

- The unique invitation link in the email they received.
- A direct link to the session (e.g., bookmarked from a prior
  visit) — sign-in match required.

After sign-in, the reviewer lands on:

- The **reviewer dashboard** (`/me`) — a list of sessions
  the signed-in identity is invited to or active in, with one
  card per session showing session name, deadline, status,
  and a "Open review" button.
- The **session review surface** for a given session — see
  below.

### 10.2 Pre-open and post-close behaviour

If the session is in `draft` or `validated` — visible to the
reviewer but not yet accepting responses — the reviewer sees a
**pre-open landing card** explaining the session is prepared
but not yet open, naming the deadline, and offering a return
link to the dashboard. No review form renders.

If the session is past deadline or paused, the reviewer's
**review surface still loads** but renders read-only: inputs
disabled, Save / Submit / Clear hidden, previously-saved
responses still visible. Per-instrument visibility-when-closed
controls whether each instrument's responses remain readable
or are hidden after close.

If the signed-in identity does not match any reviewer row on
the session, the reviewer sees an account-mismatch banner
pointing them at their account-debug page.

### 10.3 Review surface

The review surface (`/me/sessions/{id}/{page}`) is a
**dense tabular form** — one row per reviewee (or one row per
group, for group-scoped instruments) and one column per
display field plus one column per response field.

**Multi-instrument navigation.** A session with multiple
instruments renders each as its own "page" within the surface;
a per-instrument page-nav button at the top selects the
visible instrument. The reviewer's draft data on every page
persists in the form while they navigate between pages, and is
written together on Save / Submit.

**Cell rendering** is driven by each response field's RTD:

- String fields render as `<input type="text">` (≤100
  characters) or `<textarea>` (>100 characters, two-row
  default).
- Integer fields render as `<input type="number">` with min /
  max / step from the RTD.
- Decimal fields render as `<input type="number">` with a
  step ≤ 1.
- List fields render as `<select>` with an empty leading
  option plus the RTD's list values.

Display columns render as plain text (or as an anchor for
photo / profile-link sources).

**Sortability** — every column header on the review surface is
clickable to sort the rows by that column; Shift-click adds a
secondary priority. A "Reset" link snaps back to the
operator-configured default sort. The reviewer's choices
persist in a per-(browser, session, instrument) cookie.

**Self-review** — when the reviewer's own email matches a
reviewee row in the session (case-insensitive), the reviewer
sees a row for themselves. The reviewer surface marks the row
visually but does not block writes; the operator controls
session-wide self-review behaviour via the self-reviews-active
toggle.

### 10.4 Group-scoped review surface

For an instrument the operator has set to **group-scoped**, the
surface presents **one row per group** instead of one row per
reviewee. Groups are computed by partitioning the reviewer's
rule-eligible universe by the operator-marked boundary tags
on the Display Fields table.

The group row's identity column is a **composed display**
showing the boundary tag values on one line and (optionally)
the first ten member names on the second, with a "+N more"
overflow indicator. Reviewer writes to a group cell **fan
out** to one response row per group member; reads aggregate
back to one row per `(instrument, group_key)`.

Missing-required and validation errors surface once per group,
not once per member.

### 10.5 Saving

The reviewer surface uses an **explicit Save** model. Inputs
are dirty-tracked; the Save button is enabled while any
input on the current page is dirty. Clicking Save persists
every populated cell on the current page (other pages'
inputs persist in the DOM but are not written by this Save).

Clearing a cell to empty deletes that response row. There is
no per-cell autosave today; this is an intentional simple
contract.

### 10.6 Submission

**Submit** is a one-click session-wide action available on
every page. On click:

1. Every page's dirty inputs are saved (implicit save).
2. Required-field validation runs across every instrument's
   every assigned row.
3. If any required cell is empty, the submit is blocked and a
   full-width "Missing required" card enumerates the gaps
   row-by-row (`Page N: Reviewee X — field Y`). No partial
   submit happens.
4. If validation passes, every populated cell receives a
   `submitted_at` timestamp in one atomic transaction; per-
   page status pills flip to `submitted` and a per-row
   submission timestamp appears in each row's trailing status
   column.

After submission, the reviewer **may continue to edit** — the
session is not locked. Re-editing a previously-submitted
required field back to empty deletes the row and flips the
operator's monitoring view back to "in progress". Submission
in RRW is a status marker, not an enforcement gate.

### 10.7 Clear all

A reviewer-facing destructive action (in their own danger
zone) wipes every response across every instrument for that
reviewer. Confirmation checkbox required. Audit-logged as
`responses.cleared`.

### 10.8 Reviewer's own CSV download

Once the session has fully submitted (every required cell
populated and stamped), the reviewer can download a CSV of
their own response history — `{code}_my_responses.csv`,
same 21-column shape as the operator-facing Responses
extract narrowed to this reviewer's rows.

---

## 11. Invitations and email

The invitation and email subsystem is a central functional
contract of RRW. It is described here **in full** because the
operator-facing surface and the on-disk artefacts of the
subsystem (templates, tokens, outbox, schedules) are wired —
even though the last-mile dispatch leg (the actual transport
that hands a rendered message to an outbound mail server) is
not yet shipped.

### 11.1 What an invitation is

For every reviewer the operator wishes to invite, the system
creates one **invitation** row carrying:

- The reviewer's email.
- A unique one-shot **token** — generated at create time,
  embedded in the email body as a sign-in URL, and stored on
  the row only as a SHA-256 **hash**. The raw token is not
  persisted; it lives only in the email body.
- Status (`created`, `sent`, `opened`).
- Created-at, sent-at, opened-at timestamps.

When the reviewer clicks the link, the system hashes the URL
token, matches it to the invitation row, stamps `opened_at`
the first time (idempotent on subsequent visits), emits
`invitation.opened`, and forwards the reviewer to the
session's review surface.

### 11.2 What an email is

Each kind of message — invitation, reminder, responses-
received — is rendered from the session's operator-editable
template by substituting per-reviewer merge fields:

- **Invitation**: `$reviewer_name`, `$session_name`,
  `$deadline`, `$help_contact`, `$invite_url`.
- **Reminder**: `$reviewer_name`, `$session_name`,
  `$deadline`, `$help_contact`. (No `$invite_url` — the
  reviewer has already opened the invitation.)
- **Responses received**: `$reviewer_name`, `$session_name`,
  `$deadline`, `$help_contact`, `$submitted_at`.

Unmatched merge tags render as empty. The 2000-character
body limit applies per template.

Per-template **cc** and **bcc** override fields let the
operator copy a help-contact mailbox or an audit address on
every send.

### 11.3 The outbox

Every send attempt — manual or scheduled — writes to the
**email outbox** ledger *before* dispatch is attempted. Each
row carries:

- Session id, reviewer id, invitation id.
- Kind (invitation / reminder / responses-received).
- To-email, cc, bcc.
- Merged subject and body — exactly as they would go on the
  wire.
- Status (`queued`, `sending`, `sent`, `failed`).
- Audit columns: from-address, backend identifier, backend
  message id, delivered-at, payload hash, correlation id,
  error message.

The outbox is the **system of record** for what was sent.
Write-before-dispatch makes the queue crash-safe; on restart,
no message is lost and (with correlation-id dedupe) none is
double-sent.

A diagnostic outbox viewer behind the sys-admin gate shows
the per-session queue with kind, recipient, status, sent-at,
and the rendered body.

### 11.4 Scheduling — auto-send

The operator can configure **invite offsets** anchored on the
scheduled-activation moment and **reminder offsets** anchored
on the deadline. Each offset triggers one auto-send pass over
the eligible reviewers:

- **Auto-send invitations** fires at each invite-offset moment
  for sessions that are `ready`, have invitations created,
  and have not been manually sent.
- **Auto-send reminders** fires at each reminder-offset moment
  for sessions that are `ready`, are within the response
  window, and have outstanding invited-but-incomplete
  reviewers.

Per-offset audit events (`session.scheduled_invites_fired`,
`session.scheduled_reminders_fired`, plus per-skip events with
reasons) record every firing. Per-reviewer dedupe via the
outbox's correlation_id prevents duplicate reminders to the
same reviewer for the same offset.

The Session Details edit form previews every resolved fire
moment in chronological order in the Schedule timeline sub-
card; the Manage Invitations page surfaces the same
information as a captioned auto-send line.

### 11.5 Backend options

The dispatch leg of the subsystem is **pluggable**. The
system defines an abstract `EmailTransport` seam; one concrete
backend is selected per deployment.

Four options exist in the design space, in increasing order of
infrastructure ambition:

1. **SMTP relay (Option A).** The operator's personal SMTP
   credentials, configured on the operator settings page,
   speak directly to the institution's submission server.
   Per-operator "send-as-me" identity. Supports STARTTLS
   (port 587) and implicit TLS (port 465). Cheap; works
   anywhere. Bounce / delivery confirmation is best-effort.

2. **Microsoft Graph (Option B).** The deployment's Entra
   application credentials send through a shared
   institutional mailbox via the Graph `Mail.Send`
   application permission. Friendly-name customisation
   without spoofing; aggressive throttles at high volume.

3. **Azure Communication Services (Option C).** First-party
   Azure transactional email. Verified sending domain,
   SPF / DKIM-handled deliverability, per-message cost.

4. **Third-party transactional (Option D).** SendGrid /
   Mailgun / Postmark / Resend / AWS SES / equivalent. Each
   provider has its own API surface; the seam accommodates
   per-provider concrete implementations.

A full discussion of each option's deliverability,
infrastructure, and cost trade-offs lives in
`spec/email_infra_options.md`.

### 11.6 What is wired today, what is not

As of 2026-05-22, the following invitation-and-email surface
is **wired**:

- Per-session invitation, reminder, and responses-received
  templates with merge-tag substitution, reset-to-default
  per-field, per-template cc/bcc, and the 2000-character
  body limit.
- Invitation rows with per-reviewer one-shot tokens (hashed
  at rest, raw token in email body only).
- The opened-at idempotent stamping on token redemption,
  with the `invitation.opened` audit event.
- The outbox ledger — every send attempt writes a row
  before dispatch, with full envelope and merged body.
- Auto-send scheduling — invite offsets, reminder offsets,
  the lazy observer that fires per offset, the per-offset
  audit events on fire and skip, the manual-activate modal
  that warns the operator about pending auto-sends.
- The Schedule timeline preview on Edit Session Details
  showing every resolved fire moment.
- The Manage Invitations page with per-reviewer status,
  per-row Send / Send-reminder / Regenerate buttons, and
  the auto-send captions.
- The chrome strip's four-state Invitations pill
  (`Not created` / `Not sent` / `Partially sent` / `All
  sent`).
- The operator settings page for the SMTP credentials and
  the deployment configuration switch for the active
  backend.

What is **not yet wired**: the actual transport dispatch.
The `EmailTransport` seam is in place, the SMTP backend
(Option A) is stubbed, but no message is actually delivered
to a mail server today. Invitations and reminders accumulate
in the outbox with status `queued`; the Manage Invitations
page reflects them as queued. The functional contract is
complete and ready to be exercised; only the last mile (the
backend connection) is pending.

This gap is the scope of an upcoming segment of work. **The
functional spec describes RRW's intended invitation and
email behaviour in full** because the templates, tokens,
outbox, and scheduling are all live; the gap is a
deployment-level concern, not a functional one.

---

## 12. Data export

Five **live CSV downloads** ship on Extract Data per session:
Reviewers, Reviewees, Relationships, Settings, Responses. A
sixth file — the **audit-events CSV** — is reachable from the
per-session audit-log viewer behind the sys-admin gate. A
**zip-all bundle** wraps all six plus per-instrument response
CSVs and per-entity stats CSVs into a single archive.

### 12.1 Envelope

Every file is UTF-8, comma-delimited, with the header row
first. Filenames follow `{session_code}_{kind}.csv`. Datetimes
in per-session files are ISO 8601 with the session's resolved
offset (e.g., `2026-06-02T08:00:00+08:00`); datetimes in the
audit-events file are UTC throughout (this is the deliberate
exception, called out on the file's surface).

### 12.2 Per-entity files

- **Reviewers.csv** — `ReviewerName, ReviewerEmail,
  ReviewerTag1, ReviewerTag2, ReviewerTag3`. Active rows
  first, then by name, then by email. Status is **not**
  exported (operator manages via Setup UI).
- **Reviewees.csv** — `RevieweeName, RevieweeEmail_or_Identifier,
  RevieweeTag1, RevieweeTag2, RevieweeTag3, PhotoLink`. Same
  sort discipline.
- **Relationships.csv** — `ReviewerEmail, RevieweeEmail,
  PairContextTag1, PairContextTag2, PairContextTag3, Status`.
  Active rows first, by reviewer email, then by reviewee
  identifier.
- **Settings.csv** — three-column `field, value, data_type`
  format spanning six sections (session-level fields, email
  templates, RTDs, instruments, session RuleSets, friendly
  labels). Round-trips perfectly back through the Settings
  import path.

### 12.3 Responses extract

A 21-column long-format file:
`ReviewerName, ReviewerEmail, ReviewerTag1/2/3, RevieweeName,
RevieweeEmail_or_Identifier, RevieweeTag1/2/3, InstrumentName,
InstrumentShortLabel, FieldKey, FieldLabel, ResponseType,
Value, SavedAt, SubmittedAt, Version, SelfReview,
InstrumentFlavour`. A per-instrument preamble at the top of
the file lists each instrument's field dictionary.

Group-scoped instruments collapse one row per group rather
than per member. The file streams to the operator without
buffering the full dataset in memory.

### 12.4 Per-instrument response files (bundle only)

`{code}_instrument_{n}.csv` — same 21-column shape, narrowed
to one instrument per file, sorted reviewee-first then by
reviewer email. Shipped inside the zip-all bundle.

### 12.5 Entity-stats files (bundle only)

`{code}_reviewer_stats.csv` and `{code}_reviewee_stats.csv`
— roster columns plus per-instrument response-activity
metrics (draft pairs, submitted pairs, distinct partners,
fields-answered counts, required-fields-answered counts,
string-typed character counts). Shipped inside the zip-all
bundle.

### 12.6 Audit-events file

`{code}_audit_log.csv` —
`EventType, Severity, Summary, ActorEmail, CorrelationId,
CreatedAt (UTC), DetailJson`. Reached from the sys-admin
audit-log viewer; not surfaced on the operator-facing Extract
Data card.

### 12.7 Round-trip stability

The four roster pairs (Reviewers, Reviewees, Relationships,
Settings) are designed for **byte-stable round trip** — an
export-then-import cycle does not perturb the session's
config. Deterministic row order, deterministic field order,
empty-string handling for missing optional cells,
vocabulary normalisation, and seeded entries omitted from
the Settings extract together guarantee this.

### 12.8 Reviewer's personal extract

In addition to the operator-facing files, the reviewer can
download their own response history once the session is fully
submitted (see [§10.8](#108-reviewers-own-csv-download)).

The full per-file column listing, validation rules, and round-
trip guarantees are documented in `spec/csv_contracts.md`.

---

## 13. Validation

RRW validates user input at four boundaries.

### 13.1 Import validation

CSV uploads are validated row-by-row and file-as-a-whole
**before any database write**. The system collects every
validation error across the file and reports them all in one
response — the operator does not see a "fix the first error
then refresh" loop. Common checks:

- Required columns present.
- Email format and within-file uniqueness.
- Cross-table identity (a reviewer email may not also be a
  reviewee identifier, and vice versa).
- Foreign-key resolution (a Relationships row's reviewer/
  reviewee emails must exist on the rosters).
- Enum membership (status must be `active` or `inactive`).
- Tag-field length limits.

On any error, the import is refused wholesale; the page
re-renders with the existing roster intact and the validation
report at the top.

### 13.2 Session readiness validation

The Validate page (`/operator/sessions/{id}/validate`) runs a
documented checklist that gates `draft → validated`:

- Session metadata is complete (name, code, deadline, timezone).
- Rosters are non-empty and consistent.
- Each instrument has at least one response field.
- Each instrument has a pinned rule.
- Generated assignments cover every active reviewer (with
  warnings, not errors, for under-covered reviewees).
- Email templates are not empty.
- For group-scoped instruments, at least one boundary tag is
  marked.

Errors block activation; warnings require explicit
acknowledgement on `/validate?activate=1`. Every issue carries
a "Fix on {page} ↗" deep-link to the offending row on the
relevant Setup page.

### 13.3 Reviewer response validation

On Save, only RTD-level validation runs (e.g., the numeric
value parses, the chosen list option exists). Empty cells are
allowed during Save — drafts may be partial.

On Submit, required-field validation runs across every
instrument's every assigned row. Missing required fields
block the submit and are enumerated row by row in the
"Missing required" card. Invalid numeric values block the
submit with a per-cell error and preserve the user's typed
value.

### 13.4 Export validation

CSV exports are validated at row-write time — every row's
required columns are present, datetimes are normalised to
the session zone (or UTC for audit), and the row count
matches the expected entity count.

---

## 14. Reconciling regeneration

When the operator regenerates assignments (because rosters or
rules changed), the system does **not** wipe the assignments
and rebuild from scratch. Instead it **reconciles**:

1. Compute the new set of `(reviewer, reviewee, instrument)`
   pairs the active rules generate against the active rosters.
2. Insert pairs that are in the new set but not the old.
3. Drop pairs that are in the old set but not the new — and
   cascade-delete their response rows.
4. Keep pairs that are in both — preserving their existing
   responses.

This means a small rule edit or a single reviewer renaming
does not destroy mid-cycle reviewer work.

The **Activate super-button** runs a dry-run reconcile before
firing; if the regeneration would delete any saved responses,
the operator is detoured to `/validate?activate=1` with a
banner naming the exact responses that would be lost and a
required acknowledgement before the actual reconcile fires.

Full contract: `spec/reconciling_regeneration.md`.

---

## 15. Audit and logging

Every mutation in the system writes one or more **audit event
rows**. Each row carries the type (a `subject.verb` string
like `session.activated`), severity (info / warning / error),
actor (the operator who triggered it, or `null` for system-
emitted events), session, request-scoped correlation id,
timestamp (UTC), summary, and a structured `detail` JSON
envelope.

Event types are registered per emitter and validated against a
per-type schema at write time. The envelope is one of four
shapes — a before/after diff, an entity snapshot, a counts
roll-up, or a set-mutation. The contract is documented in
`spec/architecture.md` "Audit-event detail schema".

Coverage:

- **Lifecycle transitions** — `session.activated`,
  `session.reverted_to_draft`, `session.archived`, etc.
- **Setup mutations** — `reviewers.imported`,
  `instrument.field_added`, `relationships.deleted_all`, etc.
- **Assignment regeneration** — `assignments.generated`,
  with `excluded_counts` recording why each row was kept or
  dropped.
- **Response mutations** — `responses.saved`,
  `responses.submitted`, `responses.cleared`,
  `responses.deleted_all`.
- **Invitation lifecycle** — `invitation.created`,
  `invitation.sent`, `invitation.opened`,
  `invitation.regenerated`.
- **Email send attempts** — `email.send_attempted`,
  `email.send_succeeded`, `email.send_failed` (the last two
  rely on the transport leg shipping).
- **Workspace admin** — `user.promoted_to_operator`,
  `user.demoted_to_member`, `user.deleted`.
- **Scheduled-event lifecycle** —
  `session.scheduled_activation_fired`,
  `session.scheduled_invites_skipped`,
  `session.scheduled_reminders_fired`, etc.

Operators read their own session's audit log via the per-
session audit-log viewer in the sys-admin surface (the viewer
is gated on sys-admin, not on session ownership, so operator-
side reading is mediated through the sys-admin role). The
audit-events CSV is reachable from the same surface.

---

## 16. Retention, archive, and deletion

RRW offers three distinct mechanisms to remove data, in
increasing order of permanence.

### 16.1 Archive

Operator-driven, reversible. A session moves from `draft` (or
any non-`ready` state) into `archived`. Archived sessions:

- Disappear from the main Sessions lobby.
- Are visible on the archived-sessions child page.
- Have all data preserved on disk.
- Can be unarchived back to `draft` at any time.

### 16.2 Delete data

A per-session operator action on the Edit Session Details
Danger Zone. Wipes every reviewer response in the session
while preserving the rosters, instruments, assignments, and
configuration. Available in any state. Audit-logged as
`responses.deleted_all`. Useful for clearing a session between
two pilot runs without rebuilding the configuration.

### 16.3 Delete session

A per-session operator action on the Edit Session Details
Danger Zone. Removes the session entirely and cascades to
every dependent row (rosters, assignments, responses, audit
events for the session). Visible-but-disabled while the
session is `ready`; the operator must pause first.

### 16.4 Operator-triggered purge and archive

A bulk action on the Sessions lobby row expander: hard-
deletes a session's responses + rosters + audit log, then
archives the configuration shell. Useful for sessions that
have served their purpose but whose configuration the
operator wants to keep as a template.

### 16.5 Per-session retention

Two inert columns sit on each session — a per-session
retention exception and a per-session retention overrides
JSON — pending a scheduled-purge subsystem that has been
deferred. The functional intent is to let an operator (or
the workspace) configure a per-session retention window
distinct from a workspace default; the manual archive +
operator-triggered purge cover the per-session needs in the
meantime.

### 16.6 Scheduled archive and purge

Deferred. The functional intent — auto-archive after a
configurable offset from the deadline; auto-purge per a
deployment-or-session retention policy — is captured in the
schema but not currently fired. Operators today rely on the
manual archive (lobby row expander) and the operator-
triggered purge for these needs.

---

## 17. Permissions and access control

RRW enforces access at three gates:

1. **Workspace operator** — applies to every `/operator/*`
   surface. The signed-in identity must be on the workspace
   allowlist.
2. **Per-session operator** — applies to session-scoped
   `/operator/sessions/{id}/*` surfaces. The signed-in
   identity must be an owner of that session.
3. **Sys admin** — applies to the workspace governance and
   diagnostics surfaces. The signed-in identity must carry
   the sys-admin flag.

A fourth gate applies to reviewer surfaces:

4. **Reviewer in session** — the signed-in identity's email
   must match an active reviewer row on the session, or the
   invitation token must be valid for the signed-in identity.

Every gate is enforced server-side; UI affordances that the
current identity cannot use render either inert (with an
explanatory tooltip) or hidden, depending on the surface.

Destructive actions universally require **explicit
confirmation** (a tick-box gating the destructive submit)
and write one or more audit events.

Per-cell trust: reviewer POST endpoints build the assignment
index from the authenticated reviewer's own assignments;
foreign assignment ids supplied in form bodies are silently
ignored rather than dispatched against.

Secrets at rest (SMTP passwords) are encrypted with a
deployment-managed key.

A full security-posture catalogue lives in
`docs/security_posture.md`.

---

## 18. Glossary

- **Assignment** — A row linking `(reviewer, reviewee,
  instrument)`. Materialised by rule generation; not edited
  row by row.
- **Audit event** — An immutable record of one mutation.
- **Boundary tag** — A display field marked "Group by" on a
  group-scoped instrument. Members of a group share the same
  value for every boundary tag.
- **D6 source** — One of the seven possible display-field
  sources (reviewee name, reviewee email, photo link, three
  reviewee tags, three pair-context tags).
- **Display field** — A read-only context column on an
  instrument; one of seven D6 sources.
- **Display label** — The user-facing string for a lifecycle
  state. `ready` displays as "Activated"; `validated`
  displays as "Validated"; etc. The label vocabulary
  diverges from the enum vocabulary intentionally.
- **Friendly label** — The operator-editable display string
  for one of 12 in-scope slots (tag positions, identity
  positions).
- **Group-scoped instrument** — An instrument that presents
  one row per group rather than one row per reviewee.
- **Instrument** — A review form. A session has one or more
  instruments.
- **Invitation** — A per-reviewer record carrying a unique
  sign-in token.
- **Lifecycle state** — One of `draft`, `validated`, `ready`,
  `archived`, `expired`.
- **Outbox** — The append-only ledger of every email send
  attempt.
- **Pair-context tag** — A pair-level tag stored in the
  Relationships table.
- **Response** — A reviewer's value for one response field of
  one assignment.
- **Response field** — A column on an instrument that
  collects reviewer input. Typed by an RTD.
- **Response Type Definition (RTD)** — A reusable spec for
  one kind of response field (data type, validation, input
  control).
- **Reviewee** — A person being reviewed.
- **Reviewer** — A person giving feedback.
- **RuleSet** — A bundle of rules selecting which
  `(reviewer, reviewee)` pairs an instrument applies to.
- **Self-review** — An assignment where the reviewer and the
  reviewee are the same person (matched by email, case-
  insensitive).
- **Session** — One review cycle. The top-level unit.
- **Sys admin** — A workspace-level governance role.
- **Workspace** — The deployment-level container holding the
  operator allowlist and every session.

---

## 19. Reading guide

The per-page / per-subsystem specs that this document
references:

| Subject | Spec |
|---|---|
| Domain model + audit-event detail | `spec/architecture.md` |
| Auth posture + audience model | `spec/audience_and_identity_model.md` |
| CSV import / export contracts | `spec/csv_contracts.md` |
| UI vocabulary (button styles, layout) | `spec/domain_assumptions.md` |
| Email backend options | `spec/email_infra_options.md` |
| Group-scoped instruments | `spec/instruments.md` (operator-card / model side); `spec/assignments.md` (fan-out / aggregation) |
| Instruments page contract | `spec/instruments.md` |
| Lifecycle states and transitions | `spec/lifecycle.md` |
| Operations-row pages (Validate / Previews / Invitations / Responses) | `spec/operations_pages.md` |
| Operator button audit (canonical styles) | `spec/operator_button_audit.md` |
| Operator UI shell + chrome | `spec/operator_ui_concept.md` |
| Previews hub | `spec/preview_hub.md` |
| Quick Setup card | `spec/quick_setup_card_spec.md` |
| Reconciling assignment regeneration | `spec/reconciling_regeneration.md` |
| Reviewer surface — full contract | `spec/reviewer-surface.md` |
| Assignment engine + Assignments page | `spec/assignments.md` |
| Session Home page contract | `spec/session_home.md` |
| Sessions lobby page contract | `spec/sessions_overview.md` |
| Settings inventory (every persisted setting) | `spec/settings_inventory.md` |
| Setup pages shared shape | `spec/setup_pages.md` |
| Reviewer surface sort | `spec/sort_by_reviewee.md` |
| Timezone display | `spec/timezone_display.md` |
| Visual style (general primitives) | `spec/visual_style_general.md` |
| Visual style (RRW-specific) | `spec/visual_style_rrw.md` |
| Workflow card states | `spec/workflow_card.md` |

For ship-state — what URL works today, what audit event fires
today, what is queued for an upcoming segment — read
`docs/status.md`. For the long-term roadmap and segment-by-
segment history, read `guide/todo_master.md`.

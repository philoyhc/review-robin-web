# Review Robin Web — Functional Specification

> **Technology-neutral functional contract.** This document
> describes **what** Review Robin Web (RRW) is meant to do, in
> user- and concept-level terms — not **how** it is built.
>
> Implementation details (URLs, code modules, data types, frameworks)
> are owned by the per-page / per-subsystem specs alongside this file.
> This one names a route or an event type only where the contract
> turns on it, and the owning spec governs if the two differ.
> Cross-references are
> noted in [§19 Reading guide](#19-reading-guide).

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
7. Let the operator **monitor** invitation sends and response
   progress in real time, both per-reviewer and per-reviewee.
8. **Validate** session setup against a documented readiness
   checklist, surfacing every blocking error and every advisory
   warning, with deep links from each issue to the page that fixes
   it.
9. **Activate** a session in a single operator action — a
   transition that moves the session from `validated` into
   `ready`, opens the reviewer surface for writes, and (when
   schedules are configured) triggers the timed dispatch of
   invitations and reminders.
10. **Export** the session as CSV — five per-entity files
    (reviewers, reviewees, relationships, settings, responses), the
    first four (plus observers, when enabled) zipped as a setup
    bundle; the Extract data tab's lens
    files (by instrument, per-entity metadata, saved data shapes,
    token keys), zipped with the responses file as a responses
    bundle; and an audit-events file behind the sys-admin gate.
11. **Archive** and (separately) **purge** sessions whose work is
    done, with manual operator control and per-session retention
    overrides.
12. Maintain an **append-only audit log** of every mutation, every
    state transition, every send of invitations or reminders (the
    outbox row is the record of each email), and every
    administrative action, exportable as CSV for compliance review.
    Rows are never edited, and are deleted only by Delete session or by
    Purge and archive with the audit log ticked (§16.4, §16.5).
13. Honour a **single canonical timezone per session** for every
    display surface (operator and reviewer) and every per-session
    CSV extract. The sys-admin audit-log viewer is not a session
    surface: it reads in the viewing operator's zone or in UTC, at
    their choice, and its CSV keeps UTC.
14. Provide **system-administrator surfaces** for workspace
    governance (operator / admin / super-admin roles), cross-session
    diagnostics, and per-session audit-log inspection.
15. Give **reviewees and observers** authenticated read access to
    the review data collected about them (reviewee) or across the
    session (observer), in the operator-controlled form (Raw /
    Anonymized / Summarized) and release window each per-instrument
    visibility policy allows, plus a reviewee **Acknowledge**
    gesture.

---

## 3. Non-goals

The system does not:

- **Analyse the data it collects.** Statistical aggregation,
  scoring rubrics, dashboards, normalisation, leaderboards — none
  of this lives in RRW. The export is the deliverable.
- **Host non-tabular review forms.** Free-form questionnaire
  builders or non-grid layouts are out of scope. The unit of review
  is a row × column grid. Branching between response fields of one
  instrument, two levels deep, is in scope ([§5.7](#57-response-field));
  a third level, more than one branch per parent, and a String parent
  are not.
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

Five roles interact with the system. The operator, reviewer,
reviewee, and observer are authenticated users; the downstream
data consumer is a target audience but not an in-system actor.
The administrator tier (admin / super-admin) is a governance
elevation of the operator role, not a separate login.

### 4.1 System administrator (three-tier model)

Workspace governance is a **strict three-tier hierarchy** with
**nested capabilities** (super-admin ⊇ admin ⊇ operator). Operator and
admin are flags granted in-app, the admin flag by a super-admin only;
super-admin is derived from the deployer's configuration, never stored
and never changed in-app, and with none configured any admin may
manage admins. On top of operator capability an admin has Accounts
Management (the allowlist, invites, and removing a user from all
sessions), Sessions Diagnostics, and every session's audit log and its
CSV. Reading a session's diagnostics grants no edit rights: an admin
edits a session they do not own only after the audited **Manage**
self-add, so every config change is by a recorded owner.

`spec/permissions.md` §1, §3 and §4.1 own the roles, the gates and every
Accounts Management guard; `spec/audience_and_identity_model.md` §4 owns
the rationale.

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
- **Revert to draft** on an activated session, then edit and
  re-activate.
- **Archive and unarchive** sessions they own.
- **Purge and archive** a session they own (operator-triggered
  hard delete of responses + rosters + audit log).
- **Manage their own operator settings** — email-send (SMTP)
  credentials and default display timezone.

Operators do **not** see other operators' sessions in their lobby
unless they have been added as a co-owner. Admins reach non-owned
sessions through Sessions Diagnostics ([§4.1](#41-system-administrator-three-tier-model)).

### 4.3 Reviewer

A session-scoped participant — the person who fills in the review
form. Reviewers can:

- **Sign in** through institutional identity. The unique invitation
  link signs no one in: it needs that sign-in first, and takes a
  reviewer whose signed-in email matches the invitation's to their
  review surface.
- **See the `/me` dashboard** — a cross-role lobby of every
  session they touch in any participant role (reviewer / reviewee
  / observer).
- **Open a session's review surface** (`/me/sessions/{id}/{page}`)
  and see one row per reviewee (or per group) for each instrument
  they are assigned to.
- **Save draft responses** at any time during the session's
  accepting-responses window.
- **Submit** their work to lock in a "complete" state on the
  operator's monitoring surfaces.
- **Continue editing** previously-submitted responses while the
  session remains open — submission is a status marker, not a
  lock — and **Recall** a submission back to draft while the
  review is still open (activated and before its deadline).
- **Clear all** their responses with explicit confirmation (a
  per-reviewer destructive action).
- **Download** a CSV of their own response history, and view a
  read-only per-session **summary** page, once they have fully
  submitted.

Reviewers do **not** see other reviewers' responses, do not see
session configuration, and have no operator affordances.

### 4.4 Reviewee

A session-scoped participant — the person being evaluated. An
email-identified reviewee is a **live authenticated audience**.
A reviewee can:

- **Sign in** and reach their `/me` dashboard.
- **Open the results surface** (`/me/sessions/{id}/results`) —
  per-instrument sections rendering the responses collected *about
  them* in the operator-chosen form (Raw / Anonymized /
  Summarized) and only inside the open response-release window.
- **Acknowledge** they have seen their results (a one-shot,
  idempotent gesture that records when they did).

Access takes two checks: the roster check — an active reviewee row
whose email or identifier parses as a real email matching the
signed-in user,
case-insensitively — **plus a currently-resolving visibility
grant**, meaning at least one instrument granting this reviewee a
mode inside the open response-release window. The roster check alone
is not enough; without a grant the route answers 404 (see
[§10.9](#109-reviewee-results-surface)).
**Confidential reviewees** (non-email identifiers, used for
analysis-only sessions) cannot reach the results surface by
construction — there is no inbox to authenticate against.

### 4.5 Observer

A session-scoped participant who views **collated** results across
the session (as opposed to a reviewee, who sees only their own).
The observer roster is opt-in per session
(the Observers toggle, [§5.17](#517-feature-toggles)). An observer can:

- **Sign in** and reach their `/me` dashboard.
- **Open the collation surface** (`/me/sessions/{id}/collation`) —
  per-instrument tables aggregating responses across the reviewers
  and reviewees in the observer's **cohort** (a per-observer match
  rule authored on the Observers Setup page), in the form the
  per-instrument observer visibility policy allows (Raw /
  Anonymized rows / Anonymized summaries), with per-instrument CSV
  downloads. Anonymized downloads swap names for per-session
  opaque tokens the operator can reverse via the Extract-data Token
  keys card.

Observers are always email-identified.

### 4.6 Downstream data consumer

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
unique across the workspace), description, deadline, display timezone,
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
and invitation delivery), up to three free-form tags, photo /
profile link, status (active or inactive).

**System-derived fields:** unique within-session row id, created-
at, updated-at.

### 5.3 Reviewee

A person being reviewed. Reviewees are session-resident, like
reviewers. An **email-identified** reviewee is also a live
authenticated audience — they sign in, reach `/me`, and read the
results collected about them where a visibility policy grants it
(see [§4.4](#44-reviewee)); a reviewee identified by anything
other than an email is a subject of evaluation only, with no way
in.

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
label (≤32 characters, reviewer-facing — appears in the instrument's
status pill and the H2 title), friendly description (≤2000
characters, reviewer-facing — appears as subtitle below the H2),
unit of review (per-reviewee vs group-scoped), the instrument's
**assignment rule** (Band 1 — which reviewer × reviewee pairs are
eligible), page-break flag (where the reviewer surface
breaks to a new page), ordered list of response fields, ordered
list of display fields, and per-audience **visibility policies**
(see [§5.16](#516-visibility-policy)).

**System-derived fields:** the materialised assignment rows the
rule produces, the cached eligible-pair count, the per-instrument
fan-out copies for group-scoped instruments, and the
accepting-responses flag, which the session's lifecycle sets on
every instrument at once (Activate opens; the deadline, Close session,
Revert or Archive closes).

A session may have any number of instruments (no cap). Each
instrument defines its own response fields, display fields, rule,
unit of review, page-break, and visibility policies independently
of the others. The default instrument is created with the session
and ships with one Rating + one Comments response field.

### 5.6 Observer

A person who views collated session results. Observers live in a
per-session roster, opt-in via the Observers feature toggle
([§5.17](#517-feature-toggles)).

**User-supplied fields:** email (required identity — always
email-shaped), optional display name, a single free-form tag, a
per-observer **cohort match rule** (authored on the
Observers Setup page — selects which reviewers / reviewees the
observer's collation aggregates over), status.

**System-derived fields:** unique within-session row id,
timestamps. Cohort membership is materialised at request time on
the collation surface (no junction table).

### 5.7 Response Field

A column on an instrument — one question the reviewer answers
per reviewee row.

**User-supplied fields:** friendly label, **data type** (`String`
/ `Integer` / `Decimal` / `List`), inline bounds (min / max /
step for numeric; the options for List; length min/max for
String), required flag, help text (+ its visibility flag),
visibility flag, order within the instrument. A field may head a
**branch**: an Integer, Decimal or List field carries one condition,
and what the condition does to the fields it governs. **Show** (the
default): they show only while its answer meets it, and a required
governed field is required, and missing when empty, only while its
branch is open. **Require**: they always show, and are required exactly
while its answer meets it, else optional. A governed field may head a
branch of its own, one level down and no further; a field shows only
while every Show branch above it is open, and a Require branch above it
never hides it (`spec/instruments.md` §
*Branching between response fields*).

An Integer or Decimal parent's condition compares its answer with one
number (`=`, `≠`, `≥`, `>`, `≤`, `<`) or with a **range**: *within* or
*outside* a low and a high number, inclusive or exclusive, the low end
strictly below the high one; an inclusive *outside* counts the ends as
outside. A List parent's condition is `is` or `is not` against one
option or several, read as *any of* / *none of*. An unanswered parent,
or an answer that does not parse against its type, fails the
condition: a Show branch closes, and a Require branch's fields stay
answerable but optional.
A visible governed field can be required only when the instrument also
has an active required field outside any branch — the **anchor**, which
every submit answers — and Save and the settings CSV refuse it
otherwise. A **hidden parent** (Active off) hides its whole branch, a
branch inside it included.

**System-derived fields:** the field key (machine id, derived from
the label); the input control that renders in each cell (text
input, textarea, number input, or select) — driven directly by
the field's own data type.

Each response field carries its own data type and bounds. The Band 3
type picker offers pre-filled **List presets** (Boolean / Agreement /
Grades) for convenience; picking one fills in the type and options,
and the field does not remember which preset it came from.

### 5.8 Display Field

A column on an instrument that shows *context about the reviewee*
to the reviewer — read-only, derived from existing roster /
relationship data, not collected by this review.

Display fields draw from **nine sources**:

1. The reviewee's name.
2. The reviewee's email or identifier.
3. The reviewee's photo / profile link.
4. The reviewee's tag 1 / tag 2 / tag 3.
5. The pair-context tag 1 / tag 2 / tag 3 from the relationship
   row matching `(reviewer, reviewee)`.

For each display field on each instrument, the operator chooses
which source feeds it, an include/exclude flag and an order. Its
header is the session-wide friendly label for that source
([§8.5](#85-friendly-labels)), the same on every instrument. The
operator-side default
sort is set from badges on the Band 2 preview's column headers
(`spec/sort_by_reviewee.md`).

On an individual instrument the reviewee's name and email are
always present (cannot be turned off — they are the two locked
rows). On a group-scoped instrument the name stays locked too, so
member names always show below the group's identity line; email does
not apply to a group row. The other seven are opt-in.

### 5.9 Assignment

A row linking a reviewer, a reviewee, and an instrument — the
unit "this reviewer will review this reviewee on this
instrument".

**Fields:** reviewer id, reviewee id, instrument id, include flag
(used by the assignment-regeneration reconciler, seeded at
generation from the session's self-reviews-active flag for
self-review pairs — see [§8.6](#86-self-review-behaviour) — and
false whenever the reviewer or the reviewee is inactive),
self-review flag.

The self-review flag depends on the instrument's unit of
review:

- **Individual-scoped** — true when reviewer.email matches
  reviewee.email, case-insensitively.
- **Group-scoped** — the *whole-group* rule: true when the
  reviewer is a member of the group being reviewed (never the
  blank-boundary catch-all group), and when it fires **every
  assignment in that group is flagged**, not only the reviewer's own
  cell.

`spec/assignments.md` § *Self-review policy* is the authority.

Assignments are produced by the assignment-generation step from
the instrument's pinned rule against the roster. A pair with an
inactive side is still materialized but excluded, so its
responses survive a deactivate → Prepare → reactivate round trip;
only pairs whose two sides are active are assigned work. They are
not user-edited row by row; the operator changes them by changing
the rule or the rosters and regenerating.

### 5.10 Response

A reviewer's answer to one response field for one assignment.

**Fields:** assignment id, response field id, value (typed
according to the field's data type), saved-at, submitted-at.

A response row is created the first time a reviewer enters a
value into that cell; clearing the value back to empty deletes
the row. Submission stamps every populated cell's submitted-at
in one atomic action.

For group-scoped instruments, one logical group answer fans out
to one response row per group member, all carrying the same
value. Reads collapse the fan-out back to one row per instrument
per group for monitoring, extracts, and the reviewer surface.

### 5.11 Rule and RuleSet

A **rule** is a predicate over `(reviewer, reviewee)` pairs that
selects which pairs are eligible for an instrument. A **RuleSet**
is a named bundle of rules.

Rule predicates match against reviewer tags, reviewee tags, and
pair-context tags, using per-predicate operators (`IS` / `IS NOT`
and the cross-side `IS THE SAME AS` / `IS DIFFERENT FROM`).

Every RuleSet is **per-session**: a rule belongs to one
instrument in one session and nowhere else.

Each instrument owns its rule, authored inline in the instrument
card's **Instrument assignment rule** (Band 1). When every Link is
left in its "all"/"individual" state the instrument stores no rule
and the engine substitutes a **synthetic Full Matrix** (everyone
reviews everyone) at evaluate time; the moment a Link carries a
filter, a stored rule is created. The operator changes
a rule by editing Band 1; sharing a rule across instruments is via
Replicate-the-instrument, not a library.

### 5.12 Invitation

A per-reviewer, per-session record carrying a unique sign-in
token.

**Fields:** reviewer id, hashed token (the raw token is not on this
row; a sent invitation's is in its email body, which the outbox keeps
— §11.1),
created-at, sent-at, opened-at, status.

An invitation is created when the operator runs Prepare session
([§9.8](#98-validation-and-activation)); sending, manual or
scheduled, never creates one. It is opened when the reviewer first
redeems the link.

### 5.13 Audit event

An immutable record of one mutation or noteworthy read: never
edited after it is written, and deleted only by Delete session
(§16.4) or by Purge and archive with the audit log ticked (§16.5),
which keeps the archived session.

**Fields:** event type (enumerated), severity (info / warning /
error), summary text, actor id (operator id, system, or null),
session id, created-at (UTC), correlation id (request-scoped),
structured detail (a JSON envelope — a before/after diff, an entity
snapshot, a counts roll-up, or a set mutation).

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

### 5.16 Visibility policy

A per-instrument, per-audience grant controlling **who** may see
an instrument's responses, **in what form**, and **during which
window**. One grant per instrument per audience, resolved at view
time (nothing is copied onto assignments).

- **Audiences** (3): peer reviewer (a reviewer viewing their own
  work), reviewee, observer. The operator is not a configurable
  audience — the operator always sees everything, identified.
- **Form** (3 coherent modes): **Raw** (each reviewer's response,
  attributed), **Anonymized** (each response, attribution
  stripped), **Summarized** (per-data-type aggregate stats, no
  individual rows).
- **Window** (2): **session ongoing** — while the session is
  Activated (`ready`), whether or not its deadline has passed — and
  **responses released** — while it is Closed (`expired`) and inside
  the operator's Release-responses window. A grant carries one mode
  per window; a grant with a mode in both is visible in either.

Not every mode is valid in every cell (`spec/visibility_policy.md`
§3.1). The reviewer's own view has a fixed **Raw** baseline while the
session is ongoing, which the operator cannot turn off; after release
it is off or Raw.

Default on instrument create: no rows — beyond that baseline, an
instrument is invisible to every participant audience until the
operator opts each one in in the instrument card's visibility editor
(its "Who can see what you wrote" card, unlocked).

### 5.17 Feature toggles

Two per-session toggles, **Relationships** and **Observers** (both
off by default), show the optional Relationships and Observers Setup
tabs; the Observers toggle also shows the Extract data page's
Observers and Token keys cards. They gate no participant surface: an
observer reaches the collation surface through an active roster row
alone ([§10.10](#1010-observer-collation-surface)). Both are set on
the Session details config card. Once the corresponding roster has
any rows the toggle locks on (can't be flipped back off) to avoid
orphaning data behind a hidden tab.

### 5.18 Session tags

Free-form labels an operator puts on a session to find it again in the
lobby; participants never see them. Tags are typed comma-separated and
stored trimmed and lower case, at most 64 characters each and unique
per session. They are set on Create, on the Session details card's
**Tags** field ([§9.4](#94-session-details-config-card)), and from
the lobby's row and bulk expanders, whose typeahead offers the tags
already on the operator's sessions; the lobby's tag-filter strip
filters on them ([§9.1](#91-lobby-management)). Each change made in a
tag editor is audited as `session.tag_added` or `session.tag_removed`.
The tags also round-trip through Settings.csv and are copied by a
clone; neither of those paths writes a tag event. `spec/sessions_overview.md` owns the
lobby's filter.

---

## 6. Session lifecycle

A session moves through a small set of states. State drives what
the operator can do, what the reviewer sees, and how the system
treats the session in lobby and extract surfaces.

| State | Display label | Meaning |
|---|---|---|
| `draft` | Draft | Setup is open. Operator may edit any aspect. Reviewer surface is read-only (pre-open). |
| `validated` | Validated | Setup has been validated and passed all blocking checks. Setup is still open. Any setup change the readiness check reads auto-invalidates back to `draft`. |
| `ready` | Activated | Reviewer surface is open and accepting responses. Setup is locked. Operator may revert to `draft`. |
| `expired` | Closed | The operator closed the session with the Workflow-card **Close session** button. Every instrument is closed; all responses (drafts + submitted) are preserved. Operator can Revert to draft to reopen for editing. |
| `archived` | Archived | Session is filed out of the active lobby; no data deleted unless the operator chose to purge on the way in. The service accepts **any non-archived** state; which state each control offers it from is in §6.1. Unarchive returns it to `draft`. |

### 6.1 Transitions

Prepare session moves `draft → validated` on a clean validation, and
any setup change the readiness check reads flips the session back to
`draft`. Activate moves `validated → ready`, by the operator or on
schedule; Close session moves `ready → expired`; Revert to draft
returns `ready` or `expired` to `draft` with responses kept. The
Workflow card offers **Archive session** only in `expired`, while the
lobby's **Purge and archive** and the Extract data page's **Archive
session** card archive from `draft`, `validated` or `expired`, never
`ready` ([§16.5](#165-operator-triggered-purge-and-archive)); Unarchive
returns the session to `draft`. The release-responses window opens only
while the session is `expired` ([§8.3](#83-schedule-fields)). The
reviewer surface takes writes only in `ready`, before the deadline
([§10.2](#102-pre-open-and-post-close-behaviour)).

`spec/lifecycle.md` §1 and §2 own each transition, its guard and its
audit event, and §8 the scheduled ones.

### 6.2 Editable vs locked semantics

Setup is editable in `draft` and `validated` only. In every other state
the roster pages and Instruments render a yellow **lock card** naming
the way out, and their mutating controls are hidden or disabled by the
same test; **Observers** alone stays editable until `archived`
([§9.5](#95-populate-rosters)). The Email Template page carries no lock,
and Assignments, Invitations and Responses rely on the Workflow card.

`spec/lifecycle.md` §3 and §5 own the gates and the lock-card pattern;
`spec/session_home.md` owns the Session details card's own gate.

### 6.3 Lazy deadline closure

Once the deadline passes, the first request that observes it closes
every instrument and writes one `instrument.closed` event per
instrument. `spec/lifecycle.md` §4 owns the lazy close, and
`spec/reviewer-surface.md` "Lazy deadline-close" what the reviewer sees
after it.

---

## 7. Identity and authentication

### 7.1 Operator identity

Operators sign in through the deployment's institutional identity
provider — typically a single-sign-on integration with the
workspace's directory. The system trusts the identity layer to
authenticate and passes through identity headers carrying the
operator's email and display name.

Operator email is the join key against the workspace allowlist;
only allowlisted emails reach operator surfaces. A non-allowlisted
authenticated user who requests an operator route is redirected
(303) to their `/me` dashboard.

A development fallback (fake auth) supplies a configured email
and name when no real identity layer is available; this is
disabled in deployed environments.

### 7.2 Reviewer identity

Reviewers sign in through the same institutional identity layer.
Two entry paths exist:

- **Direct session link** (`/me/sessions/{id}`). The signed-
  in user's email must case-insensitively match an active
  reviewer row on that session. Mismatch answers a **bare 404** —
  no banner, no hint that the session exists — so a signed-in
  stranger cannot enumerate session ids. The friendly
  account-mismatch page belongs to the invitation path below, not
  here.

- **Unique invitation link** (`/me/invite/{token}`). The
  token is per-reviewer, per-session, redeemed to a durable session
  URL. The invitation row stores only its hash. An invitation send
  mints a fresh token and puts it in the email body, which the
  outbox row keeps, so a sys admin can re-read the link that
  was sent; a reminder reuses that link while it is still current,
  and sends a fresh invitation once a Regenerate has rotated it. The
  link stays usable until
  the next invitation send or a Regenerate rotates the token;
  a token minted at create time or by Regenerate is never written
  anywhere in the clear. It is a pointer, not a credential:
  redemption requires sign-in and a matching email (§11.1).
  Redemption matches token → reviewer, checks the signed-in user's
  email matches the invited reviewer's email, stamps opened-at
  on first visit (idempotent), emits `invitation.opened`, and
  forwards to the session. **On mismatch this path — and only this
  path — renders the friendly account-mismatch page**, with a
  `403`: the invited address partly masked, what to do when it is
  an alias, and the session's help contact.

Reviewers can access only the sessions they are listed in.

### 7.3 Workspace allowlist

The workspace allowlist is the gate between authenticated identity and
operator capability. A user not on it who requests an operator route is
redirected (303) to `/me?notice=organizers`; a user on it holds one of
the tiers of [§4.1](#41-system-administrator-three-tier-model). It is
managed on the Accounts Management page, and every change is
audit-logged. `spec/permissions.md` §1, §2 and §4.1 own the contract.

### 7.4 Session ownership

Each session has one or more **operator owners**. Ownership is
managed on Session Home's own **Owners** card (shown to the session's
owners, in any session state); the creator can also name
co-owners on Create's **Owners** card, saved with the session. An
owner can add another allowlisted operator as a co-owner and
remove a co-owner, themselves included; the last owner cannot be
removed. Each add or remove saves at once and is audited as
`session.owner_added` / `session.owner_removed`. The card has no
Lock / Unlock; removing another owner asks first. Per-session add and remove are
for owners only: a non-owner admin can only **self-add** (the adopt
bootstrap from Sessions Diagnostics) or clone. The one exception is
Accounts Management's **remove from all sessions**, which takes a
user off every session's owners at once, refused where they are the
sole owner, without the admin owning those sessions
([§4.1](#41-system-administrator-three-tier-model)).
`spec/session_owners.md` owns the contract.

---

## 8. Per-session metadata and settings

A session carries metadata that the operator edits on the Create
New Session form and, thereafter, in place on the **Session
details** config card on Session Home ([§9.4](#94-session-details-config-card)), plus
per-session preferences accessible from setup pages or operator
settings.

### 8.1 Identity fields

- **Name** — free-form display label.
- **Code** — short stable identifier, unique across the workspace,
  not per operator. Create, Session Home's Save and, on a `draft` or
  `validated` session, the lobby's row-expander Save refuse a code
  another session holds before writing anything; two simultaneous
  saves of one code are still refused, by the store's own uniqueness
  rule. Used as
  the filename prefix for every CSV extract (`{code}_kind.csv`)
  and as the operator's primary short-form reference.
- **Description** — optional long-form description; appears at the
  top of the reviewer's review surface (whether open or read-only),
  of the reviewee results and observer collation surfaces, and in
  the Session details card. The pre-open page does not show it.
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
offsets (the activation / invite / reminder consumers are wired;
archive / retention are deferred):

- **Scheduled activation timestamp** (Start) —
  moment at which a `validated` session auto-promotes to `ready`.
- **Invite offsets** — a list of ISO 8601 durations (e.g.,
  `-P1D`, `-PT2H`) anchored on the scheduled activation. Each
  offset triggers one auto-send of invitations.
- **Reminder offsets** — a list of ISO 8601 durations anchored
  on the deadline. Each triggers one auto-send of reminders.
- **Release-responses window** (Release-from / Release-until) — the
  absolute datetime window during which reviewee and observer
  "responses released" visibility grants open.
- **Archive offset** — duration anchored on the deadline at
  which the session auto-archives (schema present; consumer
  deferred pending pilot demand).
- **Retention overrides** — per-session retention policy overrides
  (schema present; consumer deferred).

Every scheduled anchor obeys a save-time ordering chain
(Start ≤ deadline ≤ Release-from < Release-until), which the
Settings CSV import enforces too, and an
unset-anchor rule (an offset whose anchor is unset never fires).
Triggers fire via the
lazy-observer pattern (on the next operator GET past the
scheduled time), not a background worker. The Session details
config card shows each offset's resolved fire moment inline.

### 8.4 Email-template fields

Each session carries operator-editable email templates with
per-field reset-to-default:

- **Invitation template** — subject and body. Merge tags:
  `$reviewer_name`, `$session_name`, `$deadline`,
  `$help_contact`, `$invite_url`.
- **Reminder template** — subject and body. The same merge tags
  as the invitation, `$invite_url` included.
- **Responses-received template** — subject and body sent to
  the reviewer when they submit. Merge tags: `$reviewer_name`,
  `$session_name`, `$deadline`, `$help_contact`,
  `$submitted_at`.

The responses-received template alone has an enable/disable switch,
which governs whether the
auto-send-on-submit email fires; the invitation and reminder
templates have none.

### 8.5 Friendly labels

The session also carries operator-editable display labels for
the **nine in-scope tag slots** that flow through every reviewer-
and operator-facing surface:

- Reviewer tag 1 / 2 / 3
- Reviewee tag 1 / 2 / 3
- Pair-context tag 1 / 2 / 3

(The reviewee identity / photo slots are **not** renamable — they
are identity, not labels; their built-in defaults always render.)

Friendly labels rename the *display text* shown for these slots;
the underlying machine field name does not change. Changing a
label flows through the reviewer surface, the operator preview,
and every CSV import preview and download. The nine renamable
**tag** labels are set in one of two places: the inline editor on
the Reviewers / Reviewees / Relationships pages, or the **roster CSV header** as a
`ReviewerTag1.<label>` suffix — the sole CSV round-trip carrier
for those labels.

### 8.6 Self-review behaviour

Each instrument carries a **self-reviews active** flag, the
Assignments page's per-instrument Self review toggle. When true,
self-review pairs (reviewer reviewing themselves on that
instrument) participate in the review surface; when false, they
are inactive in bulk, and Prepare / Generate keeps them so.
Per-pair include overrides apply post-flip. The session's own
flag only seeds a new instrument's; it has no editor and is set
by the Settings CSV import or Duplicate
(`spec/assignments.md`).

Separately, each instrument's rule can **exclude self-reviews
outright**: the **Include / Exclude self reviews** chip under Link 3 of the
instrument's Band 1 ([§9.6](#96-configure-instruments)), *Include*
by default and shown only once every Link is set. The line under it
follows the unit of review: on a group-scoped instrument, excluding
self reviews drops every group the reviewer belongs to. It takes effect at the next Generate:
excluded pairs are not generated at all, so an instrument that has
already generated loses those rows and their responses, behind the
Prepare confirmation ([§14](#14-reconciling-regeneration)). The
Assignments page then reports the instrument's self-reviews as
*Excluded by rule* (`spec/instruments.md` § *Self-review exclusion*).

### 8.7 Per-operator settings

Distinct from per-session settings, each operator owns:

- **Email-send credentials** — host, port, username, password,
  display name, encryption mode. The password is encrypted at
  rest with a deployment-managed key. Email send happens
  "as the operator who initiated" — there is no shared
  workspace-level sender.
- **Default display timezone** — falls in when a new session is
  created.

The operator's settings page also supports clear/reset of
the SMTP section.

### 8.8 User-interface feature toggles

The **Relationships** and **Observers** toggles
([§5.17](#517-feature-toggles)) sit on the config card, under
**Tags**, as the **Optional setup tabs and pages** field.

A full catalogue of every persisted setting lives in
`spec/settings_inventory.md`.

---

## 9. Operator workflows

### 9.1 Lobby management

The Sessions lobby (`/operator/sessions`) lists the sessions the
operator owns, with sort, search and a tag filter, and a row expander
for single-row and bulk actions: edits, tags, **Duplicate** /
**Duplicate settings only**, **Purge and archive**
([§16.5](#165-operator-triggered-purge-and-archive)) and Delete. A clone
is a fresh `draft` owned by the operator who cloned it; the copy's
trail opens with `session.cloned`, and the original's records
`session.duplicated`. The archived-sessions child page
(`/operator/sessions/archived`) lists `archived` sessions with Unarchive
and Delete.

`spec/sessions_overview.md` owns the lobby and the archived page;
`spec/roundtrip_coverage.md` owns what each clone mode carries.

### 9.2 Create session

The Create Session form (`/operator/sessions/new`) asks for the
core metadata: name, code, timezone, deadline, description,
help contact, and session tags.

The form **gates submit on Name + Code** being non-empty, and also
carries the User-interface settings toggles
([§5.17](#517-feature-toggles)), the schedule
fields, and an **Owners** card: the creator plus any workspace
operators the creator stages there, saved by **Create session**
(the card has no save of its own). An address that is not a
workspace operator refuses the whole submit. It also carries the
**Quick Setup card**, always unlocked and without its
replace-confirmation tick: files staged in its slots submit with
**Create session**, and are imported in slot order once the session
row exists (`spec/quick_setup_card_spec.md` "New-session variant").
On submit, the session is created as `draft`, the operator is set
as the first owner alongside any staged co-owners, and the operator lands on **Session
Home** — where the Session details config card is
the surface for filling in any remaining fields. The Sessions-lobby
`Duplicate` and `Duplicate settings only` actions land on Session
Home the same way.

### 9.3 Session Home

Session Home (`/operator/sessions/{id}`) is the operator's working
surface for a session: the Workflow card
([§9.8](#98-validation-and-activation)), the Session details card
([§9.4](#94-session-details-config-card)), the Quick Setup card, the
Owners card ([§7.4](#74-session-ownership)) and the Danger Zone
([§16.3](#163-delete-data), [§16.4](#164-delete-session)). The setup CSV
downloads are on the Extract data tab ([§9.12](#912-extract-data)).

`spec/session_home.md` owns the page, and
`spec/quick_setup_card_spec.md` the Quick Setup card.

### 9.4 Session details config card

The Session details card on Session Home is the only surface for
session config. Each field swaps between its value and its input; edit
mode is reachable only while the session is `draft` or `validated`; and
a save is non-destructive, so it leaves a `validated` session
`validated`. Tags are stored lower case.

`spec/session_home.md` "4. Session details card" owns the fields and the
save path; the settings themselves are
[§8](#8-per-session-metadata-and-settings)'s.

### 9.5 Populate rosters

Up to four Setup pages share one shape: Reviewers, Reviewees,
**Relationships** and **Observers** (each shown by its toggle,
[§5.17](#517-feature-toggles)). Each carries a preview table whose card
opens with a two-pane toolbar, and a row expander for the selected
rows; the preview-count line sits in the toolbar's left pane and is
shared by every preview page. Upload, Delete all and, except on
Observers, the friendly-label editor sit in the roster card's Unlock
panel. CSV import is wipe-and-replace and all or nothing; replacing
Reviewers or Reviewees while the session holds responses takes a
response-loss acknowledgement ([§14](#14-reconciling-regeneration)).
Observers is the one roster that stays editable through `ready` and
`expired`, and its expander carries the per-observer cohort match rule.

`spec/setup_pages.md` owns the shared shape and each page's columns;
`spec/lifecycle.md` §5 states the Observers exception.

### 9.6 Configure instruments

The Instruments page (`/operator/sessions/{id}/instruments`) edits each
instrument on one collapsible card, at most one unlocked at a time. A
card carries the instrument's identity; its assignment rule (Band 1,
the only place a rule is authored, behind the "Not set" safety gate,
where Link 3 picks Individual or Group and, for Group, the **boundary
tags**); a live preview with the visibility-policy editor (Band 2,
[§5.16](#516-visibility-policy)); its display and response fields
(Band 3, [§5.7](#57-response-field), [§5.8](#58-display-field)); and an
action row whose one Save commits the card.

`spec/instruments.md` owns the page, and `spec/visibility_policy.md`
§3.1 the policy grid.

### 9.7 Configure assignments

The Assignments page (`/operator/sessions/{id}/assignments`), on the
Operations row, shows the pairs generation produced: a per-instrument
status card, with pair counts, a `stale` pill and the self-review
include toggle ([§8.6](#86-self-review-behaviour)), and a preview table
whose row expander inactivates or activates the selected pairs.
Assignments are not edited row by row: the operator changes the rule
(Band 1, [§9.6](#96-configure-instruments)) or the rosters and
regenerates through Prepare session ([§14](#14-reconciling-regeneration)).

`spec/assignments.md` "Assignments operator page" owns the page, and
"Reconcile + regenerate" what regeneration keeps.

### 9.8 Validation and activation

The Workflow card on Session Home (and on every Operations-row
page as chrome) drives the lifecycle. **Its state machine is
`spec/workflow_card.md`'s to state, and is not restated here** —
a cascade of numbered states, each with its own body copy and button
set, plus a `W` overlay that adds a help-line to States 4–6 and
changes no button. Functionally, what a reader needs from here is the
shape:

- The card **short-circuits on an empty setup**. Past that it carries
  **Revert to draft** as the standing way back from every state that has
  one, and **one or two** Primary actions depending on state: States 4Err
  and 5 offer Send invites and Activate session together, and States 7
  and 10 offer none at all. The per-state matrix is
  `spec/workflow_card.md`'s.
- Its **right-hand column** is a setup checklist in every draft state
  (1 and 2); validation severity counts plus a link to the Validate page
  wherever validation has findings to show (4Err, and 4 / 5 / 6 under
  the `W` overlay); a one-line `Status` in the settled validated states;
  and no detail in States 7–10. The column reports how many findings
  there are, never which — the Validate page owns the per-issue table.
- **Prepare session** is the only compound action: it generates the
  assignment pairs, validates, and — only on a clean validation —
  creates an invitation for every active reviewer with at least one
  included assignment. A validation error stops it before that last
  step, so a prepared session can legitimately have no invitations.
- **Activate** opens the session for responses. Warnings do not block
  it but must be acknowledged on the Validate page; blocking errors
  refuse it.
- **Revert to draft** is the way back from both `ready` and `expired`,
  and **Close session** is the end-of-cycle transition.
- The card holds **at most four buttons** in any state
  (`spec/operator_ui_concept.md`).

The **Validate page** (`/operator/sessions/{id}/validate`) is the
read-only deep-dive: setup-coverage grid (per section, per
issue), severity-filter chips, grouped issue list with per-issue
"Why this check?" disclosure and "Fix on {page} ↗" deep-links to
the offending row.

**Activation** flips `validated → ready` in one transaction:
every instrument starts accepting responses and the activation
audit event fires, recording a scheduled activation as scheduled
([§15](#15-audit-and-logging)). Once active, the reviewer surface
opens.

### 9.9 Manage invitations

The Invitations page (`/operator/sessions/{id}/invitations`) is the
reviewer-centric Operations tab: lifecycle counters, then one row per
reviewer with email status, progress and the per-row Send, Send
reminder and Regenerate actions. The auto-send captions sit in the
Workflow card's right-hand column ([§11.4](#114-scheduling--auto-send)),
and the session top-nav carries a four-state Invitations pill
(`Not created`, `Not sent`, `Partially sent`, `All sent`).

`spec/operations_pages.md` "Invitations page" owns the page, and
`spec/visual_style_rrw.md` the pill.

### 9.10 Monitor responses

The Responses page (`/operator/sessions/{id}/responses`) is the
reviewee-centric Operations tab: coverage counters, then one row per
reviewee with its coverage status and a per-reviewee drill-in. It is
monitoring-only; response content is read through Extract data
([§9.12](#912-extract-data)). `spec/operations_pages.md` "Responses page"
owns it.

### 9.11 Reviewer and email previews

The Invitations per-reviewer drill-in carries the three rendered email
previews and an **Open reviewer surface** link to an inert operator
view of that reviewer's surface; there is no separate Previews page.
`spec/operations_pages.md` "Per-row drill-in" and "Page identity" own
both, and `spec/reviewer-surface.md` "Operator preview mode" the view.

### 9.12 Extract data

The Extract data Operations tab (`/operator/sessions/{id}/extract-data`)
cuts the response data for offline analysis — Extract all data, By
instrument, Reviewer / Reviewee response metadata, the Data shaper,
Token keys and an Archive session card
([§16.5](#165-operator-triggered-purge-and-archive)) — and hosts the
Extract Setup card with the round-trip setup CSVs. It is not an in-app
analysis tool. Every download emits an audit event; the audit-events
CSV sits behind the admin gate instead; and Rehydrate is built but
switched off by deployment setting (`spec/rehydrate.md`).

`spec/extract_data.md` owns the page, `spec/session_home.md` "2. Extract
Setup card" the setup card, and [§12](#12-data-export) the files.

### 9.13 Operator settings

The operator's Settings page (`/operator/settings`) carries their own
email-send (SMTP) credentials, their default display timezone, and a
confirm-gated **Clear all settings (SMTP)**. Every SMTP field but
display name is required: until all are set, email reads as not
configured. The Email send (SMTP) card sits alone in the left column,
its "Bring your own SMTP" intro shown only until an SMTP host is saved;
Date & time and Clear all settings (SMTP) stack on the right.

`spec/settings_inventory.md` §1 owns the stored fields, and
`spec/email_infra_options.md` the SMTP option.

### 9.14 Sys admin surface

The sys-admin surface, reached from the chrome's **Admin** link, carries
Accounts Management (the allowlist, its bulk actions and invite by
email), Sessions Diagnostics (every session, with the audited
**Manage** self-add), and each session's Outbox viewer
([§11.3](#113-the-outbox)), Audit Log viewer and audit-events CSV. It
has no per-session owner management ([§7.4](#74-session-ownership)).

`spec/permissions.md` §3 and §4.1 own its gates and actions, and
`spec/operator_ui_concept.md` §6 its pages.

### 9.15 Guide, About and theme

The operator chrome and the participant top bar carry **Guide** and
**About** links and a **Light / Dark** theme toggle. `/guide` is the
in-app documentation: a viewer sees only the sections for the roles
they hold, and one who holds none is redirected (303) to `/about`.
`/about` says what the software is, who is signed in, and whom to ask
for operator access. The theme is a per-browser preference, never
stored on the server.

`spec/role_landing_and_visibility.md` §3 and
`spec/operator_ui_concept.md` own the two pages, and
`spec/settings_inventory.md` §7 the theme key.

---

## 10. Reviewer experience

### 10.1 Access

A reviewer reaches their work through one of two entry points, both
behind institutional sign-in (see [§7.2](#72-reviewer-identity)):

- The unique invitation link in the email they received. It asks for
  sign-in first, then takes a reviewer whose signed-in email matches
  the invitation's to their review surface.
- A direct link to the session (for example, bookmarked from a prior
  visit), which needs an active reviewer row matching the signed-in
  email.

After sign-in, the reviewer lands on:

- The **`/me` dashboard** — a cross-role participant lobby
  listing **every session the signed-in
  identity touches in any participant role** (reviewer / reviewee
  / observer). One table row per session carries the session name
  with per-role pills beneath it, Start / End / Timezone columns,
  a Session-status pill (Not open yet / Open / Available / Closed, one
  rule for every role; an archived session is not listed), and a
  Reviewer-status pill. The
  session-name link targets the first reachable role in priority
  order Reviewer → Reviewee → Observer; each role pill deep-links
  to its own surface.
- The **session review surface** for a given session — see
  below.

Every participant surface also carries a **role-navigator chip
strip** below the page header, letting a multi-role user swap
between their reviewer / reviewee / observer surfaces on the same
session without bouncing through `/me`.

### 10.2 Pre-open and post-close behaviour

If the session is in `draft` or `validated`, the reviewer sees a
**not-open landing card**: "This review is not currently open.",
then the scheduled opening (a `validated` session only), the deadline
and the help contact, each when it applies, and a return link to the
dashboard. No review form renders. An `archived` session answers a
bare 404 to every participant.

If the session is `ready` but past its deadline, or `expired`, the
reviewer's **review surface still loads** but renders read-only:
inputs disabled, Save / Submit / Clear hidden, previously-saved
responses visible as each instrument's visibility policy allows:
always while the session is ready, and after close only through a
Raw "Responses released" grant inside the release window
(`spec/reviewer-surface.md` "Lifecycle gating").

If the signed-in identity does not match any reviewer row on
the session, a direct link answers a **bare 404** — the
enumeration-safe bare refusal. The friendly
account-mismatch page belongs to the *invitation* path
([§7.2](#72-reviewer-identity)), which answers 403 and names the
invited address.

### 10.3 Review surface

The review surface (`/me/sessions/{id}/{page}`) is a **dense tabular
form**: one row per reviewee (or per group,
[§10.4](#104-group-scoped-review-surface)) and one column per display
field and per response field, each cell's control set by the field's
data type and bounds. The operator's page breaks divide the instruments
into numbered pages, each its own server-rendered URL. Above each table
a read-only card shows who can see what the reviewer wrote
([§5.16](#516-visibility-policy)); a governed field follows its branch
([§5.7](#57-response-field)); and the reviewer can sort by any column.
When the reviewer's own email matches a reviewee row, their row for
themselves carries a **Self review** marker and writes are not blocked;
whether that row is active is the operator's
([§9.7](#97-configure-assignments)).

`spec/reviewer-surface.md` owns the surface, and
`spec/sort_by_reviewee.md` its sort.

### 10.4 Group-scoped review surface

A group-scoped instrument shows one row per group instead of one per
reviewee, the groups drawn by the boundary tags of its assignment rule
([§9.6](#96-configure-instruments)). A write to a group cell fans out to
every member, reads collapse back to one row per group, and errors
surface once per group. `spec/reviewer-surface.md` "Group-scoped
instruments" owns the surface, and `spec/assignments.md` "Group-scoped
fan-out" the storage.

### 10.5 Saving

The surface saves on an explicit **Save**, always enabled, which stores
the current page's inputs and reloads it; an invalid value answers 400
and re-renders the page with the typed value kept, while the valid ones
save. **Cancel** reloads the last-saved values, clearing a cell deletes
its response, and there is no autosave. `spec/reviewer-surface.md`
"Save / Cancel / Page navigation / Submit / Clear all" and "Persistence
semantics" own it.

### 10.6 Submission

**Submit** is one session-wide action on every page: it saves the
current page, refuses with a list of the gaps if any required cell is
empty anywhere, and otherwise stamps every populated answer as
submitted in one transaction. Submission is a status marker, not a
lock: the reviewer may keep editing; changing a submitted answer clears
its submission, and blanking one clears the submission of that
assignment's other answers, until they submit again.
`spec/reviewer-surface.md` "Missing required flow" and "Persistence
semantics" own it.

### 10.7 Clear all

A confirm-gated **Clear all** in the reviewer's own danger zone wipes
every response they hold across every instrument, audited as
`responses.cleared`. `spec/reviewer-surface.md` owns it.

### 10.8 Reviewer's own CSV download and summary page

Once every assignment is submitted, the reviewer can open a read-only
**summary page** (`/me/sessions/{id}/summary`), **recall** the
submission while the review is still open, and download
`{code}_my_responses.csv`, their own rows in the operator Responses
extract's shape ([§12.6](#126-reviewers-personal-extract)).
`spec/reviewer-surface.md` "Per-session summary" owns the page, and
`spec/csv_contracts.md` the file.

### 10.9 Reviewee results surface

An email-identified reviewee reaches `/me/sessions/{id}/results`
through the two checks of [§4.4](#44-reviewee). For each instrument
whose policy releases something to them, they see the responses about
them as Raw, Anonymized or Summarized, only inside the response-release
window, plus a one-shot **Acknowledge** (`reviewee.results_acknowledged`).
`spec/participant_model.md` §4.1 and `spec/reviewer-surface.md`
"Reviewee results" own the surface, and `spec/visibility_policy.md` the
modes.

### 10.10 Observer collation surface

An observer reaches `/me/sessions/{id}/collation` through an active
observer row matching their email; the page needs no current grant to
load. It shows per-instrument collation tables over the observer's
**cohort**, with CSV downloads, in the form and window the observer
policy allows. Anonymized downloads use per-session tokens the operator
can reverse ([§9.12](#912-extract-data)), and an archived session
answers 404. `spec/reviewer-surface.md` "Observer collation surface" and
`spec/participant_model.md` own it.

---

## 11. Invitations and email

The invitation and email subsystem is a central functional
contract of RRW, summarized here; each subsection names the spec
that owns its detail. One leg — handing a
rendered message to a mail server — is not part of the send path;
[§11.6](#116-dispatch) states what a send does instead.

### 11.1 What an invitation is

For every reviewer the operator wishes to invite, the system
creates one **invitation** row carrying:

- The reviewer it is for, by id; the email is read off the
  reviewer row, not stored on the invitation.
- A unique **token** — generated at create time, embedded in the
  email body as a sign-in URL, and stored on the invitation row only
  as a SHA-256 **hash**. Each invitation send mints a fresh token;
  that email body, raw token included, is kept on its outbox
  row (visible to sys admins). A reminder reuses the most recent
  invitation link while it is current; when there is none, or a
  Regenerate has rotated it since, it falls back to an invitation
  send, which mints a token. The link is reusable until
  the next invitation send or a
  Regenerate (per invitation or bulk) rotates the token, after which
  the outbox copy is stale. A token minted at create time or by
  Regenerate is never stored in the clear. **It is not a
  credential:** redemption requires Easy Auth sign-in and returns 403
  unless the signed-in email matches the invited reviewer, so a reused
  or leaked link admits no one else. If sign-in-free magic links are
  ever built, the token becomes a credential and must then be
  one-shot and never stored.
- Status (`pending` until sent, then `sent`, then `opened`; a
  Regenerate returns it to `pending`).
- Created-at, sent-at, opened-at and last-reminder-at timestamps.

When the reviewer clicks the link, the system hashes the URL
token, matches it to the invitation row, stamps opened-at
the first time (idempotent on subsequent visits), emits
`invitation.opened`, and forwards the reviewer to the
session's review surface.

### 11.2 What an email is

Each kind of message — invitation, reminder, responses-received — is
rendered from the session's operator-editable template by substituting
per-reviewer merge tags, with per-template cc and bcc. An unrecognized
tag is left in the text as typed, so a typo cannot fail a send.
`spec/email_template_editor.md` §6 owns the merge-tag sets and the
rendering, and §2 the editor.

### 11.3 The outbox

Every send attempt, manual or scheduled, writes an **email outbox** row
before any dispatch: the recipients, the kind, the merged subject and
body exactly as they would go out, and a status. The outbox is the
system of record for what was sent, and sys admins read it in a
per-session viewer ([§9.14](#914-sys-admin-surface)).
`spec/email_infra_options.md` "Audit log" and "Idempotency" own the
table and its retry rules.

### 11.4 Scheduling — auto-send

The operator sets **invite offsets** anchored on the
scheduled-activation moment and **reminder offsets** anchored on the
deadline. Each offset fires one auto-send pass over the eligible
reviewers, a reminder falling back to a fresh invitation where the
reviewer has no current link ([§11.1](#111-what-an-invitation-is)), and
each firing or skip is audited. The Session details card shows every
resolved fire moment, and the Workflow card's right-hand column carries
them as auto-send captions.

`spec/lifecycle.md` §8 owns the schedule and its fire-time rules, and
`spec/workflow_card.md` "Signal lines" the captions.

### 11.5 Backend options

Dispatch sits behind one pluggable transport seam, with one backend per
deployment. Four options are in the design space: an SMTP relay using
the operator's own credentials (Option A), Microsoft Graph (B), Azure
Communication Services (C) and a third-party transactional provider
(D). `spec/email_infra_options.md` owns each option and its trade-offs.

### 11.6 Dispatch

No send hands a message to a mail server. An invitation or reminder
send — manual or scheduled — renders the message, writes its outbox
row and marks it `sent` at once, as a **dev-mode preview**; the
reviewer's invitation stamps follow as if it had gone. A reviewer's
submit queues the responses-received confirmation the same way but
leaves it `queued`. An SMTP transport (STARTTLS or implicit TLS) and
a Microsoft Graph stub exist behind the transport seam
([§11.5](#115-backend-options)), and SMTP is the only transport an
operator can configure ([§9.13](#913-operator-settings)), but the send
path does not call either.

---

## 12. Data export

Extraction splits across two surfaces (see
[§9.12](#912-extract-data)): the **Extract data** Operations tab
hosts the response-shaping lenses + Data shaper, and the **Extract
Setup** card on that same tab hosts the round-trip
setup CSVs — Reviewers, Reviewees, Relationships, Observers (gated),
Settings — plus a `{code}_setup.zip` bundle.
The `{code}_responses.zip` bundle carries the unified Responses CSV
plus the lens cards' files, as each card is configured.
The **audit-events CSV** is reachable from the per-session
audit-log viewer behind the admin gate.

### 12.1 Envelope

Every file is UTF-8, comma-delimited, with the header row
first. Filenames follow `{session_code}_{kind}.csv`. Datetimes
in per-session files are ISO 8601 with the session's resolved
offset (e.g., `2026-06-02T08:00:00+08:00`); datetimes in the
audit-events file are UTC throughout (this is the deliberate
exception, called out on the file's surface).

### 12.2 Per-entity files

The setup files are Reviewers.csv, Reviewees.csv, Relationships.csv
(not gated on its toggle), Observers.csv (only with the Observers
toggle on) and Settings.csv, the three-column `field, value, data_type`
file that carries session config back through the Settings import.
`spec/csv_contracts.md` §2 and §3 own each file's columns, row order and
import rules.

### 12.3 Responses extract

The responses extract is one long-format file: a per-instrument field
dictionary as a preamble, then one row per answer under 21 fixed
columns. The column names and their positions are both part of the
contract [§12.5](#125-round-trip-stability) promises. A group-scoped
instrument's answers collapse to one row per reviewer, group and field
rather than one per member. `spec/csv_contracts.md` §2.4 owns the columns, the row order
and the collapse.

### 12.4 Audit-events file

`{code}_audit_log.csv` holds the session's audit events, with
`CreatedAt` in UTC. It is reached from the sys-admin audit-log viewer,
not from the Extract data tab. `spec/csv_contracts.md` §2.5 owns its
columns.

### 12.5 Round-trip stability

Four of the five CSV import / export pairs (Reviewers, Reviewees,
Relationships and Settings) are designed for **byte-stable round trip** — an
export-then-import cycle does not perturb the session's
config. Deterministic row order, deterministic field order,
empty-string handling for missing optional cells and
vocabulary normalization together guarantee this. Observers
round-trips too — it has a wired importer and extract, and
`Status` and `CohortRule` read back — but is not claimed
byte-stable (`spec/csv_contracts.md` "Round-trip stability
contract").

### 12.6 Reviewer's personal extract

In addition to the operator-facing files, the reviewer can
download their own response history once the session is fully
submitted (see [§10.8](#108-reviewers-own-csv-download-and-summary-page)).

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
- Cross-roster identity (a mailbox may not be held in two
  rosters under two different **names**). Holding it twice is
  fine and common — one person is often both reviewer and
  reviewee, which is the self-review case; only the names
  disagreeing is an error. Three-way across reviewers,
  reviewees and observers.
- Foreign-key resolution (a Relationships row's reviewer/
  reviewee emails must exist on the rosters).
- Enum membership (status must be `active` or `inactive`).
- Tag-field length limits.

On any error, the import is refused wholesale; the page
re-renders with the existing roster intact and the validation
report at the top.

### 13.2 Session readiness validation

The Validate page (`/operator/sessions/{id}/validate`) reports
the session's readiness findings, each an **error**, **warning** or
**info**. Errors block `draft → validated` and activation; warnings
do not block but must be acknowledged at activation, on
`/validate?activate=1`; info is advisory only. Every issue carries a "Fix on {page} ↗"
deep-link to the page that fixes it. The checks themselves, with
their severities, are `spec/validate_page.md` §3.2's to list.

### 13.3 Reviewer response validation

On Save, only data-type-level validation runs (e.g., the numeric
value parses within the field's bounds, the chosen list option
exists). Empty cells are allowed during Save — drafts may be
partial.

On Submit, required-field validation runs across every
instrument's every assigned row. Missing required fields
block the submit and are enumerated row by row in the
"Required fields missing." card. Invalid numeric values block the
submit with a per-cell error and preserve the user's typed
value.

---

## 14. Reconciling regeneration

When the operator regenerates assignments (because rosters or
rules changed), the system does **not** wipe the assignments
and rebuild from scratch. Instead it **reconciles**:

1. Compute the new set of `(reviewer, reviewee, instrument)`
   pairs the active rules generate against the rosters. A pair with
   an inactive side stays in the set, excluded.
2. Insert pairs that are in the new set but not the old.
3. Drop pairs that are in the old set but not the new — and
   cascade-delete their response rows.
4. Keep pairs that are in both — preserving their existing
   responses, except on a group-scoped instrument whose group the
   run adds a member to, which is cleared (a group with someone new
   in it is answered again).

This means a small rule edit or a single reviewer renaming
does not destroy mid-cycle reviewer work.

Outside regeneration, responses also go with what they hang on:
deleting an instrument, uploading over or deleting reviewer or
reviewee rows, or a Settings import, which rebuilds the instruments.
Each is confirm-gated, and the roster and Settings paths also ask for
a response-loss acknowledgement when the session holds responses.
A save that clears group answers asks too, and persists nothing until
the operator agrees. On a group-scoped instrument, a reviewee
boundary-tag edit, any relationship change (create, import, delete,
tag edit, re-point, status switch) or redrawing the instrument's
groups on its card clears every group that gains a member. The page
says how many saved responses would go and offers the save again with a
tick naming that count; a tick for a different count is not accepted
(`spec/assignments.md` "Group-scoped fan-out"). A group that only loses
members, by a move, a split or a delete, keeps its answer and asks
nothing.

**Prepare session**, which runs the regeneration, dry-runs the
reconcile first on a session that has responses; if it would delete
any, on dropped pairs or in groups it adds a member to, the Workflow card asks
the operator to confirm, naming how many responses and pairs would
go, before the actual reconcile runs.
Activate does not regenerate.

Full contract: `spec/assignments.md` "Reconcile + regenerate".

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
  with per-reason exclusion counts as `excluded_<reason>` keys in
  its `counts` payload.
- **Response mutations** — `responses.saved`,
  `responses.submitted`, `responses.cleared`,
  `responses.deleted_all`.
- **Invitation lifecycle** — `invitations.generated`,
  `invitation.sent`, `reminders.sent`, `invitation.opened`,
  `invitation.regenerated` / `invitations.regenerated`, and
  `responses_received.queued` when a submit queues the
  confirmation. There is no per-attempt email event: the outbox
  row is the record of each send ([§11.3](#113-the-outbox)).
- **Workspace admin** — user invite, operator admit / revoke, admin
  promote / demote, user delete, `session.owner_added` /
  `session.owner_removed`.
- **Participant model** — `observer.created` /
  `observers.imported`, `instrument.view_policy_set`,
  `reviewee.results_acknowledged`,
  `session.feature_toggled`.
- **Extract data** — `session.data_shape_saved` /
  `_deleted` / `_extracted`, `session.data_shapes_bundle_extracted`,
  `session.by_instrument_bundle_extracted`,
  `session.participant_tokens_extracted`.
- **Scheduled-event lifecycle** — a scheduled activation writes
  `session.activated` with `context.trigger="scheduled"`, or
  `session.scheduled_activation_skipped` / `_retry` /
  `_failed_persistent`; invites and reminders write
  `session.scheduled_invites_fired` / `_skipped` and
  `session.scheduled_reminders_fired` / `_skipped`.

Admins read a session's audit log via the per-session audit-log
viewer in the admin surface (gated on the admin flag, not on
session ownership). The audit-events CSV is reachable from the
same surface.

---

## 16. Retention, archive, and deletion

RRW offers several distinct mechanisms to retire a session or
remove its data, in increasing order of permanence — from the
reversible Close and Archive states through data / session
deletion and operator-triggered purge.

### 16.1 Close session

From `ready`, the Workflow card's **Close session** moves the session
to `expired` (Closed): every instrument closes, every response is kept,
and Revert to draft reopens it. `spec/lifecycle.md` §2.7 owns it.

### 16.2 Archive

Archive files a session out of the lobby onto the archived-sessions
page and keeps its data, unless it is purged on the way in (§16.5) or
deleted afterwards (§16.3, §16.4); Unarchive returns it to `draft`.
Which control archives from which state is [§6.1](#61-transitions)'s,
and `spec/lifecycle.md` §1 owns the transition.

### 16.3 Delete data

**Delete Data**, on Session Home's Danger Zone, wipes every reviewer
response and keeps the rosters, instruments, assignments and
configuration. It is available in every state but `ready` and is
audited as `responses.deleted_all`. `spec/session_home.md` "3. Danger
Zone card" owns it.

### 16.4 Delete session

**Delete Session**, on the same card, removes the session and every row
that depends on it, the session's audit events included. It is
available in every state but `ready`. `spec/session_home.md` "3. Danger
Zone card" owns the card, and `spec/sessions_overview.md` "Bulk delete"
the lobby's delete.

### 16.5 Operator-triggered purge and archive

**Purge and archive**, from the lobby's expanders or the Extract data
page's **Archive session** card, hard-deletes whichever of the session's
responses, rosters and audit log the operator ticks, then archives what
remains; with nothing ticked it is a plain archive. It applies to
`draft`, `validated` and `expired` sessions. `spec/extract_data.md`
"`Archive session` card" owns the options, and `spec/sessions_overview.md`
"Row affordances" the lobby side.

### 16.6 Per-session retention

Two per-session retention columns exist, but nothing acts on them yet;
the manual archive and the operator-triggered purge cover per-session
retention meanwhile. `spec/settings_inventory.md` §2 lists them.

### 16.7 Scheduled archive and purge

Deferred. The schedule stores an archive offset, but nothing fires it,
and there is no auto-purge. `spec/lifecycle.md` §8 owns the intent.

---

## 17. Permissions and access control

Every gate is enforced server-side. Three apply to operator surfaces —
workspace operator, per-session owner and sys admin — and three to
participant surfaces, each by a case-insensitive email match against an
**active** roster row: reviewer, reviewee with a current visibility
grant ([§4.4](#44-reviewee)), and observer. An invitation token grants
nothing on its own. Destructive actions take an explicit confirmation
and write audit events, reviewer posts act only on the reviewer's own
assignments, and SMTP passwords are encrypted at rest.

`spec/permissions.md` owns the gates, the per-route matrix and the
failure codes, and `docs/security_posture.md` the security audit.

---

## 18. Glossary

- **Assignment** — A row linking `(reviewer, reviewee,
  instrument)`. Materialised by rule generation; not edited
  row by row.
- **Audit event** — An immutable record of one mutation, deleted only by Delete session or a Purge that takes the audit log (§16.4, §16.5).
- **Boundary tag** — A reviewee or pair-context tag picked in Link 3
  of a group-scoped instrument's assignment rule. Members of a group
  share the same value for every boundary tag.
- **Display field** — A read-only context column on an
  instrument, drawn from one of **nine** sources (reviewee name,
  reviewee email, photo / profile link, three reviewee tags, three
  pair-context tags). Two are locked on, seven opt-in; see
  [§5.8](#58-display-field).
- **Display label** — The user-facing string for a lifecycle
  state. `ready` displays as "Activated"; `validated`
  displays as "Validated"; etc. The label vocabulary
  diverges from the enum vocabulary intentionally.
- **Friendly label** — The operator-editable display string
  for one of the nine in-scope tag slots (reviewer / reviewee
  tag 1-3, pair-context 1-3).
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
  collects reviewer input. Carries its own data type and
  validation bounds.
- **Reviewee** — A person being reviewed.
- **Reviewer** — A person giving feedback.
- **RuleSet** — A bundle of rules selecting which
  `(reviewer, reviewee)` pairs an instrument applies to.
- **Self-review** — On an individual-scoped instrument, an
  assignment where the reviewer and the reviewee are the same
  person (matched by email, case-insensitive). On a group-scoped
  instrument, the whole-group rule applies instead — see
  [§5.9](#59-assignment).
- **Session** — One review cycle. The top-level unit.
- **Sys admin** — A workspace-level governance role.
- **Workspace** — The deployment-level container holding the
  operator allowlist and every session.

---

## 19. Reading guide

Every live per-page / per-subsystem spec. Where one of them
disagrees with this document, **the subsystem spec wins** and this
one is corrected to match — this file describes the product, they
describe the surfaces.

The table names **every** live spec, not only the ones this
document happens to cite: it is a map of the corpus for a new
reader, so a spec missing from it is a spec nobody is sent to.

| Subject | Spec |
|---|---|
| Domain model + audit-event detail | `spec/architecture.md` |
| Auth posture + audience model | `spec/audience_and_identity_model.md` |
| CSV import / export contracts | `spec/csv_contracts.md` |
| UI vocabulary (button roles, layout primitives) | `spec/ui_elements.md` |
| Load-bearing domain assumptions | `spec/architecture.md` "Conceptual hierarchy" |
| Email backend options | `spec/email_infra_options.md` |
| Email Template editor (page contract, overrides, merge tags) | `spec/email_template_editor.md` |
| Group-scoped instruments | `spec/instruments.md` (operator-card / model side); `spec/assignments.md` (fan-out / aggregation) |
| Instruments page contract | `spec/instruments.md` |
| Lifecycle states and transitions | `spec/lifecycle.md` |
| Operations-row pages (Validate / Invitations / Responses) | `spec/operations_pages.md` |
| Operator button audit (canonical styles) | `spec/operator_button_audit.md` |
| Operator UI shell + chrome | `spec/operator_ui_concept.md` |
| Permissions / authorization (gates, per-route matrix, role + ownership invariants) | `spec/permissions.md` |
| Retired Previews hub (redirects) | `spec/operations_pages.md` "Page identity" |
| Quick Setup card | `spec/quick_setup_card_spec.md` |
| Reviewer surface — full contract | `spec/reviewer-surface.md` |
| Assignment engine + Assignments page | `spec/assignments.md` |
| Session Home page contract | `spec/session_home.md` |
| Session owners (Create and Session Home Owners cards) | `spec/session_owners.md` |
| Sessions lobby page contract | `spec/sessions_overview.md` |
| Settings inventory (every persisted setting) | `spec/settings_inventory.md` |
| Setup pages shared shape | `spec/setup_pages.md` |
| Reviewer surface sort | `spec/sort_by_reviewee.md` |
| Timezone display | `spec/timezone_display.md` |
| Visual style (general primitives) | `spec/visual_style_general.md` |
| Visual style (RRW-specific) | `spec/visual_style_rrw.md` |
| Workflow card states | `spec/workflow_card.md` |
| Colour tokens (two-tier semantic system) | `spec/color_tokens.md` |
| Extract data workbench + Data shaper | `spec/extract_data.md` |
| Participant model (reviewee / observer contracts) | `spec/participant_model.md` |
| Rehydrate (rebuild a session from extracts) | `spec/rehydrate.md` |
| Role landing pages + audience visibility | `spec/role_landing_and_visibility.md` |
| Role-navigator chip strip | `spec/reviewer-surface.md` "Role-navigator chip strip" |
| Round-trip coverage (export → import) | `spec/roundtrip_coverage.md` |
| Validate page | `spec/validate_page.md` |
| Visibility policy (audience × window grid) | `spec/visibility_policy.md` |
| Cordware host + identity (the process that serves RRW at `/reviewrobin`; who a request is from) | `cordware/spec/host.md`; `cordware/spec/identity.md` |

For what is still to be built, read `guide/todo_master.md`; for
segment-by-segment history, the archived plans indexed in
`guide/archive/README.md`.

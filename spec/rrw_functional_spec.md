# Review Robin Web — Functional Specification

> **Technology-neutral functional contract.** This document
> describes **what** Review Robin Web (RRW) is meant to do, in
> user- and concept-level terms — not **how** it is built.
>
> Implementation details (URLs, code modules, data types, frameworks)
> live in the per-page / per-subsystem specs alongside this file.
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
7. Let the operator **monitor** invitation engagement and response
   completion in real time, both per-reviewer and per-reviewee.
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
    state transition, every email send attempt, and every
    administrative action, exportable as CSV for compliance review.
13. Honour a **single canonical timezone per session** for every
    display surface (operator and reviewer) and every per-session
    CSV extract, with the sys-admin audit-log viewer as the
    deliberate UTC exception.
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
**nested capabilities** (super-admin ⊇ admin ⊇ operator) and a
**config-anchored top tier**:

| Tier | Held as | Added / revoked by |
|---|---|---|
| **Operator** | an operator flag on the user | Admins (and super-admins by nesting) |
| **Admin** | an admin flag on the user | Super-admins only |
| **Super-admin** | *derived*: the email is on the deployment's super-admin list | The deployer's configuration only — never in-app |

Super-admin is **derived, never stored**, so it can't drift from the
configuration or be flipped in-app. A super-admin is given the admin
and operator flags on every sign-in, so every admin and operator gate
passes with no special case. **With no super-admin configured** the top
tier is absent and any admin may grant, promote and demote admins
rather than nobody; a deployed instance logs a warning at startup in
that state.

An **admin** can, on top of operator capability:

- **Manage the workspace allowlist** on the Accounts Management page —
  **invite** a user by email before their first sign-in (as an
  operator, or as an admin), admit / revoke operator status, and
  delete users entirely. A **super-admin** actor is additionally
  required to promote / demote the admin flag or to invite an admin;
  destructive actions refuse when the target is a super-admin.
  Revoking operator status or deleting a user refuses while they still
  own a session (remove them from all sessions first), and demoting or
  deleting the last admin refuses.
- **Bulk-remove a user from all sessions** they appear on
  (departure cleanup).
- **View cross-session diagnostics** — a Sessions Diagnostics
  surface listing every session in the workspace with summary
  state.
- **Read the per-session audit log viewer** and **download the
  audit-events CSV** for any session.

Reading a non-owned session's diagnostics does **not** grant
edit rights. Editing a non-owned
session requires **ownership**: the Diagnostics **"Manage"**
action self-adds the admin as an owner (audited
`session.owner_added`) and opens the session, after which they
act through the normal operator path. There is no shadow
editing — every config change is by a recorded owner.

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

- **Sign in** through institutional identity or through a unique
  invitation link.
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
  session is still `ready`.
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
every instrument at once (Activate opens; the deadline, Close session
or Revert closes).

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

The reviewee's name and email are always present (cannot be
turned off — they are the two locked rows); the other seven
are opt-in.

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
  reviewer is a member of the group being reviewed, and when it
  fires **every assignment in that group is flagged**, not only
  the reviewer's own cell.

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

An invitation is created when the operator (or auto-send
schedule) issues invitations for the session; it is opened when
the reviewer first redeems the link.

### 5.13 Audit event

An immutable record of one mutation or noteworthy read.

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
**Tags** sub-card ([§9.4](#94-session-details-config-card)), and from
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

- **`draft → validated`**: Operator runs Prepare session; its
  validation step passes with no blocking errors.
- **`validated → draft`** (auto-invalidate): Any setup change the
  readiness check reads (roster import, instrument edit, rule change,
  assignment regenerate) automatically flips the session back to
  `draft`. This is silent and invariant; the operator does not opt
  in. The session's own Details, tags and owners, and the
  Assignments page's include toggles, leave it `validated`
  (`spec/lifecycle.md` §2.3).
- **`validated → ready`** (activate): Operator clicks the Workflow
  card's **Activate session**, or a scheduled activation fires.
  Activation is from `validated` only. If warnings exist, the operator
  must explicitly acknowledge them; if blocking errors exist, the
  transition is refused.
- **`ready → draft`** (revert): Operator clicks **Revert to draft**.
  The operator must tick a confirmation checkbox; the reviewer surface
  closes; responses are preserved.
- **`ready → expired`** (Close session): Operator clicks the
  Workflow card's **Close session** button. Every instrument is
  closed and all responses are preserved. From `expired` the
  operator can **Revert to draft** to reopen the session for
  editing (the revert path accepts both `ready` and `expired`).
- **`* → archived`**: The Workflow card offers **Archive session** only in
  `expired`. The lobby's **Purge and archive** (row or bulk
  expander) and the Extract data page's **Archive session** card
  archive from `draft`, `validated` or `expired` — never `ready`,
  which must be reverted first — optionally purging responses,
  rosters and the audit log first ([§16.5](#165-operator-triggered-purge-and-archive)).
  Unarchive returns the session to `draft`.
- **Release-responses window**: open only while the session is
  `expired`, from its Release-from moment until its Release-until
  moment ([§8.3](#83-schedule-fields)). In
  `expired` the Workflow card offers **Release responses** to open
  it now and **Stop releasing responses** to end it.

The reviewer surface is open for writes **only in `ready`**, before
the deadline. Past the deadline, and in `expired`, it still loads
read-only: inputs render disabled and the Save / Submit / Clear
affordances are hidden. In `draft` and
`validated` the reviewer gets the pre-open page instead, and in
`archived` the same page with closed copy
([§10.2](#102-pre-open-and-post-close-behaviour)).

### 6.2 Editable vs locked semantics

In `draft` and `validated`, every setup page is fully editable.
In every other state — `ready`, `expired`, `archived` — the
Reviewers, Reviewees and Relationships pages and Instruments render a
prominent yellow **lock card** explaining why setup is locked and
offering the way out that state has: `ready` and `expired` carry an
inline Revert form, `archived` links the lobby's Unarchive and offers
no control, because Revert is refused from there. **Observers**
locks only in `archived`: its roster stays editable through `ready`
and `expired` ([§9.5](#95-populate-rosters)). All four roster
pages share one lock card; `spec/lifecycle.md` §5 is the contract.

Not *every* setup page: the **Email Template** page renders no
lock card and carries no editable gate at all (deliberate —
`spec/email_template_editor.md` §5), and Assignments /
Invitations / Responses carry none either — the Workflow card is
the lifecycle chrome on those.

While locked, upload affordances and destructive-action cards are
hidden, the row-selection surface is absent rather than inert, and
form controls inside builders — including the friendly-label
editor — are disabled. Every one of those answers the same
editability test as the card, so the explanation and the
controls cannot disagree.

The Session details config card on Session Home is also
lifecycle-gated — its edit mode is only reachable in `draft` /
`validated`; on an active session the Lock toggle renders inert with
a "revert to draft to edit" tooltip, and a direct save is refused
server-side.

### 6.3 Lazy deadline closure

When the deadline passes, the system **lazily closes** each
instrument on the first request that observes the past-deadline
state. Closure turns off each instrument's accepting-responses flag
and emits one `instrument.closed` audit event (reason: deadline) per
instrument. After closure the reviewer surface remains
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
  `403`, pointing the user at their account-debug page.

Reviewers can access only the sessions they are listed in.

### 7.3 Workspace allowlist

The workspace allowlist is the gate between authenticated
identity and operator capability. A user is one of (three-tier
model, [§4.1](#41-system-administrator-three-tier-model)):

- **Not allowlisted** — authenticated but cannot reach operator
  routes; a request for one is redirected (303) to `/me`.
- **Operator** — can create sessions and is
  automatically the owner of sessions they create; can be added
  as co-owner to other operators' sessions.
- **Admin** — operator capability plus workspace
  governance (Accounts Management, Sessions Diagnostics, audit-log
  viewer).
- **Super-admin** — derived from the deployer's configuration;
  the only actor who can promote / demote the admin flag (while one
  is configured), and protected from demotion / deletion in-app.

The allowlist is managed on the Accounts Management page;
promotion, demotion, and removal are audit-logged.

### 7.4 Session ownership

Each session has one or more **operator owners**. Ownership is
managed on Session Home's own **Owners** card (shown to the session's
owners, in any session state); the creator can also name
co-owners on Create's **Owners** card, saved with the session. An
owner can add another allowlisted operator as a co-owner and
remove a co-owner, themselves included; the last owner cannot be
removed. Each add or remove saves at once and is audited as
`session.owner_added` / `session.owner_removed`. The card renders
locked, and **Unlock** enables its controls — a guard against
accidental edits, not a permission. Per-session add and remove are
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
(Start ≤ deadline ≤ Release-from < Release-until) and an
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

Each session carries a **self-reviews active** flag. When true,
self-review pairs (reviewer reviewing themselves on a given
instrument) participate in the review surface; when false, they
are inactive in bulk. Per-pair include overrides apply
post-flip. The flag has no editor; it is set by the Settings CSV
import or Duplicate.

Separately, each instrument's rule can **exclude self-reviews
outright**: the **Self reviews** checkbox under Link 3 of the
instrument's Band 1 ([§9.6](#96-configure-instruments)), off by
default and shown only once every Link is set. Its wording follows
the unit of review — on a group-scoped instrument it excludes every
group the reviewer belongs to. It takes effect at the next Generate:
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
([§5.17](#517-feature-toggles)) sit on the config card's **User
interface settings** sub-card.

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
expander** for single-row actions (rename and deadline adjust while
the session is `draft` or `validated`, read-only otherwise; tag edit
in any state; duplicate, purge and archive, delete). Multiple
tickings open the bulk-action variant of the expander.

The lobby supports:

- **Sort** on any column header (cookie-persisted).
- **Free-text search** filtering the visible rows.
- **Tag-filter strip** with an AND/OR mode chip and a clickable
  chip per tag (LocalStorage-persisted).
- **Bulk delete** of selected sessions (confirm-gated).
- **Purge and archive** of one or more selected sessions in
  `draft`, `validated` or `expired` (an activated session is
  skipped), optionally purging responses, rosters and the audit log
  first; with nothing ticked to purge it is a plain archive
  ([§16.5](#165-operator-triggered-purge-and-archive)).
- **Per-row clone** in two flavours: **Duplicate** (the setup plus
  every roster: reviewers, reviewees, relationships and observers,
  with their cohort rules) and **Duplicate settings only** (metadata,
  email templates, instruments, rules, friendly labels, tags and saved
  data shapes; no rosters). Neither copies responses, assignments,
  invitations or audit history: the clone is a fresh `draft` owned
  by the operator who cloned it.

The **archived-sessions child page** (`/operator/sessions/archived`)
lists sessions in `archived` state with the lobby's table, sort, search
and tag-filter affordances. Its expander does **not** mirror the
lobby's: there is one template, the bulk one, and it opens on any
selection of one or more rows rather than switching on the count. It
offers Unselect all, Unarchive, Delete (gated behind "Yes, delete"),
and a **Download button that is disabled** — a placeholder with no route
behind it. See `spec/sessions_overview.md` "Row affordances" for the
selection and bracket behaviour, which is recorded there because this
page has no section of its own.

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
Clone action lands on Session Home the same way.

### 9.3 Session Home

The Session Home page (`/operator/sessions/{id}`) is the
operator's primary working surface for a session. Session config
is both **displayed and edited** here ([§9.4](#94-session-details-config-card)).
Top → bottom:

- **Workflow card** (full width) — the lifecycle-driven card
  explaining the current state and offering the single
  most-important next action(s). The card frame is constant (H2
  "Workflow", blue-framed, height grows to fit); the
  contents differ across the lifecycle states (see
  [§9.8](#98-validation-and-activation)).
- **Session details card** (full width, below Workflow) — every
  config field, displayed and edited in place
  ([§9.4](#94-session-details-config-card)).
- **Quick Setup card** (bottom left) — a
  bulk-import surface with one CSV upload affordance per roster /
  settings slot (Reviewers / Reviewees / Relationships / Settings,
  plus an Observers slot when the Observers toggle is on) and one
  **Submit** button that runs the staged imports in dependency order.
  It is available only while the session is `draft` and holds no
  responses: then it loads locked, and **Unlock** enables it;
  otherwise it stays locked with no Unlock.
- **Danger Zone card** (bottom right) —
  **Delete Data** (wipes every reviewer response, preserves setup)
  and **Delete Session** (removes the session entirely). Both are
  confirm-gated, live in every state but `ready`, and
  visible-but-disabled in `ready`, route-enforced server-side.
- **Owners card**, stacked above Danger Zone — the session's own
  owner set, editable in every session state, guarded by its own
  Lock / Unlock against accidental edits. `spec/session_owners.md` carries the full contract.

The round-trip **setup CSV download tiles** are not on Session
Home: they live on the Operations-strip **Extract data** tab (see
[§9.12](#912-extract-data)).

### 9.4 Session details config card

The Session details card on Session Home is the only surface for
session config; there is no separate Edit page, and an old Edit link
redirects to the card in edit mode.

- **Display ↔ edit swap.** Each field holds one slot — a read-only
  value in display mode, its input in edit mode. Edit mode lives in
  the page address, and is reachable only while the session is
  editable (`draft` / `validated`), so a stale link on an active
  session degrades to display mode.
- **Fields.** Name / Code, Description, Help contact, Timezone,
  and the four schedule datetimes (Start / End / Release-from /
  Release-until) plus the Send-invites and Send-reminders offset
  lists — each offset shown in display mode next to its resolved
  send datetime.
- **Owners is a card of its own**, not one of this card's sub-cards
  — see §9.3 and `spec/session_owners.md`.
- **User interface settings sub-card** — the Relationships and
  Observers checkboxes ([§5.17](#517-feature-toggles)), each
  lock-on-data.
- **Tags sub-card** — the session's tags as pills, like the
  sessions lobby's, in display mode; one text box in edit mode, saved with the card's
  **Save** (emptying the box clears them). Tags are stored lower
  case.
- **Save** returns to Home in display mode. Editing metadata is
  non-destructive (never touches assignments or responses), so
  there is no response-loss acknowledgement gate, and it leaves a
  `validated` session `validated`.

### 9.5 Populate rosters

Up to four Setup pages share an identical chrome shape: Reviewers,
Reviewees, **Relationships** and **Observers** (each shown by its
toggle, [§5.17](#517-feature-toggles)).

Each page offers the following. **Observers is the exception on some
of these points**, flagged inline; `spec/setup_pages.md`
§ *Observers page* § *Body layout* lists them in one place.

- **Friendly-label editor card** — inline editors for the
  display labels of this entity's **tag slots only**: an identity
  or photo slot is refused, and its built-in default always renders
  (see [§8.5](#85-friendly-labels)). The editor answers the same
  editability gate as the rest of the page. **Not on Observers**,
  which has one fixed tag slot and no editor.
- **Preview table** — every row in the roster (paginated by
  search + filter), with sortable headers (**not on Observers**,
  which orders by id), column-visibility toggles for the three
  optional tag columns and the photo-link column (**not on
  Observers**, whose one fixed slot has nothing to toggle), and a
  trailing **Updated** timestamp. Its
  card opens with a **two-pane toolbar** carrying the search +
  status-filter strip, `Clear`, `Add new` and `Search`; the
  leftmost checkbox column drives an injected **row expander**
  holding the selection-driven actions (Edit, Inactivate,
  Activate, Delete), the selected count (`N of M selected`,
  where M is the rendered window) and the delete confirmation.
  In Edit / Add mode the row's cells become inputs and a Save +
  Cancel pair renders in an expander bar beneath it, and the
  toolbar strip locks with `Add new` and `Search` disabled. The
  preview-count line sits in the toolbar's left pane and is
  shared by every preview page.
- **Upload card** and **Danger Zone card** — CSV file input +
  Upload submit, replacing the roster wholesale on success; and
  Delete All, confirm-gated, wiping it. Both live in the roster
  card's **Unlock panel** above the table, alongside the
  friendly-label editor on the three pages that have one; on
  Observers the panel holds these two alone, mirrored left-to-right.
  **Nothing renders below the table.**

All four pages share this shape. `spec/setup_pages.md` § *The roster
card and the Unlock panel* and § *Roster controls and their route
contracts* are authoritative. **Three of the four share their gates
too; Observers does not**, and the paragraph below is that exception.

**Observers differs in one further respect, and it is a behavior
change rather than a layout one:** its roster stays editable through
`ready` and `expired`, closing only at `archived`. Observers never
appear in assignments and produce no responses, so freezing their
roster at Activate protects nothing, while refining who sees what
mid-session is a legitimate flow. It is the only roster page whose
mutating surface outlives the editable states; `spec/lifecycle.md` §5 states
the exception and governs any second one. Its expander also carries a
surface no other roster page has — the per-observer **cohort match
rule** builder, which decides what that observer sees.

The Reviewers page collects: name, email, tag 1 / 2 / 3, photo
link, status.
The Reviewees page collects: name, email or identifier, tag 1 /
2 / 3, photo link, status.
The Relationships page collects: reviewer email, reviewee email,
pair-context tag 1 / 2 / 3, status.
The Observers page collects: email, display name, a single tag,
the per-observer cohort match rule, status — no friendly-label
editor (single-tag observers don't need one).

CSV import is **wipe-and-replace**: on each upload the whole
existing roster is dropped and the new file's rows take its
place. Validation errors block the import wholesale — partial
loads do not happen. Replacing a non-empty roster takes a
replace confirmation; on Reviewers and Reviewees, whose rows carry
assignments, it also takes a response-loss acknowledgement when the
session holds responses, since the dropped rows take their
responses with them ([§14](#14-reconciling-regeneration)).

### 9.6 Configure instruments

The Instruments page (`/operator/sessions/{id}/instruments`)
is a consolidated per-instrument editor.

**The session status card** sits at the top beside the guidance
card, **half-width**. It carries a one-line
pill row (session deadline, `N accepting`, `M not accepting`) and
the **Expand all / Collapse all instruments** buttons, which act on
the page rather than on any instrument.

Accepting follows the lifecycle: Activate opens every instrument,
and the deadline, Close session or Revert closes them all. What a
participant sees once an instrument closes follows its visibility
policy. `spec/instruments.md` owns that contract and states it in
full.

Below the status card, one **per-instrument card** per instrument,
each collapsible, with a locked/unlocked edit state (at
most one instrument unlocked at a time). Its stripes:

- **Identity** (in the card's always-visible header) — the reviewer-facing
  short label (editable inline when unlocked), Set-up / Not-set-up
  and Locked / Unlocked pills, and drag handle for reorder.
- **Instrument assignment rule** (Band 1) — three "Links" of equal
  width: Link 1 *Who does the review*, Link 2 *Who is being
  reviewed*, Link 3 *Unit of review* (Individual vs Group). Each
  Link cycles a `Not set → All → Filter/Group` pill. A **"Not set"
  safety gate** requires the operator to deliberately touch every
  Link before the instrument reads as configured, so the implicit
  Full Matrix default can't ship silently. When Link 3 is Group, it
  picks the **boundary tags** — reviewee and pair-context tags whose
  shared values define a group ([§10.4](#104-group-scoped-review-surface)).
  Below Link 3, once every Link is set, sits the **Self reviews**
  exclusion checkbox ([§8.6](#86-self-review-behaviour)). (The card's
  heading is **Instrument assignment rule**; "Band 1" is this spec's
  shorthand for it. It is the only place a rule is authored.)
- **Band 2 — Preview** — a live preview of one sample reviewee row
  (display fields, then response fields), with
  drag-resizable column widths and the instrument description
  (lock-driven edit swap). Band 2 also carries the "Who can see what
  you wrote" card: locked, the reviewer's read-only view of the
  visibility policy; unlocked, the **per-audience visibility-policy
  editor** — a chip grid (You (reviewer) / Reviewees / Observers ×
  Session-ongoing / Responses-released) picking, per audience per
  window, among the modes that cell allows
  (`spec/visibility_policy.md` §3.1; see
  [§5.16](#516-visibility-policy)).
- **Band 3 — Display and response fields** — two tables, 15% and
  85% of the band. The left picks and orders the display fields
  (Reviewee Name / Email always shown; the populated tag sources
  opt-in). The right is the response-field table, one row per field:
  an Active checkbox (per-field surface visibility), Name, **Type**
  (String / Integer / Decimal / List, plus a Quick-fill group of List
  presets), inline bounds (min / max / step, or the list options),
  Required toggle, help-text toggle, ▲ ▼ for order, and a fork control
  that turns an Integer, Decimal or List field into the parent of a
  **branch** over the fields directly beneath it
  ([§5.7](#57-response-field)). Type + bounds lock once the
  field has saved responses. Both tables
  show in the preview at once and persist with the card's Save
  (`spec/instruments.md`).
- **Action row** — Save / Cancel (edit only) / Replicate / Delete
  (confirm-gated; blocked when only one instrument) / **+Instrument**
  / **+Page break** / Lock-Unlock. One bulk Save commits identity,
  Band 1, Band 3, visibility policies, and column widths together.

### 9.7 Configure assignments

The Assignments page (`/operator/sessions/{id}/assignments`) is
on the Operations row of the chrome. It carries:

- **Per-instrument status card** — one block per instrument,
  showing type (Individual / Group), generated pair count (with a
  `stale` pill when the current rule + roster would produce a
  different set), group count, self-review count + per-instrument
  self-review toggle (locked outside `draft` / `validated`), included
  count, and a per-instrument "Show in preview table" filter
  checkbox.
- **Assignments preview table** — every materialised pair,
  with reviewer identity + tag columns, reviewee identity +
  tag columns, pair-context tag columns, an Include yes / no pill,
  Instrument column, sortable headers, column-visibility
  toggles. Its card opens with the same **two-pane toolbar**
  the roster pages carry: chips, pager and preview-count line
  left; the filter strip — status filter, a Search-by dropdown
  (All / Reviewers / Reviewees), a search box with typeahead
  suggestions, `Clear`, `Search` — right, in that order.
- **Row expander** — ticking rows injects a panel beneath the
  selection carrying the selected count and the
  selection-driven bulk **Inactivate** / **Activate** —
  whichever is actionable for the selection, so one where every
  ticked pair is the same way and both where it is mixed.
  **Self-review assignments are flipped
  active/inactive** per instrument from the status card's Self
  review column; the session's self-reviews-active flag seeds the
  include value at generation time and this column overrides
  it after (see [§8.6](#86-self-review-behaviour)). An instrument
  whose rule excludes self-reviews has none to flip, and the column
  reads *Excluded by rule*.

Assignments are not edited row by row. The operator changes
which pairs exist by changing the rule (in the **Instrument
assignment rule** card / Band 1 on the Instruments page — the
only place a rule is authored) or the
rosters and **regenerating** via the Workflow card's Prepare
action. Generation runs a per-instrument rule pass over the
session's reviewer × reviewee matrix; an instrument with no
stored rule uses the synthetic Full Matrix. See
[§14](#14-reconciling-regeneration) for what regeneration
preserves.

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

The Invitations page (`/operator/sessions/{id}/invitations`) is
a reviewer-centric Operations-row tab.

- **Info card** at the top, full width — lifecycle
  counters (eligible reviewers, invitations created / sent /
  pending, reminders sent / pending, completed / incomplete
  reviews).
- **Two-pane table toolbar** — the table card opens with it.
  Left pane: column chips, pager cluster, preview-count line.
  Right pane: the filter strip — Status dropdown + free-text
  search + Clear / **`Search`**.
- **Invitations table** — one row per reviewer carrying:
  reviewer name + email, email status (sent / queued / not
  sent), email-sent timestamp, per-reviewer engagement
  (opened / first-response / submitted), required-fields-
  filled count, last-reminder timestamp, per-row Send /
  Send-reminder / Regenerate actions (lifecycle-gated).

The **auto-send captions** — how the next scheduled invitation and
reminder sends will resolve given the current schedule, including any
skip reason — are not on this page's body: they sit in the Workflow
card's right-hand column, which this page carries as chrome
([§11.4](#114-scheduling--auto-send)).

The chrome's session top-nav bar carries a **four-state
Invitations pill** — `Not created`, `Not sent`, `Partially
sent`, `All sent` — reflecting the session-wide invitation
status at a glance. The four states are what the pill is for: a
single present-or-absent indicator cannot distinguish "created but
unsent" from "partially sent".

### 9.10 Monitor responses

The Responses page (`/operator/sessions/{id}/responses`) is a
reviewee-centric Operations-row tab.

- **Info card**, full width — counts of reviewees with
  responses, without responses, total reviewees.
- **Two-pane table toolbar** — the same shape as Invitations':
  chips, pager and count line left; the filter strip (search +
  status filter, Clear / **`Search`**) right.
- **Responses table** — one row per reviewee, with name +
  email, coverage status (complete / adequate / at risk /
  no responses), reviewers-completed count over total assigned, last-
  response timestamp.

A per-row drill-in opens a per-reviewee detail view showing
each reviewer's status for that reviewee.

The Responses page is monitoring-only; per-cell response
content is not readable here — that channel is the Extract
Data download.

### 9.11 Reviewer and email previews

The Invitations per-reviewer drill-in carries the three rendered email
previews and an **Open reviewer surface** link. The latter opens an inert
operator view of that reviewer's production surface in a new tab, using the
same template and context path as the live surface. There is no separate
Previews page; its old URL permanently redirects to Invitations
(`spec/operations_pages.md` "Page identity").

### 9.12 Extract data

Extraction splits across two surfaces:

**Extract Setup card** (the round-trip / porting CSVs) — on the
**Extract data** Operations tab, not on Session Home.
It offers per-entity download tiles — Reviewers, Reviewees,
Relationships (always shown, whatever the Relationships toggle says),
Settings, and an Observers tile when the Observers toggle is on —
plus a Zip-all footer bundling the setup CSVs as
`{code}_setup.zip`. Each tile greys its Download button when its roster is empty; Settings is
always clickable. Filenames follow `{session_code}_{kind}.csv`.

**Extract data page** (`/operator/sessions/{id}/extract-data`) —
the Operations-strip workbench for **shaping response data** for
offline analysis. It is deliberately not an in-app analysis tool
(no charts, no pivots); it cuts the response data along the
dimension the operator asks for. Cards:

- **Extract all data** — a top-level `Zip all`
  (`{code}_responses.zip`): always the unified responses file, plus
  each other card's files, as that card is configured, for each of
  its chips that is on.
- **By instrument** — one wide CSV per instrument (rows =
  reviewer × reviewee pairs, columns = response fields
  side-by-side) for cross-reviewer comparison.
- **Reviewer / Reviewee response metadata** — per-entity activity
  rollups (assigned / answered counts + per-field aggregates by
  data type), with a Self-review handling chip (`Include self` /
  `Exclude self` / `Both`).
- **Data shaper** — a generalised builder: pick axis (reviewer /
  reviewee), instrument / response-field scope, identification and
  aggregate columns via chips, see a live preview row, save the
  shape under a name, and download its CSV.
- **Token keys** (when the Observers toggle is on) — the
  operator-side deanonymization key (Role / Name / Email / Token)
  mapping each participant to the per-session opaque token used in
  Anonymized observer downloads.
- **Archive session** — the lobby's purge-and-archive on one
  session: archive it from `draft`, `validated` or `expired`,
  optionally purging responses, rosters and the audit log first, then
  land on the archived-sessions page
  ([§16.5](#165-operator-triggered-purge-and-archive)). Inert in
  `ready` and once archived.

Every download emits an audit event. The **audit-events CSV**
lives behind the admin gate, not here. **Rehydrate** — rebuilding a
session from a complete extract set — is built but switched off by
deployment setting, so it is not exposed to operators: its pages are
not found and the lobby shows no button (`spec/rehydrate.md`).

Full export contracts: see [§12](#12-data-export).

### 9.13 Operator settings

The operator's Settings page (`/operator/settings`) carries:

- **Email send (SMTP)** — host, port, from-email / username,
  password (encrypted at rest), display name, encryption mode
  (`starttls` or `ssl`, the latter implicit TLS). Every field but
  display name is required: until all are set, email reads as not
  configured.
- **Date & time** — the operator's default display timezone (IANA
  typeahead with a worked-example live preview).
- **Clear all settings** — wipes the SMTP fields on the account.

The cards sit in two columns: Email send (SMTP) alone
on the left, its "Bring your own SMTP" intro (shown only until an SMTP
host is saved) below its header and above its fields; Date & time and
Clear all settings stacked on the right.

### 9.14 Sys admin surface

The sys-admin surface is workspace-scoped and reachable from
the chrome's plain **Admin** link, shown to sys admins beside
Settings, Guide and About. It carries:

- **Accounts Management** — workspace allowlist with per-row
  promote / demote / delete actions, a bulk toolbar, and an **Invite
  by email** card that pre-seeds a user before their first sign-in,
  as an operator or as an admin; the refusals are
  [§4.1](#41-system-administrator-three-tier-model)'s.
- **Sessions Diagnostics** — cross-workspace listing of every
  session with summary state. Its **"Manage"** row action self-adds
  the sys-admin as an owner (audited) and opens the session — the
  explicit elevation door, since editing a non-owned session requires
  ownership. Below it, a read-only **Visibility grid audit** lists
  every stored visibility cell in the workspace that carries a mode
  its audience and window do not allow — one the instrument card's
  editor and the Settings import both refuse — and marks those a
  participant can reach now. Clearing one is the owning operator's
  job, in that instrument's visibility editor.
- **Per-session Outbox viewer** — the session's email outbox
  ([§11.3](#113-the-outbox)).
- **Per-session Audit Log viewer** — filter strip + pretty-
  printed detail expander over the session's audit-events
  history.
- **Audit-events CSV download** per session.

There is no per-session owner management here: owners are added and
removed on Session Home's Owners card by the session's own owners
([§7.4](#74-session-ownership)), and a non-owner sys-admin's only
per-session door is the self-add. Accounts Management's **remove
from all sessions** is the one bulk exception.

### 9.15 Guide, About and theme

The operator chrome and the participant top bar carry **Guide** and
**About** links, each carrying where the viewer came from so the
page can link back, and a **Light / Dark** theme toggle.
The standalone error page has no chrome. Neither link renders on its
own page or on the account-debug page, and the Guide link is also omitted
for a viewer the Guide has nothing for.

- **`/guide`** is the in-app documentation: one page of sections
  addressed to operators, reviewers, observers and reviewees. A viewer
  sees only the sections for the roles they hold — operator from the
  workspace allowlist (sys-admins included), the participant roles
  from their roster rows
  (a reviewee only while a visibility grant resolves). It grants
  nothing and holds nothing privileged. A viewer who holds no role is
  redirected (303) to `/about`, and the chrome omits their Guide link.
- **`/about`** is identity and access: what the software is, who is
  signed in, and whom to contact for operator access. Any signed-in
  user can open it.
- **Theme** is a per-browser display preference kept in the
  browser's local storage, applied before first paint. It is never stored on
  the server and does not follow the operating system's setting;
  `spec/settings_inventory.md` lists it.

---

## 10. Reviewer experience

### 10.1 Access

A reviewer reaches their work through one of two entry points
(see [§7.2](#72-reviewer-identity)):

- The unique invitation link in the email they received.
- A direct link to the session (e.g., bookmarked from a prior
  visit) — sign-in match required.

After sign-in, the reviewer lands on:

- The **`/me` dashboard** — a cross-role participant lobby
  listing **every session the signed-in
  identity touches in any participant role** (reviewer / reviewee
  / observer). One table row per session carries the session name
  with per-role pills beneath it, Start / End / Timezone columns,
  a Session-status pill, and a Reviewer-status pill. Between End
  and Timezone sit **View responses** and **Until** columns, which
  are placeholders: every row renders an em dash in both. The
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

If the session is in `draft` or `validated` — not yet accepting
responses, or reverted to draft — the reviewer sees a
**pre-open landing card** explaining the session is not open, naming
the deadline, and offering a return link to the dashboard. In
`archived` the same card says the review has closed, with no
deadline. No review form renders.

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

The review surface (`/me/sessions/{id}/{page}`) is a
**dense tabular form** — one row per reviewee (or one row per
group, for group-scoped instruments) and one column per
display field plus one column per response field.

**Pages.** The operator's page breaks divide the
session's instruments into numbered pages, each holding one or more
instruments; a session without breaks is one page. Each page is its
own server-rendered URL, and a multi-page session carries **Prev /
Page N of M / Next** links that load the adjacent page from the
server; there is no per-instrument page button. Only the current
page's inputs are on screen: other pages' values live in the
database from their own Saves, and unsaved typing on the current page
is dropped on navigating away.

**Who can see what you wrote.** Above each instrument's table a
read-only card titled *Who can see what you wrote (other than admin)*
shows, for **You** and for **Reviewees**, the mode the instrument's
visibility policy grants while the session is ongoing and once
responses are released — Raw responses, Anonymized responses,
Anonymized summaries, or — for none. Observers are not listed. It is
the reviewer's view of the policy the operator sets on the same card,
unlocked, in Band 2 ([§9.6](#96-configure-instruments),
`spec/visibility_policy.md`).

**Cell rendering** is driven by each response field's own
data type and inline bounds:

- **String** fields render as a one-line text box (length cap
  ≤ 100) or a multi-line text area (cap > 100, initial height
  derived from the length cap and column width).
- **Integer** / **Decimal** fields render as a number box
  with min / max / step from the field's bounds.
- **List** fields render as a drop-down with an empty leading
  option plus the field's list options.

Display columns render as plain text (or as a link for
photo / profile-link sources).

**Branching** — a governed response field renders muted and
disabled while its branch is closed, and is required only while §5.7
says so; it follows the parent live as the reviewer edits it, and the
server applies the same rule on Save, deleting a governed answer whose
branch is closed, whatever the page shows
(`spec/reviewer-surface.md` § "Branching between response fields").

**Sortability** — every Reviewee, display-field and response-field
column header is clickable to sort the rows by that column alone (a
group-scoped instrument's **Group** column and the trailing status
column are not sortable); Shift-click adds
a secondary priority, up to three. There is no Reset link:
clearing the sort returns to the operator-configured default
(`spec/sort_by_reviewee.md`). The reviewer's choices persist in a
per-(browser, session, instrument) cookie.

**Self-review** — when the reviewer's own email matches a
reviewee row in the session (case-insensitive), the reviewer
sees a row for themselves. The reviewer surface marks the row
visually but does not block writes. Whether such a row is active
at all is the operator's: the session's self-reviews-active flag
seeds it at generation, and the **Assignments page flips
self-review assignments active/inactive per instrument**
thereafter (see [§9.7](#97-configure-assignments)).

### 10.4 Group-scoped review surface

For an instrument the operator has set to **group-scoped**, the
surface presents **one row per group** instead of one row per
reviewee. Groups are computed by partitioning the reviewer's
rule-eligible universe by the **boundary tags** picked in Link 3 of
the instrument's assignment rule ([§9.6](#96-configure-instruments))
— reviewee and pair-context tags; reviewees sharing every boundary
value form one group.

The group row's identity column is a **composed display**: on one
line, the values of the instrument's visible reviewee-tag display
fields (or, with none visible, the group's boundary values); on the
next, when the reviewee-name display field is visible, the first ten
member names, with a "+N more" overflow indicator. Reviewer writes to
a group cell **fan out** to one response row per group member; reads
aggregate back to one row per instrument per group.

Missing-required and validation errors surface once per group,
not once per member.

### 10.5 Saving

The reviewer surface uses an **explicit Save** model. **Save** is
always enabled — there is no dirty tracking — and persists the
current page's inputs, then reloads that page; saving with no edits
is a harmless no-op. If a value is invalid, Save answers 400 and
re-renders the page in place with a warning card and the typed value
kept; the valid values still save. **Cancel** reloads the page from
its last-saved values, dropping unsaved typing. There is no unsaved-changes warning
on leaving a page.

Clearing a cell to empty deletes that response row. There is
no per-cell autosave today; this is an intentional simple
contract.

### 10.6 Submission

**Submit** is a one-click session-wide action available on
every page. On click:

1. The current page's inputs are saved (implicit save); other
   pages contribute what their own Saves stored.
2. Required-field validation runs across every instrument's
   every assigned row.
3. If any required cell is empty, the submit is blocked and the
   page Submit was pressed on re-renders with a full-width
   "Required fields missing." card enumerating the gaps row-by-row
   (`#N Label: Reviewee X — field Y`, the instrument named as its
   status pill names it). No partial submit happens.
4. If validation passes, every populated cell receives a
   submitted-at timestamp in one atomic transaction; per-
   page status pills flip to `submitted` and each row's trailing
   status column shows a complete (✓) icon where its required
   fields are filled — an icon only, with no per-row
   timestamp. The reviewer lands on the summary page once every
   assignment is submitted, otherwise back on page 1.

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

### 10.8 Reviewer's own CSV download and summary page

Once the session has fully submitted (every required cell
populated and stamped), the reviewer sees a read-only
**summary page** (`/me/sessions/{id}/summary`) — one section per
instrument they responded on and may read now (each instrument's
visibility policy decides; nothing once archived), a submitted-on
timestamp, a
**Recall my submission** control (rolls the submission back to
draft while the session is still `ready`), and a **Download my
responses (CSV)** button (when any section shows) emitting `{code}_my_responses.csv` (same
21-column shape as the operator Responses extract, narrowed to
this reviewer's rows).

### 10.9 Reviewee results surface

An email-identified reviewee reaches
`/me/sessions/{id}/results` through the two checks of
[§4.4](#44-reviewee) — the roster check plus a currently-resolving
visibility grant; without one the page answers 404. The body is
per-instrument sections — one section per instrument whose reviewee
visibility policy resolves to a mode and that has an included
assignment to this
reviewee — rendering the responses collected *about this
reviewee* in the policy's mode:

- **Raw** — one row per reviewer with an included assignment to this
  reviewee, identified; a reviewer who has not submitted shows empty
  value cells.
- **Anonymized** — the same per-row table with every
  identification cell stripped to a muted em-dash.
- **Summarized** — one aggregate row per instrument, with
  per-data-type stats (Integer/Decimal: average / median / min /
  max / N; List: per-choice frequency; String: total + average
  length).

A reviewee grant is after-release only: outside the open
response-release window no section renders, and nothing opens while
the session is ongoing. An **Acknowledge card** at the foot lets the
reviewee confirm they've seen their results — a one-shot, idempotent
gesture that records when, and emits
`reviewee.results_acknowledged`.

### 10.10 Observer collation surface

An observer reaches `/me/sessions/{id}/collation` through an
active observer row matching their email, case-insensitively; unlike
the reviewee surface, the page needs no current grant to load. The
body is a per-instrument
3-row collation table scoped to the observer's **cohort**: a
distinct-reviewer headcount + shared aggregate, a
distinct-reviewee headcount + the same aggregate, and a
conditional per-instrument **Download CSV** button. Identification
mode follows the per-instrument observer visibility policy (Raw /
Anonymized rows / Anonymized summaries); Anonymized downloads
substitute per-session opaque tokens for names (reversible via the
operator's Extract-data Token keys card). Each instrument renders
only while its observer policy resolves a mode for the current
window: its session-ongoing mode (Summarized, or nothing) while the
session is `ready`, and its responses-released mode while it is
`expired` and inside the release window; nothing once archived.

---

## 11. Invitations and email

The invitation and email subsystem is a central functional
contract of RRW, described here in full. One leg — handing a
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

Each kind of message — invitation, reminder, responses-
received — is rendered from the session's operator-editable
template by substituting per-reviewer merge fields:

- **Invitation**: `$reviewer_name`, `$session_name`,
  `$deadline`, `$help_contact`, `$invite_url`.
- **Reminder**: `$reviewer_name`, `$session_name`,
  `$deadline`, `$help_contact`, `$invite_url` — the same set
  as the invitation; the default reminder body repeats the
  sign-in link.
- **Responses received**: `$reviewer_name`, `$session_name`,
  `$deadline`, `$help_contact`, `$submitted_at`.

An unrecognised merge tag is left in the text verbatim — never
blanked, never an error — so a typo cannot fail a send. Subjects
are capped at 255 characters by the editor; bodies carry no
length limit. Full editor contract: `spec/email_template_editor.md`.

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
  for sessions that are `validated` or `ready` and have
  invitations created, sending every invitation not yet sent whose
  reviewer is still eligible.
- **Auto-send reminders** fires at each reminder-offset moment
  for sessions that are `ready`, before their deadline, with
  invitations created, sending to every reviewer who has an
  invitation and has not submitted. A reviewer whose invitation was
  never sent, or whose link a Regenerate has since rotated, is sent
  a fresh invitation in place of the reminder ([§11.1](#111-what-an-invitation-is)).

Per-offset audit events (`session.scheduled_invites_fired`,
`session.scheduled_reminders_fired`, plus per-skip events with
reasons) record every firing. A per-reviewer, per-offset key on
the outbox row prevents duplicate reminders to the same reviewer for
the same offset.

The Session details config card previews every resolved fire
moment inline next to its offset; the Workflow card's right-hand
column, on Session Home and every Operations-row page, carries the
same information as auto-send captions.

### 11.5 Backend options

The dispatch leg of the subsystem is **pluggable**: one transport
seam, with one concrete backend selected per deployment.

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

- **Reviewers.csv** — `ReviewerName, ReviewerEmail,
  ReviewerTag1, ReviewerTag2, ReviewerTag3, ProfileLink, Status`.
  Active rows first, then by name, then by email.
- **Reviewees.csv** — `RevieweeName, RevieweeEmail,
  RevieweeTag1, RevieweeTag2, RevieweeTag3, ProfileLink, Status`.
  Same sort discipline.
- **Relationships.csv** — `ReviewerEmail, RevieweeEmail,
  PairContextTag1, PairContextTag2, PairContextTag3, Status`.
  Active rows first, by reviewer email, then by reviewee
  identifier. Not gated on the Relationships toggle.
- **Observers.csv** — `ObserverEmail, ObserverName, ObserverTag1,
  Status, CohortRule`. Conditional on the Observers toggle.
- **Settings.csv** — three-column `field, value, data_type`
  format spanning session-level fields, email templates,
  instruments, session RuleSets, data shapes, and session tags.
  Round-trips perfectly back through the Settings import path.
  It carries **no** response-type section and **no**
  friendly-labels section — tag friendly labels ride the roster
  CSV headers instead — and `rtds[...]` / `field_labels.*` rows in
  an older bundle are silently ignored on import rather than
  rejected.

### 12.3 Responses extract

A 21-column long-format file, in this order:
`ReviewerName, ReviewerEmail, ReviewerTag1/2/3, RevieweeName,
RevieweeEmail, RevieweeTag1/2/3, InstrumentName,
InstrumentShortLabel, FieldKey, FieldLabel, ResponseType,
Value, SelfReview, SavedAt, SubmittedAt, Version,
InstrumentFlavour`. A per-instrument preamble at the top of
the file lists each instrument's field dictionary.

`RevieweeEmail` deliberately mirrors the roster CSV header even
though the value is the reviewee's email or other identifier. The
column names and their positions are both part of the contract
[§12.5](#125-round-trip-stability) promises, and both break a
downstream consumer if they move.

Group-scoped instruments collapse one row per group rather
than per member. The file streams to the operator without
buffering the full dataset in memory.

### 12.4 Audit-events file

`{code}_audit_log.csv` —
`EventType, Severity, Summary, ActorEmail, CorrelationId,
CreatedAt, DetailJson`, with `CreatedAt` in UTC. Reached from the sys-admin
audit-log viewer; not surfaced on the operator-facing Extract
Data card.

### 12.5 Round-trip stability

Four of the five roster pairs (Reviewers, Reviewees, Relationships,
Settings) are designed for **byte-stable round trip** — an
export-then-import cycle does not perturb the session's
config. Deterministic row order, deterministic field order,
empty-string handling for missing optional cells,
vocabulary normalisation, and seeded entries omitted from
the Settings extract together guarantee this. Observers
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
   responses.

This means a small rule edit or a single reviewer renaming
does not destroy mid-cycle reviewer work.

Outside regeneration, responses also go with what they hang on:
deleting an instrument, uploading over or deleting reviewer or
reviewee rows, or a Settings import, which rebuilds the instruments.
Each is confirm-gated, and the roster and Settings paths also ask for
a response-loss acknowledgement when the session holds responses.
One loss outside regeneration asks for neither. On a group-scoped
instrument, a reviewee boundary-tag edit or any relationship change
(create, import, delete, tag edit, re-point, status switch) that
moves a pair to another group deletes the old group's answer copy on
that row at once; the row takes its new group's answer when one
exists (`spec/assignments.md` "Group-scoped fan-out").

**Prepare session**, which runs the regeneration, dry-runs the
reconcile first on a session that has responses; if it would delete
any, the Workflow card asks the operator to confirm, naming how many
responses and pairs would go, before the actual reconcile runs.
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

Operator-driven, reversible. From `ready`, the Workflow card's
**Close session** button moves the session to `expired`
(display label "Closed"): every instrument closes, all responses
are preserved, and the operator can Revert to draft to reopen for
editing. Distinct from Revert to draft (`ready → draft`) — Close is
the end-of-cycle transition; Revert is a mid-cycle setup edit.

### 16.2 Archive

Operator-driven, reversible. The Workflow card offers **Archive
session** once the session is `expired`; the Sessions lobby's **Purge and
archive** and the Extract data page's **Archive session** card
archive a `draft`, `validated` or `expired` session, never a `ready`
one ([§6.1](#61-transitions)). Archived sessions:

- Disappear from the main Sessions lobby.
- Are visible on the archived-sessions child page.
- Have all data preserved on disk, unless purged on the way in
  (§16.5) or deleted afterwards from Session Home's Danger Zone
  (§16.3, §16.4).
- Can be unarchived back to `draft` at any time.

### 16.3 Delete data

A per-session operator action on the Session Home Danger Zone.
Wipes every reviewer response in the session while preserving the
rosters, instruments, assignments, and configuration. Available in
every state but `ready` (`draft`, `validated`, `expired`,
`archived`); an Activated session takes **Revert to draft** first.
Audit-logged as `responses.deleted_all`. Useful for
clearing a session between two pilot runs without rebuilding the
configuration.

### 16.4 Delete session

A per-session operator action on the Session Home Danger Zone.
Removes the session entirely and cascades to every dependent row
(rosters, assignments, responses, audit events for the session).
Available in every state but `ready`, so a finished (`expired`) or
`archived` session can be deleted from its Home; visible-but-disabled
while the session is `ready`, which takes **Revert to draft** first.

### 16.5 Operator-triggered purge and archive

An action on the Sessions lobby's row and bulk expanders, and on
the Extract data page's **Archive session** card. It hard-deletes
whichever of the session's responses, rosters and audit log the
operator ticks, then archives what remains; with nothing ticked it
is a plain archive. It applies to `draft`, `validated` and `expired`
sessions; an activated (`ready`) one is skipped. Useful for sessions
that have served their purpose but whose configuration the operator
wants to keep as a template.

### 16.6 Per-session retention

Two inert columns sit on each session — a per-session
retention exception and a per-session retention overrides
JSON — pending a scheduled-purge subsystem that has been
deferred. The functional intent is to let an operator (or
the workspace) configure a per-session retention window
distinct from a workspace default; the manual archive +
operator-triggered purge cover the per-session needs in the
meantime.

### 16.7 Scheduled archive and purge

Deferred. The functional intent — auto-archive after a
configurable offset from the deadline; auto-purge per a
deployment-or-session retention policy — is captured in the
schema but not currently fired. Operators today rely on the
manual archive (lobby row expander) and the operator-
triggered purge for these needs.

---

## 17. Permissions and access control

RRW enforces access at six gates (the full catalogue, with
failure semantics and the per-route matrix, is
`spec/permissions.md`):

1. **Workspace operator** — applies to every `/operator/*`
   surface. The signed-in identity must be on the workspace
   allowlist (operator or admin flag).
2. **Per-session operator** — applies to session-scoped
   `/operator/sessions/{id}/*` surfaces. The signed-in
   identity must be an owner of that session. An admin who
   is not an owner may *read* the session's diagnostics but
   must self-add as owner (an audited action) before editing.
3. **Sys admin** — applies to the workspace governance and
   diagnostics surfaces. The signed-in identity must carry
   the admin flag; changing *who is an admin* additionally
   requires the config-derived super-admin tier.

Three gates apply to participant surfaces, each by
case-insensitive email match against an **active** roster row —
and gate 5 additionally by a visibility grant:

4. **Reviewer in session** — the reviewer surface, save /
   submit / clear, and the post-submit summary.
5. **Reviewee in session, with a current grant** — the reviewee
   results surface. The roster match alone is not enough: at
   least one instrument must grant this reviewee a mode inside the
   open response-release window, or the route answers 404
   ([§4.4](#44-reviewee)). A reviewee whose identifier is not
   an email can never reach it.
6. **Observer in session** — the observer collation surface.

An invitation token grants nothing on its own: the token
landing checks the signed-in email against the invitation's
reviewer email (403 on mismatch) and then forwards to the
reviewer surface, which applies gate 4.

Every gate is enforced server-side; UI affordances that the
current identity cannot use render either inert (with an
explanatory tooltip) or hidden, depending on the surface.

Destructive actions require **explicit confirmation** (a
tick-box gating the destructive submit) and write one or more
audit events. A tag or relationship change that moves a pair to
another group on a group-scoped instrument deletes that row's group
answer copy without a response-loss acknowledgement
([§14](#14-reconciling-regeneration)).

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
- **Boundary tag** — A reviewee or pair-context tag picked in Link 3
  of a group-scoped instrument's assignment rule. Members of a group
  share the same value for every boundary tag.
- **D6 source** — One of the **nine** possible display-field
  sources (reviewee name, reviewee email, photo link, three
  reviewee tags, three pair-context tags). Two are locked on,
  seven opt-in; see [§5.8](#58-display-field).
- **Display field** — A read-only context column on an
  instrument; one of nine D6 sources.
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

For what is still to be built, read `guide/todo_master.md`; for
segment-by-segment history, the archived plans indexed in
`guide/archive/README.md`.

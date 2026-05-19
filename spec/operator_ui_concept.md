# Operator UI concept

**Conceptual map of the operator-facing page surface plus per-page contracts.** Names the page set's groupings, the navigation principles that govern movement between them, the lifecycle vocabulary the surface is built around, and a per-page contract summary for each operator page.

This file sits one level above the visual style spec for Review Robin (`spec/visual_style_rrw.md`, which owns chrome and component details) and one level below the audience model (`spec/audience_and_identity_model.md`) and the architecture spec (`spec/architecture.md`, which owns the domain). When the page set or its navigation changes, this is the file to update first; visual chrome decisions in `visual_style_rrw.md` follow from the page taxonomy here, and per-page deep-dive specs (e.g. `spec/session_home.md`, `spec/instruments.md`) assume this doc's contracts as their starting point.

For the reviewer-facing surface — out of scope here — see `spec/reviewer-surface.md` and the reviewer chrome section of `spec/visual_style_rrw.md`.

## Reading order

This doc reads downstream from:

- **`spec/audience_and_identity_model.md`** — audience definitions, auth posture, customization boundaries. Establishes that *operator* and *reviewer* are distinct audiences each with their own chrome conventions; this file covers the operator audience.
- **`spec/architecture.md`** — domain entities and layering.
- **`spec/visual_style_general.md`** — portable design system (palette, type, components).

…and upstream of (or peer to):

- **`spec/visual_style_rrw.md`** — Review-Robin instantiation of the design system, including chrome implementation details. Where this doc says "two-row chrome", `visual_style_rrw.md` says exactly which colors, classes, and tints realize it.
- **`spec/session_home.md`** — functional spec for the Session Home (Control Panel) page in detail.
- **`spec/instruments.md`** — locked spec for the Instruments page, post-Segment-10D rebuild.
- **`spec/preview_hub.md`** — Preview Pages contract.
- **`spec/quick_setup_card_spec.md`** — the Quick Setup card on Session Home.

When this doc disagrees with one of those, the more specific doc wins for the area it covers; this doc is canonical for the *taxonomy*, *navigation model*, and *contract-level page roles*.

## Lifecycle vocabulary

Sessions move through a small lifecycle. Three live states; two reserved future states. Internal enum values appear here; user-facing display labels are mapped through the helper documented in `spec/session_home.md` (notably `ready` → "Activated").

| Enum | Display label | Status |
|---|---|---|
| `draft` | Draft | live |
| `validated` | Validated | live |
| `ready` | **Activated** | live |
| `expired` | Expired | reserved (Segment 9.3+; deadline has passed) |
| `archived` | Archived | reserved (Segment 12+) |

Older docs and CSS occasionally reference a `closed` state; that state is not in the canonical enum. Slated for cleanup; `expired` and `archived` are the post-life states.

## Page taxonomy

The operator's pages fall into five active groupings plus one forward-looking placeholder.

### 1. Operator's Overview

The **top level** for a signed-in operator. Lists every session the operator has access to. The single launch point for everything session-scoped — to do anything inside a session, the operator clicks into it from here.

- `sessions_list.html` — `GET /operator/sessions`.

**Children of the Overview** (not session-scoped, but reached from this page):

- `session_new.html` — `GET /operator/sessions/new` — the Create-Session form.

### 2. Per Session Home / Control Panel

Once an operator is **inside a session**, the Control Panel is that session's home. It is the **launch point for lifecycle transitions**, not a control centre for ongoing work.

- `session_detail.html` — `GET /operator/sessions/{id}`.

Most of the operator's time is spent doing **phase work** — configuring setup, then running operations — on the phase pages where that work belongs. But the **transitions between lifecycle states** are session-level commits and the Workflow card on every session-scoped page surfaces the next one explicitly: validating a setup, activating, and reverting to draft all happen via the Workflow card's stepper.

Home's body, layout, and per-state behaviour are specified in **`spec/session_home.md`**. The Workflow card itself is specified in **`spec/workflow_card.md`** (same partial renders on Session Home and every Operations-row page). The high-level Home shape: a full-width **Workflow card** above two independent flex columns — left column carries Session Details + Danger Zone, right column carries Quick Setup + Extract Data. The Workflow card's seven-stage stepper is the canonical entry point for every lifecycle-advancing action; the Activate session super-button collapses Generate → Validate → Activate into a single click.

#### Sub-pages of Home

- `session_edit.html` — `GET /operator/sessions/{id}/edit` — edit form for session metadata (name, code, deadline, description). Reached from a link on Home.

(The detailed Validate page, formerly a sub-page of Home, is now an Operations tab — see §5 below.)

### 3. Per Session Setup Pages

The five surfaces where the operator does the work needed to make the session run properly. Each one has full edit affordance while the session is `draft` / `validated`, and locks down once the session is `ready` (yellow lock card pattern; see `spec/visual_style_rrw.md` "Warning surfaces — shared brown framing").

| Page | Template | URL |
|---|---|---|
| Reviewers | `session_reviewers.html` | `/sessions/{id}/reviewers` |
| Reviewees | `session_reviewees.html` | `/sessions/{id}/reviewees` |
| Relationships | `session_relationships.html` | `/sessions/{id}/relationships` |
| Instruments | `instruments_index.html` | `/sessions/{id}/instruments` |
| Email Template | `session_setupinvite.html` | `/sessions/{id}/setupinvite` |

The URL slug `setupinvite` predates the Setup Page / Operations Page split; the settled name for the page is **Email Template**. The page houses the email-template editor (shipped in Segment 11E): per-template overrides for Invitation / Reminder / Responses-received emails, with merge-tag reference, per-field reset, and a "Send confirmation when a reviewer submits?" toggle. The run-time invitation management lives in the Operations Page below.

**Relationships** carries pair-level context — the `relationships` table seeded in Segment 13E PR 2 and lit up by the Setup page in Segment 15D PR 2. Reviewer × reviewee rows carry three `tag_N` slots consumed by the rule engine via the `pair_context.tag1` / `pair_context.tag2` / `pair_context.tag3` predicate field names (15D PR 3 / PR 4) plus an `active` / `inactive` status. The page mirrors Reviewers / Reviewees — CSV upload, "Fields with data" pill row, preview table with per-row authoring, Danger Zone.

The Reviewers / Reviewees / Relationships pages share a common body shape (chrome → status strip → "Fields with data" pill row → optional lifecycle lock card → a half-width `bottom-grid` pairing the friendly-label editor with the **Operator actions card** → preview table with a leftmost checkbox column, visibility toggles, clickable sort headers and a right-end Updated column → upload-and-Danger-Zone grid). The full UI contract for these pages — including the per-page preview-table column order, the shared visibility-toggle pattern, the shared sort affordance, and the Segment 15F per-row Edit / Add / bulk authoring surface — is in `spec/setup_pages.md`. Instruments has a heavier custom layout — see `spec/instruments.md` for the locked spec.

The **sort affordance** is the rrw-sort primitive shipped 2026-05-12 in Segment 13B Part 2. Any operator table that wants clickable sort headers opts in via a small annotation contract on the `<table>` + `<th>`s + `<td>`s; the shared JS in `base.html` + cookie persistence layer take care of state. Today's adopters: Reviewers / Reviewees / Relationships (Setup row) + the Operations Assignments table. Per-instrument `sort_display_fields` on the reviewer surface is a separate but compatible mechanism — the operator picks a default for reviewers via the Sort column on the Instruments Display Fields card; reviewers override live via the same header buttons. Functional spec at `spec/sort_by_reviewee.md`.

**Assignments retired from Setup row in Segment 15D PR 6a.** Pre-15D the page was a Setup-row primitive carrying both pair-level context (`PairContext1/2/3` / `AssignmentContext1/2/3` JSON columns) and the rule-based generation card. Post-15D pair-level context lives on the first-class `relationships` table (its own Setup page above); the Operations Assignments page is now a materialised derivative — see §5 below.

### 4. Preview Pages

Read-only renderings spun off from one or other Setup Page, showing what the configured setup will look like to its audience (reviewers today; future reviewees or other audiences once they exist).

The Preview hub lives at `GET /operator/sessions/{id}/previews` (Operations row, tab label "Previews") — see `spec/preview_hub.md` for the contract. The standalone reviewer-surface preview at `GET /operator/sessions/{id}/preview` (singular) was retired in Segment 11F PR C; the URL is now a permanent (308) redirect to `/operator/sessions/{id}/previews#reviewer-surface` (the surface card on the consolidated hub). The hub bypasses session-status / deadline / acceptance gates.

The grouping name stays plural because additional Preview surfaces are anticipated (e.g. per-instrument preview integration is open per `spec/instruments.md` Section D).

### 5. Per Session Operations Pages

Surfaces for running a session and intervening when needed — validating setup, generating / previewing the materialised reviewer-facing artifacts, engaging reviewers, tracking reviewee coverage. Five tabs in the chrome's Operations row:

| Page | Template | URL |
|---|---|---|
| Validate | `session_validate.html` | `/sessions/{id}/validate` |
| Assignments | `session_assignments.html` | `/sessions/{id}/assignments` |
| Previews | `session_previews.html` | `/sessions/{id}/previews` |
| Invitations | `session_invitations.html` | `/sessions/{id}/invitations` |
| Responses | `session_responses.html` | `/sessions/{id}/responses` |

Assignments moved Setup → Operations in Segment 15D PR 6a: pair-level context is configured on the Relationships Setup page above, and the Assignments page reframes as the place to **generate** the reviewer × reviewee × instrument materialisation. Body shape (top-to-bottom): chrome → **Per-instrument status** card (first under chrome — sticky across draft + ready states) → a column-visibility chips card paired with an operator-actions search / bulk card (`bottom-grid`) → Assignments preview table. The status card carries per-instrument columns for Type (Individual / Group), Rule, Generated, Groups, Self review, Included, plus a Show checkbox that client-side-filters the preview table and an Edit link to the matching Instruments card; the Self review checkbox flips include flags for that instrument's self-review rows in bulk. Generation is driven from the Workflow card's stepper — the standalone Generate card retired with the Next Action workflow-stepper refresh. The pre-15D Setup-row manual-CSV upload affordance retired with the move; the legacy manual-import route survives as a dev-diagnostic surface only.

When the session is `ready`, the status card remains visible (operators inspect mid-cycle), but the per-instrument Self review checkbox renders `disabled` — review is ongoing and flipping include flags would silently change live invitation eligibility. Show + Edit + the inline filter JS stay interactive.

The row pairs are deliberate: pre-flight (Validate, Assignments, Previews), monitoring (Invitations, Responses). See `spec/operations_pages.md` for the Invitations + Responses consolidation rationale and per-page contracts; `spec/rule_based_assignment.md` §7.1 covers the Rule Based card.

**Naming:** "Invitations" + "Responses" rather than "Reviewers" + "Reviewees" — those nouns are claimed by the Setup tabs (configuring the rosters); the Operations tabs are about working with them mid-session. Distinct nouns for distinct activities.

**Retired:** the previous standalone `session_monitoring.html` is consolidated into Invitations (reviewer-centric, sending + monitoring + reminders combined). The `/sessions/{id}/monitoring` URL redirects to `/invitations` to preserve bookmarks.

**Outbox is not a chrome tab.** `session_outbox.html` at `/sessions/{id}/outbox` is a dev-diagnostic surface — useful for inspecting the rendered email body / token URL during pilot or when debugging a send issue, but not part of the operator's day-to-day Operations row taxonomy. It's reachable via a "View outbox" button on the Manage Invitations page; that button is the canonical entry point. A future cross-session admin surface would belong to the System Admin group below.

### 6. System Admin / System Setup Pages (placeholder)

A future grouping for **cross-session** admin (operator permissioning, system-wide settings, multi-tenant config). Empty today; flagged so the taxonomy has a slot for it when the work surfaces. If a cross-session admin page is added, it sits at the Operator's Overview level (or above), not inside a session.

## Design principles

### P1 — One session at a time

The operator is always **inside exactly one session, or in the Overview**. Session-scoped chrome never offers cross-session navigation; to switch sessions, the operator returns to the Overview.

### P2 — Both phases always reachable

Within a session, **Setup and Operations are both navigable from the chrome on every session-scoped page**. The operator is never required to traverse Home to switch phases.

### P3 — Home is the launch point for lifecycle transitions

Home is the session's **identity** and the canonical anchor for session-level concerns (metadata, Quick Setup, Extract Data, Danger Zone). Lifecycle-advancing actions live on the Workflow card, which renders on Home AND on every Operations-row page (per `spec/workflow_card.md`), so the operator can advance the session from wherever they happen to be looking.

### P4 — Lifecycle disables, never hides

Pages remain reachable across all session lifecycle states. Affordances that don't apply to the current state render disabled. The default disabled treatment for setup-mutation surfaces is the yellow lock card pattern (`spec/visual_style_rrw.md`); the three post-Operations pages (Assignments / Invitations / Responses) are the exception — their yellow `.card.lock` notices retired because the Workflow card's stepper already makes lifecycle state explicit. Home is the same exception via the same Workflow card.

The four-line shape: two principles about *where the operator can go* (P1, P2), one about *what Home is for* (P3), one about *what stays reachable* (P4). None of them overlap.

## Navigation model

The chrome that implements P1–P4. Visual implementation details (colors, tints, marker tones, exact CSS classes) live in **`spec/visual_style_rrw.md`** "Operator session chrome"; what follows is the conceptual contract.

### Chrome layout

A double-height **Home** anchor on the left, two rows of phase tabs to its right:

```
┌────────┬─ SETUP ▶      [Reviewers][Reviewees][Relationships][Instruments][Email Template]
│  Home  │
└────────┴─ OPERATIONS ▶ [Assignments][Validate][Previews][Invitations][Responses]
```

- **Home** is double-height to span both rows, signalling that it's one level up from the phase tabs rather than a peer of any of them. It carries the session's identity, so the chrome itself answers *"which session am I in?"* The session's lifecycle state surfaces in the status row below the chrome, not inside the Home anchor.
- **Row labels** ("SETUP", "OPERATIONS") sit at the left edge of each row. Labels carry the row-identity job; row tints reinforce but shouldn't be the only signal.
- **Same tab shape across rows.** The labels and rows do the grouping work; tabs themselves don't need to differ in shape.
- **Active tab** uses an underline marker. The marker uses one tone per row (lighter than the row's full accent) so the marker says *"you are here"* without competing with the label.

Below the chrome, a **status row** renders the at-a-glance session status, identical on every session-scoped page: lifecycle pill first, then the Setup-entity counts (Reviewers / Reviewees / Relationships / Instruments / Email Template), then two operations indicators (Invitations, Responses). Composition and visual treatment are in `visual_style_rrw.md`.

### Behaviour

- **From any phase page**, both rows are visible and any tab is one click away. No traversal through Home is required to switch phases.
- **From Home**, the chrome renders the same way, with no tab active. Both phase rows remain visible and clickable; Home's body is what's distinctive, not its chrome.
- **Lifecycle states don't hide pages.** Setup tabs remain visible and reachable when the session is `ready`, but their pages render locked behind the yellow lock card. Operations tabs remain visible and reachable when the session is `draft` or `validated`, but their actions render disabled. The chrome is stable across the lifecycle; the page bodies adapt.

### Sub-pages and Preview

- **Sub-pages of Home** (Edit Session): chrome renders the two phase rows normally, with no tab active. The sub-page identifies itself via H1 in the page body.
- **Retired standalone reviewer-surface preview** (`/preview`, singular): retired in Segment 11F PR C as a permanent (308) redirect to `/sessions/{id}/previews#reviewer-surface`. The reviewer-surface render now lives as the Previews hub's surface card.

### What the chrome does not do

- It doesn't carry **lifecycle-transition actions**. Activate session and Revert to draft are body-level actions on the Workflow card (which renders on Home + every Operations-row page), not chrome buttons. Keeping them off the chrome leaves the chrome a stable launch-point surface, while the Workflow card carries the per-state stepper next to the page body the operator is currently working in.
- It doesn't carry **cross-session navigation**. Switching sessions means returning to the Overview.
- It doesn't **change shape** based on lifecycle state or sysadmin mode. Stability matters; the operator should learn the chrome once.

## Cross-page chrome (top of every page)

Every operator page (session-scoped or not) renders the same outer chrome before the session top nav and page body:

- **App identity (top left).** "Review Robin Web App (version {num})" rendered small as a link to `/about`.
- **User card (top right).** "Signed in as {user name}" plus a Sign-out control (`/.auth/logout`).
- **Breadcrumb trail** (below the app identity) reflecting the page's position in the surface hierarchy. Each segment except the current page is a link to that ancestor; the current page renders as a plain non-link label.
  - Operator root: `Sessions` → `/operator/sessions`.
  - Reviewer root: `Reviewer` → `/reviewer` (covered in `spec/reviewer-surface.md`).

Visual treatment (typography, spacing, link colors) is per `spec/visual_style_general.md` ("Breadcrumb", "Links") and `spec/visual_style_rrw.md` (non-session operator top bar).

## Per-page contracts

A short contract per page: URL + template + role + key affordances. For per-route detail with form schemas and audit events, see `docs/status.md` (operator URL table). For deep-dive layout / behaviour specs, see the linked per-page docs.

### `/operator/sessions` — Sessions list

Top-level operator lobby. A table of sessions, one row per session, columns: **Name**, **Code**, **Status**, **Deadline**, **Created**, **Created by**, plus per-row **Access** + **Delete** buttons. Below the table: a **Create new session** button.

### `/operator/sessions/{id}` — Session Home / Control Panel

The per-session home. **Detailed spec: `spec/session_home.md`.** Full-width **Workflow card** above two independent flex columns; left column carries Session Details + Danger Zone, right column carries Quick Setup + Extract Data. The Workflow card (specified in `spec/workflow_card.md`) carries every lifecycle-advancing action via its uniform seven-stage stepper and the Activate session super-button.

### `/operator/sessions/new` — Create new session

Single-page form. No session top nav (the session doesn't exist yet); breadcrumb reads `Sessions → Create New Session`.

Fields: Name (required, max 255), Code (required, max 64; unique per operator), Timezone (required, IANA-zone `<datalist>`, pre-filled with the operator's default; Segment 18B PR 4), Deadline (optional, datetime-local — interpreted as wall-clock in the picked Timezone), Description (optional, max 2000), Help contact (optional). Action row: **Create session** (Primary) submits to `POST /operator/sessions` → inserts the session + a `SessionOperator` row + a `session.created` audit event + 303 to `/operator/sessions/{id}`. **Cancel** (Secondary) → `/operator/sessions`.

### `/operator/sessions/{id}/edit` — Edit session

Same shape as the create form, with pre-populated values; no session top nav (it's a meta-edit, sub-page of Home). Breadcrumb is `Sessions → {session.name} → Edit Session`.

Same fields as create (Name, Code, Timezone, Deadline, Description, Help contact), pre-filled — the Timezone field was folded in from the former standalone Display timezone card in Segment 18B PR 5, so the display zone is now lifecycle-gated like the rest of the form. Action row: **Save changes** (Primary) submits to `POST /operator/sessions/{id}/edit` → emits a `session.updated` audit event with `changes: {field: [old, new]}` for each changed field (plus a `session.display_timezone_set` event when the zone changes), invalidates `validated → draft`, and 303 back to session detail. **Cancel** (Secondary) → session detail.

The route returns **HTTP 409** when the session is `ready` — operators must Revert to draft first via the Workflow card.

### Setup pages (Reviewers / Reviewees / Relationships) — shared shape

All three setup-roster pages share an identical chrome shape:

1. Session top nav.
2. **Info card** with `Fields with data: {pill, pill, …}` listing
   the actual CSV column names for fields with at least one
   non-empty value (e.g. `ReviewerName`, `RevieweeEmail`,
   `PhotoLink`, `RevieweeTag1..3`, `PairContextTag1..3`,
   `Status`). The per-entity row count is **not** repeated here —
   the chrome status strip already carries it.
3. Yellow lock card when `ready` (with `return_to=reviewers` / `reviewees` / `relationships` so the operator returns here after reverting). Sits immediately under the info card — same status-info-then-yellow-lock pattern the Instruments and Assignments pages use.
4. **Friendly-label editor (left) + Operator actions card (right)** — a half-width `bottom-grid` pair. The friendly-label editor is the inline editor for the per-session tag-column labels; the Operator actions card (Segment 15F) carries the search / status filter strip and the selection-driven Edit · Inactivate · Activate · Add-new-row button row. See `spec/setup_pages.md` "Operator actions card".
5. Browseable data-preview table of the saved rows (always visible, even while locked) — leftmost checkbox column drives the operator-actions selection; a row flips to inline inputs in Edit (`?edit_id=`) / Add (`?add=1`) mode.
6. **Upload CSV** card — anchored at `#upload-csv`, hosts the bulk import form. Hidden when the lock card is shown or a row is being edited / added.
7. **Danger Zone** card with the **Delete all** confirm-checkbox form. Hidden when the lock card is shown or a row is being edited / added.

Per-row inline **Edit**, **Add new row**, and bulk **Inactivate / Reactivate** on these three pages shipped in Segment 15F (2026-05-15) — the Operator actions card is the surface; CSV Upload stays the bulk-create path. See `spec/setup_pages.md`.

The Operations Assignments page (§5 above) carries the wired **Rule Based Assignment** card. It exposes a RuleSet dropdown listing every visible RuleSet — seeded RuleSets first, then caller-owned Personal RuleSets — plus a Generate button and an inline link to the Rule Builder page (`/operator/sessions/{id}/assignments/rule-based-editor`). Shipped in Segment 13A, revamped in Segment 13A-1, and moved with the page to the Operations row in Segment 15D PR 6a; see `spec/rule_based_assignment.md` for the engine and Rule Builder UI contract.

### `/operator/sessions/{id}/instruments` — Instruments

A consolidated page for everything per-instrument: session-wide status + bulk toggles, then one card per instrument with in-place editing for description, response fields, and display fields, ending with a live Preview Instrument table.

**Detailed spec: `spec/instruments.md`.** That doc holds the locked surface definition post-Segment-10D rebuild (single bulk-save form, `?editing={iid}` URL state machine, mutual-exclusion edit lock, zero-RF save guard, RTD card with cascade-confirm and would-empty guards). Multi-instrument UI shipped — each instrument card carries an `Add instrument` / `Add group instrument` / `Replicate` button row, and the per-instrument Delete (gated by a confirm checkbox) replaced the per-card Danger Zone sub-card. Group-scoped instruments — one reviewer answer covering a group of reviewees — landed in Segment 13C.

### `/operator/sessions/{id}/setupinvite` — Email Template

Per-session email-template editor for the Invitation, Reminder, and Responses-received outbound emails. Reached from the Email Template tab in the chrome's Setup row.

The page renders, top-to-bottom: chrome (with `Email Template` highlighted as the current Setup tab); a `<div class="tab-strip tab-strip-page">` row of three page-internal nav tabs (`Invitation` / `Reminder` / `Responses received`) using the chrome's `.nav-tab` styling — see `spec/ui_elements.md` §6 "Nav button"; then a two-card body with the email composer on the left (form fields per template + per-field `Reset to default` `.btn-reset` button) and the Merge tags reference card on the right. Cancel + Save sit bottom-left of the composer card; Save is Secondary (routine submit) and renders disabled until any composer field is touched.

The composer's `?template=` query param keeps each tab bookmarkable. The `responses_received` tab also surfaces a "Send this confirmation when a reviewer submits?" checkbox above the composer fields that gates the per-session auto-send.

### `/operator/sessions/{id}/validate` — Setup validation

Operations row tab. Read-only deep-dive of every setup issue, intended for the operator who needs the per-issue breakdown beyond the at-a-glance counts on Home.

- **Page intro** (form-help text): "Read-only view of setup readiness for this session. Errors must be cleared before activation. Warnings can be acknowledged and overridden. Activate from the Workflow card at the top of any session page."
- **Severity counts** (three pills inline): error / warning / info counts.
- **Per-issue list** (rendered via the `operator/partials/validation_results.html` partial) — one entry per issue, with severity pill, source (e.g. "Reviewers", "Assignments"), and human description.

There is no standalone Activate button on this page body; activation fires from the Workflow card's Activate session super-button. The Validate page does still own the **warnings-detour banner** (`/validate?activate=1`) — the super-button redirects there when the readiness report has non-blocking findings so the operator can acknowledge them before the underlying `/activate` POST fires.

### `/operator/sessions/{id}/previews` — Previews hub

Operations row tab (label: **Previews**). **Detailed spec: `spec/preview_hub.md`.** Renders read-only previews of what reviewers will see (invitation email, response form, reminder email, responses-received email) for an operator-selected reviewer. Operator-only; bypasses session-status / deadline / acceptance gates.

The retired standalone `/operator/sessions/{id}/preview` (singular) — the predecessor reviewer-surface preview — is a permanent (308) redirect to `/sessions/{id}/previews#reviewer-surface`. The reviewer-surface render now lives as the hub's surface card.

### `/operator/sessions/{id}/invitations` — Invitations (reviewer-centric)

Operations row tab. **Detailed spec: `spec/operations_pages.md` "Invitations page".** Reviewer-centric working surface — sending invitations, sending reminders, monitoring per-reviewer progress. Consolidates what was previously split between the standalone Manage Invitations page and the (now-retired) Monitoring page.

Pattern: a list-with-bulk-actions table of reviewers, with status filtering, selection, bulk send/remind actions, and per-row drill-in into a reviewer's full engagement history. All POST actions require `ready` (409 otherwise).

### `/operator/sessions/{id}/responses` — Responses (reviewee-centric)

Operations row tab. **Detailed spec: `spec/operations_pages.md` "Responses page".** Reviewee-centric coverage view — surfaces under-served reviewees that the reviewer-centric Invitations view doesn't make visible.

Pattern: list-with-bulk-actions table of reviewees, with per-reviewee coverage status (`Complete` / `Adequate` / `At risk` / `No responses`), bulk reminder dispatch to non-responding reviewers for selected reviewees, and per-row drill-in into per-reviewer response status for that reviewee.

The reminder send-path is **shared** with the Invitations page; only the selection logic differs.

### `/operator/sessions/{id}/monitoring` — *retired*

The previous standalone Monitoring page has been consolidated into the new Invitations page (reviewer-centric) and Responses page (reviewee-centric) per `spec/operations_pages.md`. The URL redirects to `/operator/sessions/{id}/invitations` to preserve bookmarks.

### `/operator/sessions/{id}/outbox` — Email outbox

Dev-diagnostic page; **not an Operations row tab**. Reachable via the "View outbox" button on Manage Invitations. Read-only.

- **Page intro** (muted text): "Dev-mode email outbox for this session. No real SMTP backend is wired up; rows are flipped `queued → sent` synchronously when an operator clicks *Send*. The rendered body includes the raw invitation URL so you can copy it into a real client."
- **Per-row card** (newest first): kind (`invitation` / `reminder`), recipient email, status pill, sent-at timestamp, then the rendered subject + body (`<pre>` block).
- **Empty state** — "No outbox rows yet for this session."
- **Chrome.** The page extends `base.html` with the standard session top nav; no Operations tab highlights as active (mirroring how Edit Session sub-pages render with no tab active).

Real SMTP / production email is deferred to **Segment 14B** (email send activation + backends); the outbox table itself stays useful for debugging in any environment, and the columns the dispatch helper writes to landed with **Segment 11C Part 2** (PR #541, 2026-05-07).

### `/about` — About

Reached from the app-identity text at the top left of every operator page. Currently a stub.

## Out of scope / forward-looking notes

Recorded for visibility; **none are committed**. Capture additional ideas here as they surface so the taxonomy doesn't get redesigned to accommodate them later.

- **Central Control and Operations Panel** — a cross-session operator surface that aggregates run-state across all of an operator's sessions. Conceivable but ROI unclear, and P1 ("one session at a time") is stronger when the whole app respects it. Not on any segment plan.
- **Adjacent capabilities likely to land sooner:** shared operator permissions on a session, session duplication (sans response data), shared setup data between sessions (e.g. reusable reviewer rosters or instrument templates), session tagging / grouping. These compose with the Overview surface — none would force a redesign of the Setup / Control / Operations groupings.
- **Two-row chrome → single row.** With the Operations row at four tabs after the Invitations + Responses consolidation (and the Outbox de-tabbed) per `spec/operations_pages.md`, the two-row layout is unlikely to collapse. Recorded for completeness; not on any roadmap.
- **Cross-session System Admin** — when added, sits at Operator's Overview level (or above), not inside a session. Implies its own chrome (different from the per-session two-row nav). Not a per-session Operations Page.

## Cross-references

- **`spec/audience_and_identity_model.md`** — audience definitions and customization boundaries. This file covers the operator audience.
- **`spec/visual_style_general.md`** — portable design system.
- **`spec/visual_style_rrw.md`** — Review-Robin chrome instantiation, including all visual specifics elided here.
- **`spec/architecture.md`** — domain entities and layering. Reads upstream of this file.
- **`spec/session_home.md`** — Session Home (Control Panel) functional spec, including layout + lifecycle display-label mapping.
- **`spec/workflow_card.md`** — Workflow card (the single persistent action card that renders on Session Home + every Operations-row page); ten-state cascade, seven-stage stepper, Activate session super-button.
- **`spec/quick_setup_card_spec.md`** — Quick Setup card on Session Home.
- **`spec/preview_hub.md`** — Preview hub on the Operations row.
- **`spec/operations_pages.md`** — Invitations + Responses functional spec (reviewer-centric Invitations + reviewee-centric Responses; bulk-action affordances live on the Workflow card stepper).
- **`spec/reviewer-surface.md`** — reviewer-facing surface contracts (separate audience).
- **`spec/ui_elements.md`** — implementation catalogue mapping the canonical primitives to CSS classes and templates.
- **`spec/instruments.md`** — locked spec for the Instruments page.
- **`docs/status.md`** — current implementation state and per-route detail.

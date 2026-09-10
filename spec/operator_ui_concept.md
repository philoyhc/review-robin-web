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

Sessions move through a small lifecycle. All five states are live. Internal enum values appear here; user-facing display labels are mapped through the helper documented in `spec/session_home.md` (notably `ready` → "Activated").

| Enum | Display label | Status |
|---|---|---|
| `draft` | Draft | live |
| `validated` | Validated | live |
| `ready` | **Activated** | live |
| `expired` | Closed | live (Workflow-card "Close session": `ready → expired`) |
| `archived` | Archived | live (Workflow "Archive" / lobby "Purge and archive"; reversible via unarchive → draft) |

There is no `closed` state in the canonical enum — `expired` is the post-response-window state, and it *displays* as "Closed". `expired` and `archived` are the two post-life states.

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

Home's body, layout, and per-state behaviour are specified in **`spec/session_home.md`**. The Workflow card itself is specified in **`spec/workflow_card.md`** (same partial renders on Session Home and every Operations-row page). The high-level Home shape: a full-width **Workflow card**, the in-place `#session-config` card below it, then a `.bottom-grid` of **Quick Setup** (left) + **Danger Zone** (right) — see `spec/session_home.md` §3-4, which is the source of truth this summary follows. The Workflow card's single-row button layout (≤ 4 visible buttons per state, each at 25% column width, inactive hidden) is the canonical entry point for every lifecycle-advancing action; **Prepare session** runs Generate + Validate in sequence, and the standalone **Activate session** button fires from `validated` (with a warnings-detour link when there are non-blocking findings to acknowledge).

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
| Observers | `session_observers.html` | `/sessions/{id}/observers` |
| Instruments | `instruments_index.html` | `/sessions/{id}/instruments` |
| Email Template | `session_setupinvite.html` | `/sessions/{id}/setup-invite` |

**Observers page gate.** The Observers tab is only visible in the
Setup chrome and only routes to a page (rather than 404) when
`session.observers_enabled == True`. The operator sets this toggle
via the **User interface settings** card on the Create Session form
or the Edit Session Details page.

The URL slug `setup-invite` predates the Setup Page / Operations Page split; the settled name for the page is **Email Template**. The page houses the email-template editor (shipped in Segment 11E): per-template overrides for Invitation / Reminder / Responses-received emails, with merge-tag reference, per-field reset, and a "Send confirmation when a reviewer submits?" toggle. The run-time invitation management lives in the Operations Page below.

**Relationships** carries pair-level context — the `relationships` table seeded in Segment 13E PR 2 and lit up by the Setup page in Segment 15D PR 2. Reviewer × reviewee rows carry three `tag_N` slots consumed by the rule engine via the `pair_context.tag1` / `pair_context.tag2` / `pair_context.tag3` predicate field names (15D PR 3 / PR 4) plus an `active` / `inactive` status. The page mirrors Reviewers / Reviewees — CSV upload, preview table with per-row authoring and its `Show columns:` chips, Danger Zone.

The Reviewers / Reviewees / Relationships pages share a common body shape (chrome → status strip → optional lifecycle lock card → one `.card-columns` holding guidance and the friendly-label editor on the left, the **Operator actions card** on the right → preview table card, carrying its `Show columns:` chips above a table with a leftmost checkbox column, clickable sort headers and a right-end Updated column → upload-and-Danger-Zone grid). The "Fields with data" pill row that used to head the right column of that `.card-columns`, above Operator actions, retired in Segment 19I Item 12 rung 4: its pills named the columns holding data, which the chips say, and say better — a chip both reports the fact and acts on it. The Observers page shares the same shape minus the friendly-label editor and the chips (observers have a simpler fixed schema, one tag slot). The full UI contract for these pages — including the per-page preview-table column order, the shared visibility-toggle pattern, the shared sort affordance, the Segment 15F per-row Edit / Add / bulk authoring surface, and the Observers page gate — is in `spec/setup_pages.md`. Instruments has a heavier custom layout — see `spec/instruments.md` for the locked spec.

The **sort affordance** is the rrw-sort primitive shipped 2026-05-12 in Segment 13B Part 2. Any operator table that wants clickable sort headers opts in via a small annotation contract on the `<table>` + `<th>`s + `<td>`s; the shared JS in `base.html` + cookie persistence layer take care of state. Today's adopters: Reviewers / Reviewees / Relationships (Setup row) + the Operations Assignments table. Per-instrument `sort_display_fields` on the reviewer surface is a separate but compatible mechanism — the operator picks a default for reviewers via the Sort column on the Instruments Display Fields card; reviewers override live via the same header buttons. Functional spec at `spec/sort_by_reviewee.md`.

**Assignments retired from Setup row in Segment 15D PR 6a.** Pre-15D the page was a Setup-row primitive carrying both pair-level context (`PairContext1/2/3` / `AssignmentContext1/2/3` JSON columns) and the rule-based generation card. Post-15D pair-level context lives on the first-class `relationships` table (its own Setup page above); the Operations Assignments page is now a materialised derivative — see §5 below.

### 4. Preview Pages

Read-only renderings spun off from one or other Setup Page, showing what the configured setup will look like to its audience (reviewers today; future reviewees or other audiences once they exist).

The Preview hub lives at `GET /operator/sessions/{id}/previews` (Operations row, tab label "Previews") — see `spec/preview_hub.md` for the contract. The reviewer-surface render lives at the satellite route `GET /operator/sessions/{id}/preview-surface/{page_n}` (Segment 18Q follow-on, 2026-05-28) reached from the picker card's "Open full preview" button; it renders the same `reviewer/review_surface.html` template through the same `_surface_context` plumbing the live reviewer route uses. The standalone reviewer-surface preview at `GET /operator/sessions/{id}/preview` (singular) is retained as a permanent (308) redirect; its target was 2026-05-28-repointed from `/previews#reviewer-surface` (now-dead anchor) to `/preview-surface/1`. The preview surface bypasses session-status / deadline / acceptance gates.

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

Assignments moved Setup → Operations in Segment 15D PR 6a: pair-level context is configured on the Relationships Setup page above, and the Assignments page reframes as the place to **generate** the reviewer × reviewee × instrument materialisation. Body shape (top-to-bottom): chrome → **Per-instrument status** card (first under chrome — sticky across draft + ready states) → an operator-actions search / bulk card, half width and flush right → the Assignments preview table card, which carries its three `Show columns:` chip groups on one row above the table (Segment 19I Item 12: the chips moved out of a card of their own and into the table card, and the preview card's `Assignments preview` heading — the only `<h2>` on a preview card anywhere — went with the move). The status card carries per-instrument columns for Type (Individual / Group), Generated, Groups, Self review, Included, plus a Show checkbox that client-side-filters the preview table and an Edit link to the matching Instruments card; the Self review checkbox flips include flags for that instrument's self-review rows in bulk. Generation is driven from the Workflow card's stepper — the standalone Generate card retired with the Next Action workflow-stepper refresh. The pre-15D Setup-row manual-CSV upload affordance retired with the move; the legacy manual-import route survives as a dev-diagnostic surface only.

When the session is `ready`, the status card remains visible (operators inspect mid-cycle), but the per-instrument Self review checkbox renders `disabled` — review is ongoing and flipping include flags would silently change live invitation eligibility. Show + Edit + the inline filter JS stay interactive.

The row pairs are deliberate: pre-flight (Validate, Assignments, Previews), monitoring (Invitations, Responses). See `spec/operations_pages.md` for the Invitations + Responses consolidation rationale and per-page contracts; `spec/assignments.md` covers the Assignments page and the per-instrument status table.

**Naming:** "Invitations" + "Responses" rather than "Reviewers" + "Reviewees" — those nouns are claimed by the Setup tabs (configuring the rosters); the Operations tabs are about working with them mid-session. Distinct nouns for distinct activities.

**Retired:** the previous standalone `session_monitoring.html` is consolidated into Invitations (reviewer-centric, sending + monitoring + reminders combined). The `/sessions/{id}/monitoring` URL redirects to `/invitations` to preserve bookmarks.

**Outbox is not a chrome tab.** `session_outbox.html` at `/sessions/{id}/outbox` is a dev-diagnostic surface — useful for inspecting the rendered email body / token URL during pilot or when debugging a send issue, but not part of the operator's day-to-day Operations row taxonomy. It's reachable via a "View outbox" button on the Manage Invitations page; that button is the canonical entry point. A future cross-session admin surface would belong to the System Admin group below.

### 6. System Admin / System Setup Pages

The **cross-session** admin grouping. Shipped in Segment 16A and extended by Segment 18S (three-tier operator / admin / super-admin role model — see `spec/audience_and_identity_model.md` §4). It sits at the Operator's Overview level (above any single session, not inside one), is gated by `require_sys_admin`, and carries its own chrome distinct from the per-session two-row nav. Routes live in `app/web/routes_operator/_sys_admin.py`; the entry point `GET /operator/sys-admin` redirects to the default tab (Sessions Diagnostics).

Two surfaces today:

- **Accounts Management** (`/operator/sys-admin/users`, `sys_admin_users.html`) — the workspace allowlist: admit / revoke `is_operator`, promote / demote `is_sys_admin` (super-admin actor only), invite, delete users, and bulk-remove a user from every session. Server-side guards in `app/services/users.py`.
- **Sessions Diagnostics** (`/operator/sys-admin/sessions`, `sys_admin_sessions.html`) — every session in the workspace, each row exposing Outbox + Audit log (read-only for a non-owner sys-admin since 18S Item 3) and a **Manage** action that self-adds the sys-admin as an owner (`POST …/sessions/{id}/adopt`, audited `session.owner_added`) before opening the session. Since **19C Item 10** the page also carries a read-only **Visibility grid audit** card: every stored Band 3 cell whose mode its `(audience, window)` pair does not allow, workspace-wide, live findings first. It writes nothing — clearing a cell is the owning operator's action on the Band 3 editor. It sits here rather than on any per-session page because the query spans every session, which no per-session operator may see (`spec/permissions.md`).

System-wide settings + multi-tenant config remain forward-looking.

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
┌────────┬─ SETUP ▶      [Reviewers][Reviewees][Relationships][Observers][Instruments][Email Template]
│  Home  │
└────────┴─ OPERATIONS ▶ [Assignments][Validate][Previews][Invitations][Responses]
```

The Observers tab renders conditionally — only when
`session.observers_enabled == True`. When disabled the tab is
hidden from the chrome so the Setup row stays uncluttered for
sessions that don't use observers.

- **Home** is double-height to span both rows, signalling that it's one level up from the phase tabs rather than a peer of any of them. It carries the session's identity, so the chrome itself answers *"which session am I in?"* The session's lifecycle state surfaces in the status row below the chrome, not inside the Home anchor.
- **Row labels** ("SETUP", "OPERATIONS") sit at the left edge of each row. Labels carry the row-identity job; row tints reinforce but shouldn't be the only signal.
- **Same tab shape across rows.** The labels and rows do the grouping work; tabs themselves don't need to differ in shape.
- **Active tab** uses an underline marker. The marker uses one tone per row (lighter than the row's full accent) so the marker says *"you are here"* without competing with the label.

Below the chrome, a **status row** renders the at-a-glance session status, identical on every session-scoped page: lifecycle pill first, then the Setup-entity counts (Reviewers / Reviewees / Relationships / Instruments — reported `configured / total` — / Email Template), then two operations indicators (Invitations, Responses). Composition and visual treatment are in `visual_style_rrw.md`.

### Behaviour

- **From any phase page**, both rows are visible and any tab is one click away. No traversal through Home is required to switch phases.
- **From Home**, the chrome renders the same way, with no tab active. Both phase rows remain visible and clickable; Home's body is what's distinctive, not its chrome.
- **Lifecycle states don't hide pages.** Setup tabs remain visible and reachable when the session is `ready`, but their pages render locked behind the yellow lock card. Operations tabs remain visible and reachable when the session is `draft` or `validated`, but their actions render disabled. The chrome is stable across the lifecycle; the page bodies adapt.

### Sub-pages and Preview

- **Sub-pages of Home** (Edit Session): chrome renders the two phase rows normally, with no tab active. The sub-page identifies itself via H1 in the page body.
- **Operator-side preview-surface route** (`/preview-surface/{page_n}`, Segment 18Q follow-on 2026-05-28): renders the reviewer surface for an operator-selected reviewer in a new tab, reusing the live ``_surface_context`` plumbing. The legacy `/preview` (singular) URL is a permanent (308) redirect to `/preview-surface/1` (was `/previews#reviewer-surface` through 2026-05-28; the iframe surface card on the Previews hub was retired in the same follow-on).

### What the chrome does not do

- It doesn't carry **lifecycle-transition actions**. Activate session and Revert to draft are body-level actions on the Workflow card (which renders on Home + every Operations-row page), not chrome buttons. Keeping them off the chrome leaves the chrome a stable launch-point surface, while the Workflow card carries the per-state stepper next to the page body the operator is currently working in.
- It doesn't carry **cross-session navigation**. Switching sessions means returning to the Overview.
- It doesn't **change shape** based on lifecycle state or sysadmin mode. Stability matters; the operator should learn the chrome once.

## Cross-page chrome (top of every page)

Every operator page (session-scoped or not) renders the same outer chrome before the session top nav and page body:

- **App identity (top left).** "Review Robin Web App (version {num})" rendered small as a link to `/about`.
- **User card (top right).** "Signed in as {user name}" plus a Sign-out control (`/.auth/logout`). A sys-admin's name carries a tier suffix — ` (super admin)` or ` (sys admin)`, the former winning when both apply — matching the three-tier model in `spec/audience_and_identity_model.md` §4.
- **Breadcrumb trail** (below the app identity) reflecting the page's position in the surface hierarchy. Each segment except the current page is a link to that ancestor; the current page renders as a plain non-link label.
  - Operator root: `Sessions` → `/operator/sessions`.
  - Reviewer root: `Reviewer` → `/me` (covered in `spec/reviewer-surface.md`).

Visual treatment (typography, spacing, link colors) is per `spec/visual_style_general.md` ("Breadcrumb", "Links") and `spec/visual_style_rrw.md` (non-session operator top bar).

## Entry & landing (Segment 18R Item 6)

The app has no page of its own at the root or the bare operator prefix — both are **role-aware redirects** so a freshly-signed-in user lands somewhere useful without knowing a deep URL.

- **`GET /`** — a **302** redirect by role: an **operator or sys-admin** lands on `/operator/sessions` (the lobby); **everyone else** (a participant, or a signed-in user with no roles yet) lands on `/me`, which renders its own empty state. Routes on `is_operator OR is_sys_admin`. Temporary (302), never 301 — the target follows the user's role, which can change. The root serves no JSON; liveness / metadata live only at `/health`.
- **`GET /operator`** (and `/operator/`) — 302 to `/operator/sessions`. Defined app-level and **unguarded** so the lobby's router-level `require_operator` is the single place that decides operator access.
- **Non-operator/non-sys-admin who reaches any `/operator/*` page** — bounced to `/me` by the `OperatorAllowlistDenied` handler (was `/request-access`, retired 18R Item 6). The "signed in but no access / how to get in" messaging moved to **`/about`**, which carries the signed-in identity + the operator contact.

## Per-page contracts

A short contract per page: URL + template + role + key affordances. For per-route detail with form schemas and audit events, see `docs/status.md` (operator URL table). For deep-dive layout / behaviour specs, see the linked per-page docs.

### `/operator/sessions` — Sessions list

Top-level operator lobby. A table of sessions, one row per session, columns: **Name**, **Code**, **Status**, **Deadline**, **Created**, **Created by**, plus a per-row **expander** (rename / tag / clone / purge-and-archive) — see `spec/sessions_overview.md`. The **Add new session** button sits in the Search card above the table, not below it. *(Corrected 2026-09-08 at 19C's close — this read "per-row Access + Delete buttons" and "Below the table: a Create new session button".)*

### `/operator/sessions/{id}` — Session Home / Control Panel

The per-session home. **Detailed spec: `spec/session_home.md`.** Full-width **Workflow card**, then the in-place `#session-config` card, then a `.bottom-grid` of **Quick Setup** (left) + **Danger Zone** (right). *(Corrected 2026-09-08 at 19C's close — this described Session Details + Danger Zone against Quick Setup + Extract Data, a layout 18R Item 4 replaced.)* The Workflow card (specified in `spec/workflow_card.md`) carries every lifecycle-advancing action via a single-row button layout (≤ 4 visible buttons per state) — Prepare session, Create invites, Send invites, Activate session, Send reminders, Close session, Release responses, Stop releasing, Archive session, plus Revert to draft.

### `/operator/sessions/new` — Create new session

Single-page form. No session top nav (the session doesn't exist yet); breadcrumb reads `Sessions → Create New Session`.

Fields: Name (required, max 255), Code (required, max 64; unique per operator), Timezone (required, IANA-zone `<datalist>`, pre-filled with the operator's default; Segment 18B PR 4), Deadline (optional, datetime-local — interpreted as wall-clock in the picked Timezone), Description (optional, max 2000), Help contact (optional). The Schedule sub-grid also surfaces **Release responses from** (`responses_release_at`) and **Release responses until** (`responses_release_until`, an absolute close `datetime-local` — S12 retired the W14 ISO 8601 duration `release_until_offset`). All four `datetime-local` inputs (Start / End / Release-from / Release-until) carry `min` / `max` attributes the browser picker honours — Start ≤ End ≤ Release-from ≤ Release-until — and a small shared partial (`operator/partials/_schedule_ordering_js.html`) live-updates the bounds as the operator types. The server re-runs `scheduled_events.validate_schedule_ordering` as the load-bearing safety net (see `spec/lifecycle.md` §8.2.7). A **User interface settings** card above the Quick Setup card carries two checkboxes: **Enable Relationships tab** (`relationships_enabled`) and **Enable Observers tab** (`observers_enabled`); both default unchecked. Action row: **Create session** (Primary) submits to `POST /operator/sessions` → inserts the session + a `SessionOperator` row + a `session.created` audit event + 303 to `/operator/sessions/{id}`. **Cancel** (Secondary) → `/operator/sessions`.

### `/operator/sessions/{id}/edit` — retired

**There is no Edit session page.** Segment 18R Item 4 moved editing back
onto Session Home's `#session-config` card, and this route is now a
**308 redirect** to `…?editing=1#session-config`
(`app/web/routes_operator/_session_home.py`). The fields, the
lifecycle gate and the `session.updated` audit event are unchanged; only
their location is. See `spec/session_home.md` §4.

*(This section described the retired page in full — its breadcrumb,
its Save changes / Cancel action row, its 409 when the session is
`ready` — until 2026-09-08, when 19C's close audit found it. The page
had been gone for three weeks. A page-by-page concept document names
pages, so a retired one leaves a section behind that reads exactly like
a live one.)*

### Setup pages (Reviewers / Reviewees / Relationships) — shared shape

All three setup-roster pages share an identical chrome shape:

1. Session top nav.
2. Yellow lock card when `ready` (with `return_to=reviewers` / `reviewees` / `relationships` so the operator returns here after reverting). Sits directly under the status strip, above the `.card-columns` container — it used to follow the info card, which retired in Segment 19I Item 12. **Not Assignments**: P4 above already records that the three post-Operations pages retired their `.card.lock` notices, and this line contradicted it (corrected in Segment 19I Item 8).
3. **Friendly-label editor (left) + Operator actions card (right)** — the right-hand pair of the page's one `.card-columns` container, **not** a `.bottom-grid`; this page uses that only for Upload + Danger Zone. The friendly-label editor is the inline editor for the per-session tag-column labels; the Operator actions card (Segment 15F) carries the search / status filter strip and the selection-driven Edit · Inactivate · Activate · Add-new-row button row. See `spec/setup_pages.md` "Operator actions card".
4. Browseable data-preview table of the saved rows (always visible, even while locked) — leftmost checkbox column drives the operator-actions selection; a row flips to inline inputs in Edit (`?edit_id=`) / Add (`?add=1`) mode.
5. **Upload CSV** card — anchored at `#upload-csv`, hosts the bulk import form. Hidden unless the session is `is_editable` (`draft` / `validated`), or while a row is being edited / added.
6. **Danger Zone** card with the **Delete all** confirm-checkbox form. Same gate as the Upload card. Both were keyed to the lock card's `is_ready` until Segment 19I Item 3; on `expired` and `archived` they rendered while their routes answered 409, and the lock card — still `is_ready`-only — does not appear to explain the absence. See `spec/lifecycle.md` §5.

Per-row inline **Edit**, **Add** (`Add new row` until Segment 19I), and bulk **Inactivate / Reactivate** on these three pages shipped in Segment 15F (2026-05-15), joined by a selection-driven **Delete** in Segment 19I — the Operator actions card is the surface; CSV Upload stays the bulk-create path. See `spec/setup_pages.md`.

The Operations Assignments page (§5 above) used to carry a wired **Rule Based Assignment** card with a RuleSet dropdown + Generate button + inline link to a standalone **Rule Builder** page. That card and the Rule Builder page retired in Wave 5 PR 5.1; Band 1 of each instrument card now owns the rule, and the Assignments page focuses on materialisation + reconciliation. See `spec/assignments.md` for the engine contract and the post-Wave-5 page, and `spec/instruments.md` § Band 1 for the rule-authoring surface.

### `/operator/sessions/{id}/instruments` — Instruments

A consolidated page for everything per-instrument: session-wide status + bulk toggles, then one card per instrument with in-place editing for description, response fields, and display fields, ending with a live Preview Instrument table.

**Detailed spec: `spec/instruments.md`.** That doc holds the locked surface definition post-Segment-10D rebuild (single bulk-save form, `?editing={iid}` URL state machine, mutual-exclusion edit lock, zero-RF save guard, RTD card with cascade-confirm and would-empty guards). Multi-instrument UI shipped — each instrument card carries an `Add instrument` / `Add group instrument` / `Replicate` button row, and the per-instrument Delete (gated by a confirm checkbox) replaced the per-card Danger Zone sub-card. Group-scoped instruments — one reviewer answer covering a group of reviewees — landed in Segment 13C.

**Collapsible cards + drag-to-reorder + page breaks
(Segment 18M, 2026-05-27).** Each per-instrument card is
wrapped in a native `<details>` so cards collapse to a
single-row `<summary>` carrying a left-edge grip-dot drag
handle, the title (operator-facing short label with the
muted-italic `Instrument_{id}` fallback when no short label
is set — see `spec/instruments.md` "Title" + the
2026-05-28 operator-identifier policy), which since
Segment 18R Item 2 is a lock-driven view/edit swap — a
read-only span when the card is locked, an inline rename
`<input>` bound to the card's bulk-Save form when unlocked,
committed by the consolidated `/save` (no per-title ✎/✓
button, no immediate `/identity` POST) — two status pills
(`Set up` / `Not set up` +
`Locked` / `Unlocked`), and a right-edge chevron toggle. Default state on first render is
all-collapsed; an `Expand all instruments` /
`Collapse all instruments` pair lives in the Status +
bulk-actions card. Vanilla HTML5 drag-and-drop on the
grip-dot persists a new order via JSON POST to
`/instruments/order`; rejection snaps the card back with
an inline toast. Reorder reloads preserve every card's
exact collapse state via `sessionStorage`. A per-card
`+Page break` button in the action row inserts a page
break (rendered between adjacent instruments as a thin
horizontal divider with `Page break` centred + an inline
`×` delete). The break flag persists on the next
instrument's `starts_new_page` column. Locked decisions —
page breaks are create-+-delete only (never dragged); the
three reorder invariants (no leading / no trailing / no
double-stack) are enforced server-side and surfaced to
the operator via the rejection toast. Full surface
contract in `spec/instruments.md`.

### `/operator/sessions/{id}/setup-invite` — Email Template

Per-session email-template editor for the Invitation, Reminder, and Responses-received outbound emails. Reached from the Email Template tab in the chrome's Setup row.

The page renders, top-to-bottom: chrome (with `Email Template` highlighted as the current Setup tab); a `<div class="tab-strip tab-strip-page">` row of three page-internal nav tabs (`Invitation` / `Reminder` / `Responses received`) using the chrome's `.nav-tab` styling — see `spec/ui_elements.md` §6 "Nav button"; then a two-card body with the email composer on the left (form fields per template + per-field `Reset to default` `.btn-reset` button) and the Merge tags reference card on the right. Cancel + Save sit bottom-left of the composer card; Save is Secondary (routine submit) and renders disabled until any composer field is touched.

The composer's `?template=` query param keeps each tab bookmarkable. The `responses_received` tab also surfaces a "Send this confirmation when a reviewer submits?" checkbox above the composer fields that gates the per-session auto-send.

### `/operator/sessions/{id}/validate` — Setup validation

Operations row tab. Read-only deep-dive of every setup issue, intended for the operator who needs the per-issue breakdown beyond the at-a-glance counts on Home.

- **Page intro** (form-help text): "Read-only view of setup readiness for this session. Errors must be cleared before activation. Warnings can be acknowledged and overridden. Activate from the Workflow card at the top of any session page."
- **Severity counts** (three pills inline): error / warning / info counts.
- **Per-issue list** (rendered via the `operator/partials/validation_results.html` partial) — one entry per issue, with severity pill, source (e.g. "Reviewers", "Assignments"), and human description.

There is no standalone Activate button on this page body; activation fires from the Workflow card's Activate session button. The Validate page does still own the **warnings-detour banner** (`/validate?activate=1`) — the Activate button redirects there when the readiness report has non-blocking findings so the operator can acknowledge them before the underlying `/activate` POST fires.

### `/operator/sessions/{id}/previews` — Previews hub

Operations row tab (label: **Previews**). **Detailed spec: `spec/preview_hub.md`.** Renders read-only previews of what reviewers will see (invitation email, response form, reminder email, responses-received email) for an operator-selected reviewer. Operator-only; bypasses session-status / deadline / acceptance gates.

The reviewer-surface render lives at the satellite route `/operator/sessions/{id}/preview-surface/{page_n}` (Segment 18Q follow-on 2026-05-28) reachable from the hub picker card's "Open full preview" button. The legacy `/operator/sessions/{id}/preview` (singular) is a permanent (308) redirect; its target was 2026-05-28-repointed from `/sessions/{id}/previews#reviewer-surface` (now-dead anchor) to `/preview-surface/1` after the iframe surface card on the hub retired.

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

Reached from the **chrome link row** in the user block (top right), not from the
app-identity text — `.chrome-app-identity` is a `<span>`, not a link. Carries the
app description and the access note it absorbed when 18R Item 6 retired
`/request-access`, so it renders usefully for a signed-in user with no role.
Takes `?return_to=` and renders a "← Back to {context}" affordance.

**Absorbed the Guide's "Before you start" card (Segment 19E).** The Access
card now opens with how to reach the app and sign in — hosted, nothing to
install, single sign-on with an institutional MS365 account, no separate
password —
and states that an address on the operator allowlist lands on the Sessions
lobby. It sits here rather than in the Guide because a reader of the Guide has
already signed in; on `/about` the same facts answer the question a stranger
is actually asking. The lobby's own first-run card covers what an empty lobby
means, so that clause did not travel.

### `/guide` — Guide

The in-app documentation page. Sits **beside `/about`** in the same chrome link
row and takes the same `?return_to=` treatment; the two are siblings and neither
absorbs the other. `/about` is identity and access — what this software is, who
to contact. `/guide` is how to run a session.

Suppressed on its own path, exactly as `/about` is, so the row never offers a
link to the page already being viewed. **Also suppressed for a viewer who
resolves no Guide audiences** (19F PR 3) — they would only be bounced to
`/about`, and offering the link there would hand them a route straight back to
the page that bounced them.

The flag is stamped on `request.state` by `get_or_create_user` and read as
`guide_hidden is not true`, so it **fails open**: a page that never reaches
that dependency still renders the link, and the route's redirect is what
actually decides. Failing closed would hide the Guide from operators on any
page that missed the stamp — a worse error, and a silent one.

**Two chromes read it**, with the same condition. `base.html` carries the
operator chrome and `/about`; `reviewer/_top_bar.html` carries the participant
surfaces (`/me`, the review surface, `/results`, `/collation`), which gained
their Guide link on 2026-09-08 — until then a reviewer or observer holding
roster rows could reach `/guide` and saw the link once they were on `/about`,
but had no route to it from the pages they actually land on. A change to the
condition has to land in both files; `tests/integration/test_guide_scaffold.py`
asserts each of them in both directions.

**Canonical since Segment 19E rung 2.** The material from
`docs/quickstart.md` moved in and that file retired to <!-- path-ref-ok -->
`docs/archive/quickstart.md`; corrections belong here, not there.

**Two sections retired at Segment 19E**, on the author's reading of what the
page owes someone already inside the app. `Before you start` moved wholesale
to `/about` (above). `Getting help` was one sentence pointing at the Validate
page — a troubleshooting tip rather than a section — and is now the last
bullet of `Tips and troubleshooting`. Both removals are asserted in
`tests/integration/test_guide_scaffold.py`, in both directions: the card is
gone from `/guide`, and the content is present where it moved to.

Sections are declared with an audience in `app/web/views/_guide.py` and the
template renders only sections whose audience is visible. **The filter
narrows** as of rung 7 (2026-09-07), where it previously ran against a
constant that admitted everything. `visible_audiences()` unions the viewer's
operator flag — taken from `require_operator`'s own predicate,
`is_operator or is_sys_admin`, rather than restated — with whatever roles are
disclosable to them, via `participants.disclosable_roles`. So an operator
sees the eight operator sections and not the three role-addressed ones; a
reviewer sees `For reviewers`; someone who is both sees both sets.

**A viewer who resolves no audiences is redirected to `/about`** (19F
decision 6, 2026-09-07), which **reverses** rung 7's fallback of showing such
a viewer everything. A stranger seeing more of the Guide than any
role-holder does is backwards. The chrome also stops offering them the Guide
link — note that only `base.html`'s chrome carries one; the participant top
bar (`reviewer/_top_bar.html`) never has, so the conditional bites on
`/about` and the operator pages. The audience contract and the full reasoning
live in `spec/audience_and_identity_model.md`.

**Setup templates (Segment 19E rung 4).** The "Create and set up a session"
card offers `GET /templates/starter.zip` — four generic roster templates with
derived headers and one mock row each, for an operator to fill in *before*
creating the session and upload through Quick Setup. The link sits in the
paragraph that points at each Upload card's column list, since it is that
paragraph's worked example. **The author's Guide rewrite (2026-09-07) moved
what followed it.** The scenario paragraph — the tutorial groups, the
`<Column>.<label>` suffixes it demonstrates — now lives in the `Sample session`
card, where the populated session it describes actually is. What follows the
link here is the friendly-tag-label detour: a screencap of the Reviewer tag
labels editor, then a `.muted` line carrying the consequence that is easiest to
lose — **a bare tag header clears the label a session already has**, because
the header after the period is the one place a label travels, in both
directions. Contract: `spec/csv_contracts.md` §5a.

**Sample session card (Segment 19E rung 5).** A card between "Tips and
troubleshooting" and "For reviewers" — after the operator walkthrough, before
the role-addressed sections, because it is the optional "see it working first"
step rather than part of the sequence above it. It offers
`GET /templates/demo.zip` and four numbered steps: create a disposable
session, attach all four files in Quick Setup, Prepare, then look around a
populated session. A `.muted` line notes that everyone in it is fictional on
`@example.edu`, that the session should be archived when done, and that the
tag labels rename the session's tag columns as the setup templates do. The
card is **not** repeated on the lobby first-run card: that card is for someone
about to set up for real, and the sample session is a detour needing room to
explain. Contract: `spec/csv_contracts.md` §5a.

Whether `/guide` should be viewable **without signing in** is open and belongs
to Segment 20: `resolve_current_user` raises 401 today, so an anonymous Guide
would be this app's first unauthenticated surface, needing both a
`docs/security_posture.md` change and Easy Auth configured on the host.

## Out of scope / forward-looking notes

Recorded for visibility; **none are committed**. Capture additional ideas here as they surface so the taxonomy doesn't get redesigned to accommodate them later.

- **Central Control and Operations Panel** — a cross-session operator surface that aggregates run-state across all of an operator's sessions. Conceivable but ROI unclear, and P1 ("one session at a time") is stronger when the whole app respects it. Not on any segment plan.
- **Adjacent capabilities likely to land sooner:** shared operator permissions on a session, session duplication (sans response data), shared setup data between sessions (e.g. reusable reviewer rosters or instrument templates), session tagging / grouping. These compose with the Overview surface — none would force a redesign of the Setup / Control / Operations groupings.
- **Two-row chrome → single row.** With the Operations row at four tabs after the Invitations + Responses consolidation (and the Outbox de-tabbed) per `spec/operations_pages.md`, the two-row layout is unlikely to collapse. Recorded for completeness; not on any roadmap.
- **Cross-session System Admin** — shipped (Segment 16A + 18S); see §6 above. Sits at Operator's Overview level (above any single session), with its own chrome distinct from the per-session two-row nav. Remaining cross-session admin (system-wide settings, multi-tenant config) is still forward-looking.

## Cross-references

- **`spec/audience_and_identity_model.md`** — audience definitions and customization boundaries. This file covers the operator audience.
- **`spec/visual_style_general.md`** — portable design system.
- **`spec/visual_style_rrw.md`** — Review-Robin chrome instantiation, including all visual specifics elided here.
- **`spec/architecture.md`** — domain entities and layering. Reads upstream of this file.
- **`spec/session_home.md`** — Session Home (Control Panel) functional spec, including layout + lifecycle display-label mapping.
- **`spec/workflow_card.md`** — Workflow card (the single persistent action card that renders on Session Home + every Operations-row page); ten-state cascade, single-row button layout (≤ 4 visible buttons per state, each at 25% column width, inactive hidden), Prepare-then-Activate split + warnings detour.
- **`spec/quick_setup_card_spec.md`** — Quick Setup card on Session Home.
- **`spec/preview_hub.md`** — Preview hub on the Operations row.
- **`spec/operations_pages.md`** — Invitations + Responses functional spec (reviewer-centric Invitations + reviewee-centric Responses; bulk-action affordances live on the Workflow card stepper).
- **`spec/reviewer-surface.md`** — reviewer-facing surface contracts (separate audience).
- **`spec/ui_elements.md`** — implementation catalogue mapping the canonical primitives to CSS classes and templates.
- **`spec/instruments.md`** — locked spec for the Instruments page.
- **`docs/status.md`** — current implementation state and per-route detail.

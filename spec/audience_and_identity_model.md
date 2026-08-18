# Audience and identity model

**Conceptual map of who uses Review Robin and how each audience
relates to the app as a system.** Names the audiences, the auth and
identity assumptions for each, and the design posture (how prominent
the app's identity is, how much customization is permitted, what the
audience is meant to perceive).

This is a level above the visual style spec (which describes chrome
and components) and feeds into it. When the audience model changes
— a new audience added, an auth assumption revised, a customization
boundary moved — this is the first file to update; the visual style
parts follow from the decisions here.

## Audiences

The app has two live audiences and a small number of forward-looking
ones.

### 1. Operator

The person setting up and running review sessions. Configures
reviewers, reviewees, instruments, email templates; activates
sessions; monitors responses; extracts data.

- **Auth.** Institutional credentials (MS365 SSO is the default in
  current target deployments).
- **Account model.** Operators have first-class accounts in Review
  Robin. They sign in, work, sign out. Multiple sessions per
  operator is the norm.
- **Surface.** The operator-facing pages: Sessions list, per-session
  Home / Setup / Operations chrome, About, Settings.

### 2. Reviewer

The person evaluating reviewees within a session. Receives an
invitation, completes one or more instruments for one or more
assigned reviewees, submits responses.

- **Auth.** Institutional credentials (MS365 SSO) by default.
  Magic links available as enhancement / fallback for cases where
  SSO is unavailable (external evaluators, cross-institution
  panels). Reviews are intended to be secure and authenticated;
  unauthenticated review is not a supported posture.
- **Account model.** Reviewers have lightweight accounts in Review
  Robin — they sign in and have a session-spanning identity, but
  the app is not their primary workspace. They visit, complete a
  task, leave.
- **Surface.** A small set of reviewer-facing pages: sign-in,
  reviewer's review list, response form per instrument,
  submission confirmation, error / expired states.

### 3. Reviewee

The reviewee is a live participant audience. W16 + W19 (PRs #1737–#1752) shipped the full results surface:

- A `require_reviewee_in_session` gate in `app/web/deps.py` that
  matches a signed-in user to an active Reviewee row by
  case-insensitive email equality.
- A **Reviewee Results** page at `GET /me/sessions/{id}/results`
  rendering per-instrument sections in raw / anonymized / summarized
  mode, filtered through the per-instrument visibility policy.
- An Acknowledge gesture (`POST …/results/acknowledge`) stamping
  `reviewees.results_acknowledged_at` (idempotent).

Identity match: `reviewee.email_or_identifier` must parse as a
valid email to confer access (confidential reviewees — non-email
identifiers — never grant access; the surface stays unavailable
by construction per `participants.is_email_identified`).

### 3b. Observer (participant-model Phase 1 — partially live)

The observer audience can view collated results across the whole
session (as opposed to a reviewee who sees only their own
results). Phase 1 has:

- An `Observer` model and per-session `observers` table with a
  dedicated CRUD Setup page (gated by `session.observers_enabled`).
- An `observers.cohort_rule` JSON column carrying a per-observer
  cohort match rule authored on the Observers Setup page (see
  `spec/setup_pages.md` "Cohort match rule editor" + `guide/archive/observers.md`).
  Materialised at request time on the collation surface (no
  junction table).
- A `require_observer_in_session` gate in `app/web/deps.py`.
- The **Observer Collation** surface at
  `GET /me/sessions/{id}/collation` — per-instrument 3-row
  table (Row 1 distinct-reviewer headcount + shared aggregate
  over the in-cohort assignment pool / Row 2 distinct-reviewee
  headcount + same aggregate / Row 3 conditional CSV download)
  scoped to the observer's cohort. Identification mode (Raw /
  Anonymized rows / Anonymized summaries) follows the
  per-instrument Band 3 observer policy. Anonymized downloads
  swap reviewer / reviewee names for per-session opaque
  tokens via `app/services/participant_tokens.py`; the same
  tokens are exposed as an operator-side CSV at
  `GET /sessions/{id}/export/participant_tokens.csv` (the
  Extract data tab's Token keys card) for ad-hoc
  deanonymization. MVP shipped 2026-06-02, partition refactor
  + Token keys card 2026-06-03.

Observers are always email-identified (`observers.email` is NOT
NULL); no parse check is needed before identity matching.

### 4. System administrator (three-tier role model)

Since Segment 18S Item 1 the admin surface is a **strict three-tier
hierarchy** with **nested capabilities** and a **config-anchored top
tier**:

| Tier | Stored as | Added / revoked by |
|---|---|---|
| **Operator** | `users.is_operator` | Admins (and super-admins, by nesting) |
| **Admin** | `users.is_sys_admin` | **Super-admins only** |
| **Super-admin** | *derived*: email ∈ `SUPER_ADMIN_EMAILS` (deployer config) | **Azure App Settings only** — never in-app |

**Capability nesting (strict superset).** Everything an operator can do
an admin can do; everything an admin can do a super-admin can do, i.e.
**super-admin ⊇ admin ⊇ operator**. Today's gates already treat sys-admin
as implying operator (`is_operator OR is_sys_admin`); a super-admin
**self-heals** to `is_sys_admin = is_operator = True` on **every** sign-in
(`app/web/deps.py::_reassert_super_admin`, narrow — super-admin emails
only), so every admin/operator gate passes for a super-admin with no
special-casing, and a manual/pre-feature demotion can't strand a
protected account.

**Super-admin is derived, never stored** (`app/auth/roles.py::is_super_admin`
— case-insensitive membership in `SUPER_ADMIN_EMAILS`, plus a fake-auth
fold-in for local dev; see `spec/settings_inventory.md`). No DB column, no
migration; it can't drift from config or be flipped in-app.

**Who can manage whom:**

| Actor ↓ \ can add/revoke → | Operator | Admin | Super-admin |
|---|---|---|---|
| **Operator** | ✗ | ✗ | ✗ |
| **Admin** | ✓ | ✗ | ✗ |
| **Super-admin** | ✓ | ✓ | ✗ (config only) |

Two surfaces:

1. **Workspace allowlist** — admit / revoke `users.is_operator`,
   promote / demote `users.is_sys_admin`, delete `users` rows
   outright, and bulk-remove a user from every session they
   appear on, all via the Sys Admin → Accounts Management page
   (Segment 16A PR 6, reshaped 2026-05-12 to a per-row checkbox
   + bulk toolbar). Server-side guards (`app/services/users.py`):
   - **Actor guard** — `promote` / `demote` require the **actor** to be
     a super-admin (`requires_super_admin` → 403). Operator admit /
     revoke stays admin-gated.
   - **Target guard** — `demote` / `revoke` / `remove_user` /
     `remove_from_all_sessions` refuse when the **target** is a
     super-admin (`protected_super_admin` → 409), sitting *above* the
     count-based `last_admin` floor — it protects a specific identity,
     not just a count.
   - Plus the pre-existing `owns_sessions` / `still_owner` / `sole_owner`
     / `last_admin` guards.
   The Accounts page mirrors these in the UI (three-tier badges;
   Promote/Demote shown only to a super-admin actor; destructive controls
   disabled on super-admin rows) — the server guards are the real
   enforcement.
2. **Per-session diagnostics + explicit self-add** — the Sessions
   Diagnostics page lists every session in the workspace. Since
   **Segment 18S Item 3**, a sys-admin can *read* a non-owned session's
   diagnostics (Outbox, Audit log) but must **own** it to edit. The
   row's **"Manage"** action is a POST to
   `/operator/sys-admin/sessions/{id}/adopt` that **self-adds the
   sys-admin as an owner** (audited `session.owner_added`) and opens the
   session — the explicit, recorded elevation door. Every session
   *mutation* (edit config, lobby rename/tag, remove owners) is gated on
   `require_session_operator` (real ownership); the only relaxations left
   for a non-owner sys-admin are the self-add bootstrap (`owners/add`,
   self-only) and `clone` (which makes them owner of the new copy). No
   shadow editing — every config change is by a recorded owner.

Surfaced in the chrome top-right user card via a `(super admin)` /
`(sys admin)` suffix on the "Signed in as ..." label so elevated state is
visible at a glance.

Multi-tenancy + system-wide settings remain forward-looking.

### 4b. Per-session owner delegation

The session creator becomes the inaugural `session_operators`
row with `role="owner"` at session-create time. Additional
owners are added / removed by current owners via the Owners
card on `/operator/sessions/{id}/edit` (Segment 16B PR 2);
the Add-owner picker offers any workspace operator
(`users WHERE (is_operator OR is_sys_admin) AND NOT EXISTS
(SELECT 1 FROM session_operators ...)`). The service-layer
last-owner guard refuses to leave a session with zero
owners, and the audit log carries `session.owner_added` /
`session.owner_removed` events for every transition.

Per-session role granularity beyond `"owner"` (e.g.
`"viewer"` / `"deputy"`) is deferred to Segment 16B PR 3
pending pilot feedback.

## Identity model: Reviewer-as-form-respondent (Model A, middle position)

The relationship between the reviewer and the app is a deliberate
design choice with security and trust implications. Two coherent
mental models exist:

- **Reviewer signs into Review Robin to complete reviews.** Reviewer
  is a user of the app, recognizes it as their tool, has a
  consistent home in the app.
- **Reviewer authenticates into a form generated by Review Robin.**
  Reviewer relates to a specific review, not to the app; the app
  is substrate. Closer to Microsoft Forms, Qualtrics, Google Forms.

Review Robin adopts a **middle position closer to the first model:**

> The reviewer signs into Review Robin. They recognize it as a
> consistent app across sessions, but they spend most of their time
> in task-focused surfaces (the response form) rather than in
> app-level navigation. Review Robin's identity is persistent and
> visible enough to be a trust anchor, but unobtrusive enough that
> the reviewer's attention stays on their work.

### Why this position

**The case against the pure form-respondent model.** Per-session
visual customization (custom banners, operator-uploaded branding,
session-specific styling) is the natural extension of treating the
reviewer surface as belonging to the operator. But it creates
problems:

- It defeats visual phishing resistance. A reviewer who has
  learned "Review Robin reviews look like X" can spot a phishing
  attempt that doesn't look like X. If the legitimate surface
  varies session-to-session, that signal disappears.
- Customization is the attack surface. The features needed to
  support per-session theming (image uploads, custom HTML,
  operator-controlled copy in security-relevant places) are
  exactly the features that get exploited.
- It works against the app's stated ambition of running
  secure/authenticated reviews. Security benefits from visual
  consistency.

**The case against the pure app-user model.** Treating reviewers as
full users of Review Robin — with cross-session dashboards,
notification centers, app-level navigation — over-invests in a
surface most reviewers visit a few times per year. Reviewers are
not the app's primary users; operators are. Building rich reviewer
features is feature factory work that doesn't serve the actual
need.

**The middle position resolves both.** App identity is consistent
(security, trust, recognition); reviewer surfaces are light
(matches actual usage); operator customization is limited to content
within stable chrome (operators can name their session, add
instructions, identify their institution by name — but cannot
visually transform the surface).

### Operator customization boundary

What operators **can** configure that affects what the reviewer
sees:

- Session name (appears in page header, sign-in confirmation,
  email artifacts).
- Instrument names, question text, response options (the content
  of the review).
- Email template content (invitation, reminder, confirmation
  copy).
- Optional welcome message / instructions, shown above the form
  on first visit. Plain text or limited markdown; no embedded HTML.
- Optional institution name (small, supplementary, displayed near
  the session name in the page header).
- Optional contact information for questions (operator email or
  similar).

What operators **cannot** configure:

- Visual style — colors, typography, layout, spacing. App-level.
- Banner images, logos, or any uploaded visual content.
  (Possible future exception: institution wordmarks drawn from a
  vetted institutional registry rather than operator-uploaded.
  Out of scope for current work.)
- The Review Robin identity in sign-in, footer, or persistent
  chrome.
- Any chrome that could be visually confused with non-Review-Robin
  branding.

The operator's customization vector is **content within stable
chrome.** They have meaningful presence (their session is named,
their instructions appear, reviewers know who's running it)
without opening surfaces that undermine visual trust.

## Identity model: Operator-as-app-user

The operator's relationship is straightforward:

> The operator uses Review Robin as a tool. They have a first-class
> account, navigate the app's structure, run sessions, and rely on
> the app's affordances. Review Robin is their workspace for review
> management.

This entails normal app-like patterns: a persistent identity in the
top-right ("Signed in as..."), app-level navigation (Sessions,
About, Settings), full chrome and structure on session-scoped pages.
None of the trust-anchor concerns that constrain the reviewer
surface apply here in the same way; the operator chose to use this
app and uses it regularly.

## Auth posture

Both audiences authenticate. Unauthenticated access is not
supported for either:

- **Operators** sign in via institutional SSO (MS365 in current
  deployments). No operator content is reachable without auth.
- **Reviewers** sign in via institutional SSO by default; magic
  links are an enhancement supporting cases where SSO is unavailable
  (e.g., external reviewers from outside the institution). The
  invitation email contains a sign-in link, not a tokenized
  bypass-auth link. Following the sign-in link delivers the
  reviewer to SSO; after authenticating, they are deep-linked to
  the relevant response surface.

Magic links exist as an explicit fallback, not the primary mode.
The "tokenized link replaces auth" pattern is **not** the model;
that pattern works against the secure-review ambition. Magic links
in Review Robin authenticate the reviewer (proving possession of
the email account) but do not bypass identity.

**Implication for chrome:** reviewer-facing chrome assumes the
reviewer is authenticated whenever they see a response form. This
means a small "Signed in as [Name]" affordance is appropriate
(confirms correct identity) and a sign-out option exists (allows
the reviewer to leave cleanly on a shared computer). These are
unobtrusive but present.

## Surface structure

Each audience has its own surface with its own chrome conventions.
Components and visual vocabulary (palette, typography, spacing,
button shapes, etc.) are uniform across surfaces; chrome and
navigation patterns are audience-specific.

| Audience | Surface | Chrome weight | Navigation richness |
|---|---|---|---|
| Operator (in session) | Per-session pages | Heavy: two-row chrome, status strip, lifecycle context | Rich: Setup pages, Operations pages, sub-pages |
| Operator (out of session) | App-level pages | Light: minimal top bar, user menu | Sparse: Sessions, About, Settings |
| Reviewer | Response surface | Light: page header, role-navigator chips | Sparse: `/me` dashboard, response form, summary |
| Reviewee | Results surface | Same reviewer chrome with role-navigator chips | `/me/sessions/{id}/results` (live — raw / anonymized / summarized modes + Acknowledge card, W16 + W19) |
| Observer (Phase 1+) | Collation surface | Same reviewer chrome with role-navigator chips | `/me/sessions/{id}/collation` — per-instrument 3-row table (reviewer / reviewee aggregates + conditional CSV download); MVP shipped 2026-06-02 |

The discipline: **components are universal, chrome is audience-
local.** A submit button looks the same to operators and reviewers.
A page header containing a lifecycle badge is operator-only. A tab
strip showing instrument completion progress is reviewer-only.
The visual style spec (especially Part 1) defines the universal
component vocabulary; Parts 2 and 3 define each surface's chrome
conventions.

## Cross-references

- **Visual style spec — Part 1** (general): defines the universal
  component vocabulary used across all surfaces.
- **Visual style spec — Part 2** (Review Robin operator surface):
  applies the universal components to operator-specific chrome —
  two-row session navigation, lifecycle treatments, status strip.
- **Visual style spec — Part 3** (non-session and reviewer
  surfaces): applies the universal components to non-session
  operator chrome and to reviewer-facing chrome. Reads downstream
  from this file for the audience and identity assumptions.
- **`spec/operator_ui_concept.md`**: page taxonomy and navigation principles
  for the operator surface.

## Out of scope / forward-looking notes

Recorded for visibility; **none committed.**

- **Reviewee surface** is live (W16 + W19). The Observer
  collation surface (W17) shipped 2026-06-02 as the MVP — per-
  instrument 3-row table + cohort-scoped CSV downloads via
  `app/web/routes_reviewer/_collation.py`.
- **System administrator surface.** Shipped — the three-tier
  operator / admin / super-admin model + Accounts Management +
  Sessions Diagnostics (Segment 16A + 18S); see §4 above.
  Multi-tenancy + system-wide settings remain forward-looking.
- **Vetted institutional wordmarks** as a constrained customization
  vector for operators — drawn from a registry rather than uploaded.
  Possible future enhancement to the customization boundary; not
  currently planned.
- **Cross-session reviewer dashboard.** Currently the reviewer's
  list is a simple per-reviewer enumeration. A richer dashboard
  (notifications, history across sessions, review analytics for
  the reviewer themselves) is conceivable but not aligned with the
  current "reviewers are not primary users" posture.
- **Embedded reviewer surface** (response form rendered inside a
  host system like an institutional portal or LMS). Would push
  toward the form-respondent model, away from the current middle
  position. Out of scope; would require revisiting this document.

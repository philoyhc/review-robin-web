# Segment 11D — v2 sweep, non-session-centric pages (#21b)

Implementation plan for porting the eight remaining non-session-centric templates onto `body.ui-v2`. Sibling to Segments 11A (Tier 3 polish + chrome rebuild + session-centric v2 sweep) and 11B (Session Home rebuild) — finishes the v2 vocabulary rollout that the chrome rebuild started.

The v2 vocabulary is settled; this segment is mostly mechanical per-template work. Reference: `spec/visual_style_general.md`, `spec/visual_style_rrw.md` "Non-session and reviewer chrome", `spec/ui_elements.md` (canonical primitives), and `guide/ui_checklist.md` "What v2-covered means" (the per-page acceptance check).

## Status

**Shipped 2026-05-04** as PRs A → B → C. PR A swept the four operator-non-session stubs (`sessions_list`, `session_new`, `about`, `me_debug`) onto `body.ui-v2` and landed the return-to-origin helper. PR B added the two-row session chrome to `session_edit` and restructured the sessions-list lobby from a `<table>` to a flex column of `.card.session-card` rows. PR C introduced the lighter reviewer top-bar variant via a new `{% block top_bar %}` in `base.html` plus the `reviewer/_top_bar.html` partial, and swept the three reviewer templates onto `body.ui-v2 reviewer` with D5/D6/D7 (status icons, banner family, page header) applied to the response surface.

## Scope

In:

- Port the eight templates currently off `body.ui-v2` onto v2:
  - **Operator non-session pages** — `sessions_list.html`, `session_new.html`, `about.html`, `me_debug.html`.
  - **Operator sub-page of Home** — `session_edit.html` (gains the two-row session chrome with no tab active per spec, plus v2 primitives).
  - **Reviewer pages** — `reviewer/dashboard.html`, `reviewer/review_surface.html`, `reviewer/invite_mismatch.html`.
- Add a small **return-to-origin** helper for About and `/me/debug` per `spec/visual_style_rrw.md` "Return-to-origin behavior" (capture origin via `?return_to=…`; render "← Back to …" link near the top of the page body; default to `/operator/sessions` when no origin recorded).
- Sweep affected tests for old-markup assertions (`pill-info` / `pill-warning` strings on the reviewer dashboard, the legacy `<table>` shape on Sessions list, etc.).
- Tick each template in `guide/ui_checklist.md` as it lands.

Out:

- New visual primitives. Everything 11D needs already exists — `body.ui-v2` cards / banners / buttons / pills, the `lifecycle_label` Jinja filter, the `placeholder_card` macro, the `.card.next-action` treatment. If a sweep surfaces a missing primitive, escalate as a follow-on rather than inventing a new one inside this segment.
- Reviewer-surface pilot polish bundle (catalog `unfinished_business.md` #32) — that's Segment 15. 11D ports the existing surface onto v2 only; pilot-feedback-driven changes land later.
- Operator settings page. Doesn't exist yet; the spec mentions it as a future destination for the user-menu Settings link, but no template ships in 11D.
- AG Grid replacement of the reviewer-surface table (#33) — Segment 15.

## Visual-style decisions this segment makes

11D is mostly mechanical, but it does cross three deliberate visual-style boundaries that didn't apply during 11A / 11B. Settle them up front so per-template work doesn't get re-litigated.

### D1 — Operator user menu structure (non-session top bar)

Per `spec/visual_style_rrw.md` "Non-session operator pages → Top bar":

- **Left:** "Review Robin Web App (version {dev})" — already in `base.html`, rendered in `text-secondary`. No change.
- **Right user menu:** today shows "Signed in as …" + "Sign out". The spec asks for **About** and **Settings** as additional inline links between the identity line and Sign out (with **return-to-origin** behaviour — see D3). Settings has no template yet, so **11D adds About only**; the Settings link slot waits for a Settings page to ship. The user menu stays inline (three items: identity, About, Sign out); promotion to a dropdown is a future concern when the menu grows.

### D2 — Reviewer top bar variant (new chrome branch)

Per `spec/visual_style_rrw.md` "Reviewer-facing pages → Top bar", reviewer pages render a **lighter** top bar:

- **Left:** "Review Robin" — small, `text-secondary`. **No version.**
- **Right user menu:** "Signed in as [Reviewer Name]" + "My Reviews" (only when the reviewer has more than one review pending or completed; suppressed otherwise) + "Sign out".
- **No breadcrumb.** Operator-style breadcrumbs don't apply to reviewer surfaces.

`base.html` today renders the operator chrome unconditionally. 11D introduces a single template branch (the cleanest path is a new `{% block top_bar %}` whose default block emits the operator chrome and which the reviewer templates override). The branch lives entirely in `base.html` plus a one-line override in each of the three reviewer templates.

### D3 — Return-to-origin affordance (About / future Settings)

Per `spec/visual_style_rrw.md` "Return-to-origin behavior":

- About and `/me/debug` are detour destinations. Operator opens them, then wants to return to whatever they were doing.
- Origin captured via `?return_to=<path>` query param, allowlisted to `/operator/sessions`, `/operator/sessions/{int}`, `/operator/sessions/{int}/{tab}`, `/reviewer`, `/reviewer/sessions/{int}`. Anything outside the allowlist falls back to `/operator/sessions` (the operator's natural lobby).
- The page renders **"← Back to {context}"** in `accent-blue`, near the top of the page body (above the H1). Label disambiguates by context where it can: "← Back to Sessions" for the sessions list, "← Back to {session name}" for a session, "← Back to your reviews" for a reviewer page.
- Plumbing: a small helper in `app/web/breadcrumbs.py` (or a new tiny module) parses + validates `request.query_params.get("return_to")` and threads `(return_to_url, return_to_label)` into the template context.

### D4 — Sessions list lobby: cards-vs-table

Per `spec/visual_style_rrw.md` "Operator's Overview (Sessions list)" §, the lobby renders a **list or grid of session cards**, not a `<table>`. Each card carries: session name (linked), lifecycle state badge (using `lifecycle_label` display labels), deadline, brief setup-readiness summary (count badges or single status summary).

The current `sessions_list.html` is a 7-column `<table>`. Migrating to cards is a larger restructure than just swapping classes — the column headers go away, layout becomes a flex column of `.card` rows, and the per-row Action buttons (Access / Delete) move into each card.

**Decision:** PR B does this restructure. It's the bigger of the two PR B sub-pieces and is what lets the lobby read as the "operator's natural landing page" the spec calls for.

> **Revisited 2026-05-04 (post-11D):** the cards layout was reverted in favour of a v2 `<table>` inside a single `.card`. At the lobby, dense scannable rows beat per-card framing; the trimmed five-column shape (Name / Code / Status / Deadline / Actions) reads cleaner than the per-card stack. The header bar with "Create new session" Primary flush right and the empty-state `.btn-cta` promotion are kept. Spec updated in the "Operator's Overview" § with a History note.

### D5 — Status icons on the response surface

Per `spec/ui_elements.md` §9 "Status-symbol indicators", the inline-styled `✓` / `⚠` glyphs in `review_surface.html:190,193` migrate to `.status-icon-complete` / `.status-icon-incomplete` classes. New classes land in the `body.ui-v2` block in `base.html`:

```css
body.ui-v2 .status-icon-complete   { color: var(--accent-green); font-weight: 600; }
body.ui-v2 .status-icon-incomplete { color: var(--accent-amber-dark); font-weight: 600; }
```

No new tokens; reuses the existing palette.

### D6 — Reviewer-surface banners

Per `spec/ui_elements.md` §5, the four `.warning-banner` / one-off banners on the reviewer surface migrate to the canonical four-variant `.banner` family:

| Current | New |
|---|---|
| Preview-mode notice (currently a recoloured-blue `.warning-banner`) | `.banner.banner-info` |
| `?saved=ok` flash | `.banner.banner-success` (or no banner if it can be implicit) |
| `?submitted=ok` flash | `.banner.banner-success` |
| Missing-required acknowledge prompt (`acknowledge_missing` checkbox) | `.banner.banner-warning` |
| Session-closed / not-accepting state | `.banner.banner-warning` |

### D7 — Reviewer-surface page header

Per `spec/visual_style_rrw.md` "Response surface → Page header", the reviewer surface renders:

- Session name as **H1**.
- Deadline as a small line in `text-secondary` near the H1.
- (Optional, future) institution / operator name; (optional, future) operator-configured welcome message — both **deferred** to whichever segment ships those data fields. 11D doesn't add new schema.

The current template's `<h1>{{ session.name }}</h1>` (line 15) already does the H1. Add a `.form-help`-style small line below it for the deadline; everything else 11D leaves alone.

### Out of scope (deliberate)

- **Multi-instrument tab strip on the response surface** (`spec/visual_style_rrw.md` "Multi-instrument navigation"). The current reviewer surface loops by instrument with section headings; the spec calls for a single horizontal tab strip when there's more than one instrument. This is a structural change with its own UX considerations (per-tab completion indicator, free movement, save-on-tab-change). **Defer to Segment 15** under reviewer-surface polish (catalog `unfinished_business.md` #32).
- **Sign-in surface.** Easy Auth handles sign-in today; there's no in-app sign-in template. Spec mentions it as a future concept.
- **Submission-confirmation page.** Currently folded into `review_surface.html` via the `?submitted=ok` flash banner. The spec describes it as a separate "thank you" page; **defer** to whichever segment introduces the standalone page.
- **Error / expired states for reviewers.** The spec says reviewer pages should render error states without operator vocabulary. The existing `invite_mismatch.html` already does this for the token-mismatch case; broader error / expired states are out of scope for 11D.

## Templates and gap against the spec

For each template, the **Visual style** column names the canonical primitives the sweep applies and the spec sections that govern them. The **Behaviour** column names anything beyond a primitive swap (e.g. structural restructuring, new helpers).

| Template | LOC | Visual style | Behaviour |
|---|---|---|---|
| `sessions_list.html` | 44 | `body.ui-v2`. Operator non-session top bar (D1). Page body uses **session cards** (D4) — a flex column of `.card` rows, each carrying session name (link, body text), lifecycle pill via `lifecycle_label` (already in place from PR #381), deadline (small text-secondary), Access link (Secondary), Delete link (legacy `<a class="btn danger-solid">` stays — #23 in Segment 15). H1: "Sessions". Top-right primary "Create new session" → Primary; on empty state, becomes the page's prominent affordance per `spec/visual_style_rrw.md` "Operator's Overview". | None beyond the table → cards restructure (D4). |
| `session_new.html` | 32 | `body.ui-v2`. Operator non-session top bar (D1). Form labels above inputs (`text-primary`, medium-500) per `spec/visual_style_general.md` §Forms; inputs `8/12` padding, focus state in `accent-blue`; helper text via `.form-help`. Submit → Primary; Cancel anchor → Secondary. Single `.card` wraps the form. | None. |
| `about.html` | 15 | `body.ui-v2`. Operator non-session top bar (D1). Return-to-origin link (D3) at top of body, in `accent-blue`. Body content sits in a single `.card` or as loose markup (whichever reads cleaner — the page is currently a couple of paragraphs). | New return-to-origin helper (D3) — a small parser + allowlist + label-by-context. Used by both `about.html` and `me_debug.html`. |
| `me_debug.html` | 101 | `body.ui-v2`. Operator non-session top bar (D1). Return-to-origin link (D3). Claim list as a `<dl>` or `<table>` with v2 table treatment (`bg-muted` header, row-only borders, `12/16` cell padding) per `spec/visual_style_general.md` §Tables. Sign-out / sign-out-as-X anchors → Secondary. | Inline styles retired (the page has a few inline `style="…"` blocks today). |
| `session_edit.html` | 37 | `body.ui-v2`. **Gains the two-row session chrome** with no tab active per `spec/visual_style_rrw.md` "Sub-pages of Home" — include `operator/partials/session_top_nav.html` with `current_page = ""` plus the status row partial. Form lives inside a single `.card`; fields use v2 form treatment per `spec/visual_style_general.md` §Forms. Save button → Primary; Cancel → Secondary. H1 "Edit Session" inside the card. | Verify `session_edit` route already passes `status_pills` to the template (the partial requires it). If not, add the dependency to the route. |
| `reviewer/dashboard.html` | 52 | `body.ui-v2 reviewer`. **Reviewer top bar** (D2) — "Review Robin" identity, "Signed in as …" + "My Reviews" (suppress when only one review) + "Sign out". H1 "Your Reviews" inside `.card`. Per-row status pill: keep `pill-info` / `pill-warning` (the v2 aliases for `pill-count` / `pill-empty`); a `pill-success` for the submitted state may read better than `pill-info` and is worth a small tweak. Empty-state copy in `text-secondary` per `spec/visual_style_rrw.md` "Reviewer's review list → Body" ("You have no pending reviews."). | None beyond the body-class addition + reviewer top bar branch in `base.html` (D2). |
| `reviewer/invite_mismatch.html` | 22 | `body.ui-v2 reviewer`. Reviewer top bar (D2). Body content — currently the email-mismatch error — renders as a `.banner.banner-warning` near the top of the page body, per `spec/visual_style_rrw.md` "Error / expired states" (no operator vocabulary; plain language; surface contact info if present). | None. |
| `reviewer/review_surface.html` | 254 | `body.ui-v2 reviewer`. Reviewer top bar (D2). **Page header** per D7: H1 = session name (already in place); deadline as a small `text-secondary` line below it. Inline `✓` / `⚠` glyphs migrate to `.status-icon-*` classes (D5). Banners migrate to the four-variant `.banner` family (D6). Save → Primary; Submit → Primary (only when on a different per-instrument page section, otherwise Secondary — single Primary per page region per `spec/visual_style_general.md` §Buttons P1, but Save / Submit are usually surfaced together; pick Save = Primary, Submit = Secondary unless review prefers the inverse). Clear all → Destructive. Cancel → Secondary. Per-instrument cards use the default `.card` treatment; existing `.rs-help-card` family stays as-is per `spec/ui_elements.md` §4. Column-width hint classes (`.rs-narrow` / `.rs-reviewee` / `.rs-textlong`) stay. | New `.status-icon-*` classes added to `base.html` v2 block (D5). |

## PR sequence

The recommended sequence is **A → B → C**, ordered by surface familiarity. A is the smallest set of operator stubs; B is the lobby + the sub-page; C is the reviewer surface and is the heaviest test churn. Land them in order; don't fold A+B unless review wants — keeping A small means faster iteration.

**Pre-PR-A verification spike** (not a PR — record findings in PR A's description). Two cheap checks before the first sweep PR lands:

1. **Reviewer top bar branch.** Confirm whether `base.html` has any body-class switch for the reviewer surface today, or whether the operator chrome renders on every page. If the latter, PR C will need a small `base.html` change to render the lighter "Review Robin" top bar when `body.ui-v2.reviewer` (or similar) is set. Surface size: <15 lines.
2. **Test sweep size.** Grep `tests/integration/` for assertions on the eight templates' current markup — focus on `class="pill-warning"` / `class="pill-info"` literals on the reviewer dashboard, `<h1>Your Sessions</h1>` / `<h1>Edit Session</h1>` literals, and the reviewer-surface preview-mode banner copy. Note hit count in PR description so reviewers know the sweep was bounded.

### PR A — Operator non-session stubs

`sessions_list.html`, `session_new.html`, `about.html`, `me_debug.html`.

- Each gets `{% block body_class %}ui-v2{% endblock %}`.
- `sessions_list.html` swaps the per-row `<a class="btn">` for Secondary styling (Primary stays reserved for the page-level "Create new session" affirmative). Lifecycle pill in the Status column stays — already on the `lifecycle_label` filter from PR #381.
- `session_new.html` form treatment per `body.ui-v2` defaults; Cancel link sits beside Submit in a `.btn-pair`.
- `about.html` and `me_debug.html` gain the return-to-origin affordance: a one-line helper in `app/web/breadcrumbs.py` (or a new tiny module) reads `request.query_params.get("return_to")`, validates against an allowlist (`/operator/sessions`, `/operator/sessions/{id}`, `/reviewer`, `/reviewer/sessions/{id}`), and threads the safe value into the template context. Both templates render `<a class="back-link" href="{{ return_to_url }}">← Back to {{ return_to_label }}</a>` near the top of the body.
- Cross-page `routes_about.py` / `routes_auth.py` accept `return_to` and pass it through.
- Cross-page `routes_operator.py` / `routes_reviewer.py` user-menu links populate `return_to` with the current URL when generating the About / `/me/debug` href.

Test impact: small. Tick the four templates in `guide/ui_checklist.md`.

### PR B — Sessions list polish + Edit Session sub-page chrome

Splits two distinct shapes:

**B1 — `session_edit.html` gains chrome.** Wrap the existing form in the standard `<div class="session-nav-card">` that includes `operator/partials/session_top_nav.html` (with `current_page = ""` so no Setup / Operations tab activates) plus the status row partial. Form lands inside a `.card` with a clear H1 ("Edit Session"). Save → Primary; Cancel → Secondary. This brings `session_edit.html` in line with what `spec/visual_style_rrw.md` "Sub-pages of Home" prescribes.

**B2 — `sessions_list.html` lobby polish.** PR A swept the basics; this slice tightens what reviewers will see. H1 to "Sessions" or "My Sessions" (pick one; Sessions is shorter and the chrome already provides "yours" context). Empty-state card sized + worded to match the Activated-session card list visually (don't make the empty state look like a rendered session row). The "Create new session" anchor → Primary, top-right of the list area per spec ("New Session" in the top-right of the list area; when empty, the page's prominent affordance, rendered larger with explanatory text").

Test impact:

- `tests/integration/test_session_edit_delete.py` may have `<h1>Edit Session</h1>` assertions that survive the rewrite. Verify.
- `tests/integration/test_chrome_breadcrumbs.py` may reference the absence of chrome on `session_edit.html`; flip those assertions.

### PR C — Reviewer surface

`reviewer/dashboard.html`, `reviewer/invite_mismatch.html`, `reviewer/review_surface.html`. Plus the small `base.html` branch that renders the lighter reviewer top bar when the reviewer body class is set.

- `base.html`: introduce `body.ui-v2.reviewer` (or similar — name pick at implementation time). The reviewer top-bar block reads "Review Robin" (no version), with the user menu containing "Signed in as …" + "My Reviews" (when applicable) + "Sign out" per spec.
- The three reviewer templates set `body_class = "ui-v2 reviewer"` (multi-class block).
- `reviewer/review_surface.html` is the heavy lift — preview-mode banner → `.banner.banner-info`; status-icon-complete / status-icon-incomplete classes replace the inline-styled `✓` / `⚠` glyphs (and the new classes land in `base.html` v2 block alongside the rest of `spec/ui_elements.md` §9). Save / Submit / Clear button roles per visual style spec.

Test impact: heaviest in the segment.

- `tests/integration/test_reviewer_response_flow.py` (786 LOC) — many assertions on banner copy, button labels, table presence. Most should survive since I'm keeping the same DOM ids / form actions; verify when sweeping.
- `tests/integration/test_reviewer_surface_display_fields.py` (230 LOC) — display-field column assertions; should survive untouched.
- `tests/integration/test_invitations.py` and `test_monitoring.py` may render the reviewer dashboard via cross-references; check.

## Implementation pointers

- **Template diffs are mechanical.** Each template starts with `{% extends "base.html" %}` and probably already declares title + content blocks. Add `{% block body_class %}ui-v2{% endblock %}`. Then walk the template top-to-bottom: card → `.card` (and pick a kind from `.card.lock` / `.card.danger-zone` / `.card.placeholder` / `.card.next-action` if any apply); button → role per `spec/visual_style_general.md`; pill → canonical class; helper text → `.form-help`. Reference: the diff that put `session_reviewers.html` on v2 (PR #340-ish era) is the canonical example.
- **Return-to-origin allowlist.** Tight allowlist of exact paths + path patterns (`/operator/sessions`, `/operator/sessions/{int}`, `/operator/sessions/{int}/{tab}`, `/reviewer`, `/reviewer/sessions/{int}`). Reject anything else and fall back to `/operator/sessions`. Don't accept arbitrary external URLs.
- **Reviewer top-bar branch in `base.html`.** Single new conditional block; keep the operator chrome's current behaviour as the default. The simplest implementation: `{% if 'reviewer' in body_classes %}` style switch. If `body_class` is awkward to inspect inside `base.html`, add a separate `{% block top_bar %}…{% endblock %}` that the reviewer templates override; default block emits the operator top bar.
- **`session_edit.html` chrome.** The `session_top_nav.html` partial already supports `current_page = ""` (or the absence of a current page) — just include it. Status row partial reuses the same `status_pills` context the route already builds (verify `session_edit` route passes `status_pills`).
- **`status-icon-*` classes for the reviewer surface.** Define inline in `base.html` v2 block: `.status-icon-complete { color: var(--accent-green); font-weight: 600; }`, `.status-icon-incomplete { color: var(--accent-amber-dark); font-weight: 600; }`. No new tokens needed.

## Test impact summary

PR A: small — mostly snapshot-style assertions on operator stubs that survive the v2 sweep. Plan to update 1–3 lines in `test_chrome_breadcrumbs.py`.

PR B: medium — `session_edit.html` gains chrome, which existing tests that check for absence of chrome will fail on. Update those assertions. `sessions_list.html` test impact small.

PR C: heaviest — the reviewer-surface test suite is 786 LOC. Most should survive (DOM ids and form actions unchanged); plan a careful pass through `test_reviewer_response_flow.py` for any banner / button literal assertions that need updating to v2 copy.

## Out of scope (cross-references)

- **#23** — Sessions-list per-row Delete button (anchor → POST form). Deferred to Segment 15. PR A leaves the existing anchor-to-`#danger-zone` behaviour intact.
- **#24** — Operator-editable email template editor at `/operator/sessions/{id}/setupinvite`. Independent of 11D — already on v2 as a placeholder; the editor is its own segment-level work item.
- **#5** — Audit-event `detail` schema convention. Independent; gates Segment 12.
- **Segment 11C** — Operations consolidation (Invitations + Responses). Independent surface; can ship in parallel with 11D.
- **Operator Settings page.** Not yet specified beyond the user-menu link mention; if introduced, it'll follow the same non-session chrome conventions 11D establishes.

## Doc impact

- Tick the eight templates in `guide/ui_checklist.md` § "v2 sweep" as each PR lands.
- Update `guide/todo_master.md` and `guide/segment_11A_cleaning_up_unfinished_business.md` to mark `#21b` shipped once PR C merges.
- `docs/status.md` gains a 2026-MM-DD timeline entry "Segment 11D shipped (v2 sweep across the eight remaining non-session-centric templates; reviewer top bar variant; About / me_debug return-to-origin)".

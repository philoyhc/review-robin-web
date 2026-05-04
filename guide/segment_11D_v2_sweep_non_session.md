# Segment 11D — v2 sweep, non-session-centric pages (#21b)

Implementation plan for porting the eight remaining non-session-centric templates onto `body.ui-v2`. Sibling to Segments 11A (Tier 3 polish + chrome rebuild + session-centric v2 sweep) and 11B (Session Home rebuild) — finishes the v2 vocabulary rollout that the chrome rebuild started.

The v2 vocabulary is settled; this segment is mostly mechanical per-template work. Reference: `spec/visual_style_general.md`, `spec/visual_style_rrw.md` "Non-session and reviewer chrome", `spec/ui_elements.md` (canonical primitives), and `guide/ui_checklist.md` "What v2-covered means" (the per-page acceptance check).

## Status

Planning. Sized as **3 PRs** in dependency order; each independently shippable. Plan to land before Segment 12 starts so the operator + reviewer surfaces are uniformly on v2 when export ships.

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

## Templates and gap against the spec

| Template | LOC | What changes |
|---|---|---|
| `sessions_list.html` | 44 | Set `body.ui-v2`. Light non-session top bar (already in `base.html`). H1 to "Sessions" or "My Sessions" per spec. Replace the bare `<table>` with v2 table treatment (already in `base.html` v2 block). Lifecycle column already routes through `lifecycle_label` (PR #381). The two per-row buttons (`<a class="btn">Access</a>`, `<a class="btn danger-solid">Delete</a>`) need the role swap: Access → Secondary; Delete is a navigation link to the session's `#danger-zone`, deferred-fix-or-real-delete is **#23** (Segment 15) — leave as-is for now. The bottom "Create new session" link → Primary (single page-level affirmative action). |
| `session_new.html` | 32 | Set `body.ui-v2`. Form labels / inputs / helper text → v2 form treatment (`.form-help`, `8/12` padding). Submit button → Primary; Cancel → Secondary. |
| `about.html` | 15 | Set `body.ui-v2`. Add the **return-to-origin** affordance: read `?return_to=…` from the URL, render "← Back to …" link in `accent-blue` at the top of the body, default to `/operator/sessions`. Light cleanup of any inline styles. |
| `me_debug.html` | 101 | Set `body.ui-v2`. Same return-to-origin affordance as `about.html`. The headers / claim list switches to v2 typography; if any inline-styled tables, swap for v2 tables. |
| `session_edit.html` | 37 | **Gains the two-row session chrome** (currently has none) per `spec/visual_style_rrw.md` "Sub-pages of Home (Edit Session): chrome renders normally with no tab active". Wrap the form body in a `.card`. Form fields → v2 form treatment. Save button → Primary; Cancel → Secondary. Drop the `.page-grid` / `.fill-col` two-column layout if it doesn't read as natural inside a card; otherwise tokenize. |
| `reviewer/dashboard.html` | 52 | Set `body.ui-v2`. Light **reviewer top bar** ("Review Robin", no version) — currently `base.html` renders the operator chrome unconditionally; needs a body-class branch (e.g. `body.reviewer-surface` or just `body.ui-v2.reviewer`). Status pill column: `pill-info "submitted"` and `pill-warning "in progress"` are using the v2-aliased pills already; verify they read right under the new treatment. H1 → "Your reviews" stays. Linkified table cells → v2 table hover. Empty-state card → standard v2 `.card`. |
| `reviewer/invite_mismatch.html` | 22 | Set `body.ui-v2`. Whatever banner / card the page renders should use the `.banner.banner-warning` family or the standard `.card`. Reviewer top bar applies. |
| `reviewer/review_surface.html` | 254 | Heaviest sweep. Set `body.ui-v2`. Reviewer top bar. Per-instrument cards on v2 default treatment; the per-cell inline-styled severity icons (`✓` / `⚠`) migrate to `.status-icon-complete` / `.status-icon-incomplete` per `spec/ui_elements.md` §9. Save / Submit / Clear buttons follow the Primary / Secondary / Destructive split. Preview-mode banner should use `.banner.banner-info`. Existing column-width hint classes (`.rs-narrow`, `.rs-reviewee`, `.rs-textlong`) stay. |

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

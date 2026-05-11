# UI restructure checklist

Tracks UI restyling progress across two passes:

- **v1 restructure (complete 2026-04 → 2026-05)** — the
  original two-column layout + six canonical `.btn` modifiers
  from `spec/domain_assumptions.md` pass.
- **v2 sweep onto `body.ui-v2` (effectively complete
  2026-05-10)** — applies the canonical primitives in
  `spec/visual_style_general.md` + `spec/visual_style_rrw.md`
  (refined card / button / pill / chrome treatments; hover
  by fill; recovery-action color family). Reference
  implementation is `session_reviewers.html` + the
  `body.ui-v2`-scoped block in `base.html`. Every operator
  + reviewer page below has been swept; the file stays as a
  per-template record so future template additions get a tick
  when they pick up v2 from day one.

A page can be on v1 (legacy look) or v2 (canonical
primitives) — the two sections track them separately. The v1
section is a historical record only.

---

## v2 sweep onto `body.ui-v2`

### Cross-cutting

- [x] `base.html` — `:root` design tokens (palette / type /
  spacing / radii) + `body.ui-v2`-scoped block covering cards
  (default + `.card.lock` + `.card.danger-zone`), Primary /
  Secondary / Destructive / Outline-amber buttons (with hover
  by fill per P6), tables (row-only borders, generous padding),
  forms (`.form-help` / `.form-error`), pills
  (`.pill-count` / `.pill-empty` / `.pill-lifecycle-*`),
  banners (`.banner.banner-{info|success|warning|error}`),
  chrome (lighter Home anchor, bold tab labels, per-row tab
  markers).
- [x] Per-row tab markers on both v1 and v2 chrome
  (`.tab-strip-setup` → grey, `.tab-strip-ops` → soft green).

### Operator pages

- [x] `session_reviewers.html` — `/operator/sessions/{id}/reviewers`
- [x] `session_reviewees.html` — `/operator/sessions/{id}/reviewees`
- [x] `session_assignments.html` — `/operator/sessions/{id}/assignments`
- [x] `session_setupinvite.html` — `/operator/sessions/{id}/setupinvite` (Segment 11E PR 2: real editor — two-card `.bottom-grid` with email-shape composer left + merge-tag list / Save / Cancel right; per-template selector via `?template=invitation|reminder`; per-field "Reset to default" forms; Save renders `disabled` until a form input changes (no flash banner). PR #468 polish: Invitation / Reminder tabs out of card, normal-sized, flushed left.)
- [x] `operator_settings.html` — `/operator/settings` (Segment 11E PR 4 + #468: per-operator SMTP credentials with encrypted-at-rest password; ``← Back to {context}`` link from `?return_to=` per `app/web/return_to.py`; Save/Cancel flushed bottom-right; danger-zone Clear-all-settings card.)
- [x] `session_previews.html` — `/operator/sessions/{id}/previews` (Segment 11F Part 1 — Reviewer Experience Preview hub. PR A: reviewer picker (typeahead + Apply / Prev / Next / Random; `?reviewer_email=` URL state) split into `Previewing as` left + `About this reviewer` right inside a `.bottom-grid`. PR B: tabbed email previews region (Invitation / Reminder / Responses-received) with only Invitation wired live; Reminder + Responses-received render disabled until 11F Part 2. PR C: reviewer-surface card below an `<hr>` — iframe srcdoc with `sandbox="allow-scripts"`; standalone `/preview` retired as a 308 redirect to `/previews#reviewer-surface`.)
- [x] `sessions_list.html` — `/operator/sessions` (Segment 11D PR A: `body.ui-v2`; per-row Access → Secondary. PR B (D4): "Create new session" promoted to a Primary affordance flush right of the H1 in `.sessions-list-header`, with `.btn-cta` promotion inside the empty-state card. **Cards-vs-table revisit (post-11D, 2026-05-04):** the table layout returns — six labelled columns (Session Name link / Session Code / Deadline pill / Created by / Created / Last Modified) plus an unlabelled trailing column carrying an unwired select-row checkbox. The redundant Access button and the per-row Delete anchor are both gone — the Session Name link is the row's affordance, and bulk-select wiring will live on the checkbox once it ships. The `.card.session-card` per-row layout from D4 is retired.)
- [x] `session_new.html` — `/operator/sessions/new` (Segment 11D PR A: `body.ui-v2`; form wrapped in `.card`; v2 form treatment via base defaults; Cancel → Secondary)
- [x] `session_detail.html` — `/operator/sessions/{id}` (Session Setup card retired; its five Manage links live in the chrome top-nav now. Segment 11B rebuilt the body: Next Action card replaces the old Run Session + Validation summary stack; Quick Setup and Extract Data render as placeholder cards via the canonical `placeholder_card` macro; Danger Zone Delete-Session is visible-but-disabled in `ready`; lifecycle prose / status pills route through the `lifecycle_label` Jinja filter.)
- [x] `session_edit.html` — `/operator/sessions/{id}/edit` (Segment 11D PR B1: gains the two-row session chrome with no tab active per `spec/operator_ui_concept.md` "Sub-pages of Home"; status row partial wired in; route now passes `status_pills`. Form lives inside a single `.card`; Save → Primary, Cancel → Secondary.)
- [x] `instruments_index.html` — `/operator/sessions/{id}/instruments`
- [x] `session_invitations.html` — `/operator/sessions/{id}/invitations`
- [x] `session_invitations_reviewer_detail.html` — `/operator/sessions/{id}/invitations/{inv_id}/detail` (per-reviewer drill-in card, Segment 11C Part 1)
- [x] `session_outbox.html` — `/operator/sessions/{id}/outbox` (dev-diagnostic; not a chrome tab post-Segment 11C Part 1)
- [x] `session_validate.html` — `/operator/sessions/{id}/validate` (Operations-row tab; replaces Outbox in the chrome)
- [x] `session_responses.html` — `/operator/sessions/{id}/responses` (Segment 11C Part 1: new reviewee-centric coverage view replacing the retired Monitoring page; `monitoring.AT_RISK_THRESHOLDS` classifies each reviewee)
- [x] `session_responses_reviewee_detail.html` — `/operator/sessions/{id}/responses/{reviewee_id}/detail` (Segment 11C Part 1 drill-in)
- [x] `session_relationships.html` — `/operator/sessions/{id}/relationships` (Segment 15D PR 2: per-pair attributes Setup page, mirrors Reviewers / Reviewees; single-line stats card + Tag1/2/3 visibility toggles in the preview table)
- [x] `session_rule_builder.html` — `/operator/sessions/{id}/assignments/rule-based-editor` (Segment 13A-1: Rule Builder page; Personal-library forks + seeded RuleSets; full predicate / quota grammar editor)

### Operator partials

- [x] `operator/partials/session_setup_status_row.html` — emits
  lifecycle badge via `.pill-lifecycle-{status}` so each state
  picks up its own treatment (DRAFT → yellow, etc.). Post-15D
  the **Assignments:** slot retired from the strip (count + mode
  now live on the Operations Assignments page itself).
- [x] `operator/partials/_quick_setup_card.html` — Quick Setup
  card on Session Home + Create New Session (Segment 11H scaffold
  + Segment 11J wiring; two-column layout post-Post-Segment 15
  cleanup; four wired slots: Reviewers + Reviewees + Relationships
  + Session settings).
- [x] `operator/partials/_extract_data_card.html` — Extract Data
  card on Session Home (Segment 11H scaffold + 12A-1 / 12A-3 PRs
  flipped each row live; five wired tiles + inert Zip-all bundle).
- [ ] `operator/partials/validation_results.html` — currently
  renders an inner `.card` with the issues list; needs review for
  banner-family rendering when the issues are validation errors.

### Reviewer pages

- [x] `reviewer/dashboard.html` — `/reviewer` (Segment 11D PR C: `body.ui-v2 reviewer`; lighter chrome via the new `reviewer/_top_bar.html` partial; per-row submitted-state pill swapped from `pill-info` to `pill-success`; empty-state copy "You have no pending reviews".)
- [x] `reviewer/review_surface.html` — `/reviewer/sessions/{id}/{instrument_position}` (Segment 11D PR C: `body.ui-v2 reviewer` (preview reuses operator chrome via the `top_bar` `super()` branch); D5 status icons via `.status-icon-{complete,incomplete}`; D6 banners migrated to the `.banner.banner-{info,success,warning}` family; D7 page header carries H1 + deadline in `.muted`; Save → Primary, Submit → Secondary, Clear all moved into a `.card.danger-zone` with a `.btn.destructive` action. **Multi-instrument rewrite (Segment 11D follow-on, 2026-05-05, PRs #428 → #448):** URL pattern includes the 1-indexed `{instrument_position}`; bare URL 303s to `/1`. Top-row `.bottom-grid` (description card + always-on `.rs-status-panel` with per-page `.pill.pill-{empty|warning|success}` per `PageStatus`). Unified `.rs-action-row` (Save / Discard / `Page #N: short_label` / `.rs-action-divider` / Submit, mirrored top + bottom). Server renders every instrument group; CSS hides non-active ones via `.rs-paginated > .rs-instrument-group:not(.rs-active)`; JS toggles `.rs-active` + `pushState` on Page-N click; per-group dirty tracking gates Save's enabled state; Discard restores from `data-rs-saved-value`. Missing-required moved to its own full-width 2-column `.rs-missing-card` below the bottom-grid; Submit is now a hard gate (acknowledge-and-submit-anyway retired). Save / Submit flash banners retired. Numeric inputs render as `<input type="number">` with `min`/`max` + `step="any"` (spinners hidden via `base.html` CSS) + hover `title` constraint hint + JS `setCustomValidity` for step-grid violations (`1e-6` tolerance) + server-side `validate_value` backstop. A right-aligned constraint-summary row above each instrument table reads `**Rating** (1-5, steps of 1), …` (List rows omitted).)
- [x] `reviewer/invite_mismatch.html` (Segment 11D PR C: `body.ui-v2 reviewer`; the email-mismatch error renders as a `.banner.banner-warning`; legacy inline red `.card` styles retired.)

### Other

- [x] `about.html` — `/about` (Segment 11D PR A: `body.ui-v2`; body content sits in a `.card`; gains the return-to-origin "← Back to {context}" link via `app/web/return_to.py`)
- [x] `me_debug.html` — `/me/debug` (Segment 11D PR A: now extends `base.html` on `body.ui-v2`; inline styles retired, claim list uses v2 table treatment, Sign-out → Secondary, return-to-origin link at top)

### What "v2-covered" means

A page is ticked when it has been brought onto `body.ui-v2`,
including:

1. **Body class.** Sets `{% block body_class %}ui-v2{% endblock %}`
   so the v2-scoped CSS in `base.html` applies.
2. **Cards.** Lock cards use `.card.lock`; danger zones use
   `.card.danger-zone`; no inline `style="border-color: #…;
   background: #…"` overrides on cards.
3. **Buttons.** Each button uses the role per `spec/visual_style_general.md`
   §Buttons: Primary reserved for the page's *single* main
   affirmative action; routine submits are Secondary; destructive
   confirms are Destructive (outline red); recovery actions inside
   lock cards are `.btn.alert` (outline brown). No inline
   `style="background: …"` button overrides.
4. **Pills.** Counts use `.pill-count` (or the aliased
   `.pill-info`); empty/missing use `.pill-empty` (or
   `.pill-warning`); lifecycle states use `.pill-lifecycle-{state}`.
   Confirm labels pillify count phrases inline.
5. **Forms.** Helper text uses `.form-help`; redundant labels
   above file inputs retired (with `aria-label` preserved on the
   input).
6. **Banners.** Inline-styled `.card` banners migrated to
   `.banner.banner-{info|success|warning|error}` (where
   present).
7. **Layout.** Pairs that don't carry equal weight use
   `.bottom-grid` (natural heights), not `.page-grid`.
8. **Tests.** Any pinned-to-old-markup assertions updated;
   `pytest` green.

---

## v1 restructure (complete)

Historical record. Every page below was carried through the
original UI pass that introduced `.page-grid` / `.bottom-grid`
and the six `.btn` modifiers from `spec/domain_assumptions.md`. This
section is preserved as a baseline; the v2 sweep above is the
active work.

### Cross-cutting

- [x] `base.html` — typography knob, button modifier classes
  (`.btn`, `.btn.secondary`, `.btn.alert`, `.btn.alert-solid`,
  `.btn.danger`, `.btn.danger-solid`), `.page-grid` /
  `.bottom-grid` layout primitives, `.btn-cta`, `.btn-row`,
  `.btn-pair`, `.setup-grid`, `.col-shrink`, `.page-subtitle`
  styles.

### Operator pages

- [x] `sessions_list.html`
- [x] `session_new.html`
- [x] `session_detail.html`
- [x] `session_edit.html`
- [x] `session_reviewers.html`
- [x] `session_reviewees.html`
- [x] `session_assignments.html` (every assignment-method form
  inlined on the hub; the previous standalone
  `session_assignments_manual.html` /
  `session_assignments_full_matrix_setup.html` GETs and the
  earlier `assignments_preview_*.html` confirm pages were all
  removed; the POST endpoints
  `/assignments/manual/import` and `/assignments/full-matrix`
  remain but redirect back to the hub).
- [ ] `instruments_index.html`
- [x] `session_setupinvite.html` (Segment 11E rebuilt the page as
  the operator-editable email template editor; the v1 restructure
  is moot.)
- [ ] `session_invitations.html`
- [ ] `session_outbox.html`
- [ ] `session_validate.html`

(The v1 row for `session_monitoring.html` retired alongside
the template itself in Segment 11C Part 1 — `/monitoring` now
303-redirects to `/invitations`.)

### Reviewer pages

- [ ] `reviewer/dashboard.html`
- [ ] `reviewer/review_surface.html`
- [ ] `reviewer/invite_mismatch.html`

### Other

- [ ] `about.html`
- [ ] `me_debug.html`

### What "v1-covered" means

1. **Layout.** Uses `.page-grid` / `.bottom-grid` if content
   naturally splits into two parallel groupings; otherwise stays
   single-column on purpose.
2. **Buttons.** Every button uses one of the six canonical
   `.btn` modifiers from `spec/domain_assumptions.md` — no inline
   `style="background: …; border-color: …"` overrides.
3. **Copy.** Heading + instruction copy reviewed; capitalisation
   matches surrounding pages.
4. **Tests.** Any pinned-to-old-markup assertions in `tests/`
   updated; `pytest` green.

Pages with only minor copy edits (e.g. a heading rename) but no
layout / button-class pass are left unchecked.

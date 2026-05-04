# UI restructure checklist

Tracks UI restyling progress across two passes:

- **v1 restructure (complete)** — the original two-column layout
  + six canonical `.btn` modifiers from `spec/assumptions.md`
  pass.
- **v2 sweep onto `body.ui-v2`** — the current pass, applying
  the canonical primitives in `spec/ui_elements.md` (P6 hover
  by fill, P7 recovery-action-color-family, refined card /
  button / pill / chrome treatments). Reference implementation
  is `session_reviewers.html` + the `body.ui-v2`-scoped block
  in `base.html`.

Tick items as each page is reviewed. A page can be on v1 (legacy
look) or v2 (canonical primitives) — the two sections track them
separately.

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
- [x] `session_setupinvite.html` — `/operator/sessions/{id}/setupinvite` (placeholder)
- [x] `session_previews.html` — `/operator/sessions/{id}/previews` (new placeholder; Operations row)
- [x] `sessions_list.html` — `/operator/sessions` (Segment 11D PR A: `body.ui-v2`; per-row Access → Secondary. PR B (D4): table replaced with a flex column of `.card.session-card` rows carrying name + lifecycle pill + meta line; Primary "Create new session" sits in the header row when populated and promotes to a `.btn-cta` inside the empty-state card.)
- [x] `session_new.html` — `/operator/sessions/new` (Segment 11D PR A: `body.ui-v2`; form wrapped in `.card`; v2 form treatment via base defaults; Cancel → Secondary)
- [x] `session_detail.html` — `/operator/sessions/{id}` (Session Setup card retired; its five Manage links live in the chrome top-nav now. Segment 11B rebuilt the body: Next Action card replaces the old Run Session + Validation summary stack; Quick Setup and Extract Data render as placeholder cards via the canonical `placeholder_card` macro; Danger Zone Delete-Session is visible-but-disabled in `ready`; lifecycle prose / status pills route through the `lifecycle_label` Jinja filter.)
- [x] `session_edit.html` — `/operator/sessions/{id}/edit` (Segment 11D PR B1: gains the two-row session chrome with no tab active per `spec/operator_ui_concept.md` "Sub-pages of Home"; status row partial wired in; route now passes `status_pills`. Form lives inside a single `.card`; Save → Primary, Cancel → Secondary.)
- [x] `instruments_index.html` — `/operator/sessions/{id}/instruments`
- [x] `session_invitations.html` — `/operator/sessions/{id}/invitations`
- [x] `session_outbox.html` — `/operator/sessions/{id}/outbox`
- [x] `session_monitoring.html` — `/operator/sessions/{id}/monitoring`
- [x] `session_validate.html` — `/operator/sessions/{id}/validate` (now a chrome tab on the Operations row, replacing Outbox)

### Operator partials

- [x] `operator/partials/session_setup_status_row.html` — emits
  lifecycle badge via `.pill-lifecycle-{status}` so each state
  picks up its own treatment (DRAFT → yellow, etc.).
- [ ] `operator/partials/validation_results.html` — currently
  renders an inner `.card` with the issues list; needs review for
  banner-family rendering when the issues are validation errors.

### Reviewer pages

- [x] `reviewer/dashboard.html` — `/reviewer` (Segment 11D PR C: `body.ui-v2 reviewer`; lighter chrome via the new `reviewer/_top_bar.html` partial; per-row submitted-state pill swapped from `pill-info` to `pill-success`; empty-state copy "You have no pending reviews".)
- [x] `reviewer/review_surface.html` — `/reviewer/sessions/{id}` (Segment 11D PR C: `body.ui-v2 reviewer` (preview reuses operator chrome via the `top_bar` `super()` branch); D5 status icons via `.status-icon-{complete,incomplete}`; D6 banners migrated to the `.banner.banner-{info,success,warning}` family; D7 page header carries H1 + deadline in `.muted`; Save → Primary, Submit → Secondary, Clear all moved into a `.card.danger-zone` with a `.btn.destructive` action.)
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
and the six `.btn` modifiers from `spec/assumptions.md`. This
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
- [ ] `session_setupinvite.html` (heading renamed to **Email
  Invites** only; no v1 layout pass)
- [ ] `session_invitations.html`
- [ ] `session_outbox.html`
- [ ] `session_monitoring.html`
- [ ] `session_validate.html`

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
   `.btn` modifiers from `spec/assumptions.md` — no inline
   `style="background: …; border-color: …"` overrides.
3. **Copy.** Heading + instruction copy reviewed; capitalisation
   matches surrounding pages.
4. **Tests.** Any pinned-to-old-markup assertions in `tests/`
   updated; `pytest` green.

Pages with only minor copy edits (e.g. a heading rename) but no
layout / button-class pass are left unchecked.

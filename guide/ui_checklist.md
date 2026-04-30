# UI restructure checklist

Tracks which page templates have been brought through the recent UI
restructure (two-column layout where applicable, canonical button
classes from `assumptions.md`, refreshed copy, etc.). Tick items as
each page is reviewed.

## Cross-cutting

- [x] `base.html` — typography knob, button modifier classes
  (`.btn`, `.btn.secondary`, `.btn.alert`, `.btn.alert-solid`,
  `.btn.danger`, `.btn.danger-solid`), `.page-grid` /
  `.bottom-grid` layout primitives, `.btn-cta`, `.btn-row`,
  `.btn-pair`, `.setup-grid`, `.col-shrink`, `.page-subtitle`
  styles.

## Operator pages

- [x] `sessions_list.html` — `/operator/sessions`
- [x] `session_new.html` — `/operator/sessions/new`
- [x] `session_detail.html` — `/operator/sessions/{id}`
- [x] `session_edit.html` — `/operator/sessions/{id}/edit`
- [x] `session_reviewers.html` — `/operator/sessions/{id}/reviewers`
- [x] `session_reviewees.html` — `/operator/sessions/{id}/reviewees`
- [ ] `session_assignments.html` — `/operator/sessions/{id}/assignments`
- [ ] `assignments_preview_full_matrix.html`
- [ ] `assignments_preview_manual.html`
- [ ] `instruments_index.html` — `/operator/sessions/{id}/instruments`
- [ ] `session_setupinvite.html` — `/operator/sessions/{id}/setupinvite` (heading renamed to **Email Invites** only; no layout pass yet)
- [ ] `session_invitations.html` — `/operator/sessions/{id}/invitations`
- [ ] `session_outbox.html` — `/operator/sessions/{id}/outbox`
- [ ] `session_monitoring.html` — `/operator/sessions/{id}/monitoring`
- [ ] `session_validate.html` — `/operator/sessions/{id}/validate`

## Operator partials

- [ ] `operator/partials/validation_results.html` — used inside the
  upload-CSV cards on reviewers/reviewees; renders an inner
  `.card` with issues list.

## Reviewer pages

- [ ] `reviewer/dashboard.html` — `/reviewer`
- [ ] `reviewer/review_surface.html` — `/reviewer/sessions/{id}`
- [ ] `reviewer/invite_mismatch.html`

## Other

- [ ] `about.html` — `/about`
- [ ] `me_debug.html` — `/me/debug`

## What "covered" means

A page is ticked when it has been intentionally restructured /
restyled in this round, including:

1. **Layout.** Uses `.page-grid` / `.bottom-grid` if its content
   naturally splits into two parallel groupings; otherwise stays
   single-column on purpose.
2. **Buttons.** Every button uses one of the six canonical
   `.btn` modifiers from `assumptions.md` — no inline
   `style="background: …; border-color: …"` overrides.
3. **Copy.** Heading + instruction copy reviewed; capitalisation
   matches the surrounding pages.
4. **Tests.** Any pinned-to-old-markup assertions in `tests/`
   updated; `pytest` green.

Pages with only minor copy edits (e.g. a heading rename) but no
layout / button-class pass are left unchecked.

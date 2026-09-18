# Reviewer Experience Preview hub — retired

The Operations-row **Previews** hub retired in Segment 19Q Item 1. Its two
jobs now live on the Invitations per-reviewer drill-in:

- **Open reviewer surface** opens
  `/operator/sessions/{id}/preview-surface/1` for that reviewer in a
  new tab — page 1 always, hardcoded in the drill-in's button; the
  route takes a `{page_n}` and the surface's own pager moves it. The route renders the production reviewer template in inert
  operator-preview mode; `spec/reviewer-surface.md` owns that contract.
- **Email previews** renders the Invitation, Reminder and Responses received
  tabs for the drill-in's named reviewer. `spec/operations_pages.md` owns the
  placement and `spec/email_template_editor.md` owns their template source.

`GET /operator/sessions/{id}/previews` is retained only as a permanent 308
redirect to `/operator/sessions/{id}/invitations`. The picker, its Random
action, `session_previews.html`, and `_preview_picker.html` have no successor.
`POST /operator/sessions/{id}/previews/random` is not a bookmark and is gone.

The accepted consequence is that previews no longer have a door before
Prepare, for inactive reviewers, or for reviewers with no included
assignments. The Invitations table is the only picker. The historical hub
design remains in `guide/archive/segment_11F_previews_page.md`; the retirement
decision is `guide/segment_19Q_workflow_and_previews.md` Item 1.

# Deferred until pilot feedback

A common ledger of features that were scoped, designed, and
explicitly deferred — not because they're out of scope forever,
but because **building them speculatively would cost more than
discovering they're unwanted**. Each item carries enough
context that it can be re-activated quickly if pilot feedback
asks for it.

The pattern: small, well-scoped post-MVP slices peeled off
named segments after the MVP shipped, rather than carried as
hard-tail items inside otherwise-archived plans. Living here
keeps the archive clean (one segment plan = one segment) and
makes the deferred set scannable in one place.

When pilot feedback **does** request one of these, lift the
section into a fresh segment plan (or fold it into a related
in-flight segment) and remove the bullet from this doc.

---

## 16C PR 4 — Audit log: entity drill-in (~200 LOC)

> Carved from `guide/archive/segment_16C_richer_audit_views.md`
> 2026-05-11 once 16C PRs 1-3 shipped and the segment retired
> to archive. Plan text below is the original 16C PR 4 spec
> verbatim plus a small "what changed since" note covering
> the 16B / 16C ride-alongs that the renderer now needs to
> handle.

**Ships.**

- The envelope's `refs` slot already carries cross-entity
  int PKs (e.g. `refs.reviewer_id`, `refs.instrument_id`,
  `refs.target_user_id` from 16B PR 2). Per-row anchors
  render alongside the detail rendering — "View reviewer"
  / "View instrument" / "View RuleSet" / "View user"
  deep-linking into the relevant operator-page surface.
- Deleted entities render as a disabled `(deleted)` suffix
  rather than a broken link. The viewer checks for row
  existence via cheap `EXISTS` queries batched per
  page-load.
- Per-entity URL builder
  `views.audit_ref_url(ref_key, ref_id, session) -> str`
  centralises the routing so anchors stay consistent with
  the operator chrome.

**Why deferred.** PRs 1-3's per-row expander already shows
`refs.target_user_id: 42` plain-text. Whether operators want
clickable deep-links vs. just reading the int PK is exactly
the kind of "small UX accelerant" that pilot feedback
surfaces (or doesn't) — building it preemptively risks
matching the wrong navigation pattern.

**Lift trigger.** Operator says "I keep wanting to click on
those IDs to jump to the entity" or analogous.

**Wire-up.** Lives in `app/web/views/_audit_log.py`'s
detail-renderer pipeline. The `format_audit_detail` view
adapter that PR 3 ships already gives the per-section
markup the right hook point — extend `_render_kv` (or split
out a `_render_refs`) to consult `audit_ref_url` and emit
anchors instead of plain `<code>` for known ref keys.

---

## 16C PR 5 — Cross-session workspace audit search (~250 LOC)

> Carved from `guide/archive/segment_16C_richer_audit_views.md`
> 2026-05-11 once 16C PRs 1-3 shipped and the segment retired
> to archive.

**Ships.**

- New workspace-level route `/operator/sys-admin/audit-log`
  (no session id). Same chrome, same table, same filter
  strip — but scoped to every session the sys-admin can
  see, plus workspace-scoped events
  (`workspace.operator_admitted` / `.operator_revoked` /
  `sys_admin.role_promoted` / `.role_demoted` from 16A
  PR 6) which have no `session_id`.
- Sys Admin top nav grows a third tab ("Audit log")
  alongside Sessions Diagnostics + Accounts Management.
- Filter strip gains a session-code dropdown / typeahead.
- Default date range "last 7 days" to keep the query
  bounded; operators can widen explicitly.
- Performance guard: query times measured on a fixture
  with N=10000 events per session × 50 sessions; if it
  bites, add an `(session_id, created_at)` composite index.

**Why deferred.** Per-session viewer (PR 1) is the natural
entry point for "what happened on this session?" — the
question that drove 16C in the first place. Cross-session
search is a different question ("who admitted whom across
all sessions?" / "what did this operator touch this week?")
and the cost is real (new top-nav tab, new query shape,
performance guard). Wait for the question to surface before
building the answer.

**Lift trigger.** Sys-admin says "I need to see what happened
across all sessions in date X" or "I want to audit one
operator's actions wherever they touched the workspace."

**Wire-up.** Reuses the PR 1 reader (with a small
generalisation to drop the `session_id` predicate) plus the
PR 2 filter strip. The new route lives in
`app/web/routes_operator/_sys_admin.py`; the new top-nav
tab lands in `sys_admin_top_nav.html`.

---

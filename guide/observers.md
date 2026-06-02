# Observers — participant role + collation surface

Standing notes for the **observer** participant role: who they
are, the data model, the surfaces, and the wiring tail that's
still to ship.

## Status

**Paused 2026-06-01.** Operator-side observer plumbing is live
(roster Setup page, Quick Setup slot, Extract Setup row, bundle
inclusion, per-session enable toggle, friendly-label resolver,
visibility-policy column) but the participant-facing collation
surface (`/me/sessions/{id}/collation`) renders only the
placeholder chrome — no body.

**Use-scenario framing (2026-06-02).** The paused work resumes
once the two distinct observer scenarios are designed
separately rather than collapsed into one collation surface:

### Scenario A — Universal observers (see everyone)

An observer who needs visibility over the *entire* session's
responses (e.g. a department head reviewing an evaluation
cycle, an auditor, a programme administrator).

For this group, **a participant-facing surface is mostly
redundant**. The operator already has the Extract data tab
with per-instrument lens cards, the Data shaper, the Zip-all
bundles. The cleanest path:

- **Operator sends the relevant CSVs directly** to the
  observer out-of-band (email, file share). No new surface
  needed.
- If a surface is wanted, it should be **download-only** —
  no in-page table, no interactive filters. A one-page list
  of links that mirror what the operator would have attached
  in an email.
- **Optional refinement:** a summary-only surface (rolled-up
  per-instrument aggregates across the whole session) for
  observers who want a dashboard rather than raw data. The
  W16 summarized-mode aggregate primitives in
  `_reviewee_results.py::_summarize_field` carry over
  directly.

Implication: most of the W17 design we'd sketched (cross-
reviewee table, per-cell visibility policy resolution, layout
that flips the W16 axis) doesn't actually serve this group.

### Scenario B — Partitioned observers (see a subset)

An observer tagged to a specific partition of the session who
needs visibility only over *their* partition. Example: tutors
of students from different tutorial groups, each tutor sees
only their tutees. Mentors / coaches / programme coordinators
each scoped to a cohort.

This is the group that genuinely needs **observer status as a
distinct participant role**. It needs:

- **A partition-assignment affordance** — akin to the
  rule-based assignment that ties reviewers to reviewees, but
  far simpler. Probably a single-axis tag match between the
  observer's `tag_1` (already on the model) and the
  reviewee's `tag_1` / `tag_2` / `tag_3`. The operator picks
  which reviewee-tag axis the observer-tag matches on; the
  service materialises the per-observer reviewee scope.
- **A participant-facing surface** — a per-observer view of
  the reviewees in their partition + the responses about
  them, gated through the per-instrument visibility policy.

The W17 cross-reviewee body sketch (with the `tag_1`-match
filter) is the right shape for this scenario; the open
questions become:

- **Match-axis explicitness.** Observer-tag → reviewee-tag-N
  needs an explicit per-session config rather than a hardcoded
  `observer.tag_1 == reviewee.tag_1`. A small operator-side
  control (a dropdown? a setting on the observers toggle?)
  picks the axis.
- **Match-many semantics.** What if an observer's `tag_1`
  matches multiple reviewees across different tag values? A
  comma-separated match list on the observer-side?
- **Default render mode.** Same question as before — when
  the operator hasn't authored a per-instrument policy for
  the observer audience on a given instrument, what's the
  cell render? (Likely: Summarized by default, with the
  operator able to opt in to per-cell Raw / Anonymized.)

## Re-design path

When the body wiring resumes, the natural cut is:

1. **Decide if Scenario A needs a surface at all.** If yes,
   spec what shape (download-only vs. summary-only vs. both).
   If no, retire the operator-side toggle + roster for
   Scenario A users; the operator just exports + emails.
2. **Design the partition-assignment affordance** for
   Scenario B. The "akin to but simpler than reviewer-rules"
   shape suggests a per-session operator setting +
   materialisation service + UI surface for the operator to
   inspect coverage.
3. **Then** wire the `/collation` body for Scenario B per the
   sketched layout (rows = reviewees in the observer's
   partition, columns = aggregate of responses about that
   reviewee, cells resolved through the visibility policy).

When that work scopes, fold this file into a
`segment_22_observers.md` plan and link from
`guide/todo_master.md`'s Upcoming list.

## Where the wiring stands

What's shipped (live in production):

- **Schema** — `observers` table, `observer.*` audit events,
  `sessions.observers_enabled` toggle.
- **Roster** — Setup-Observers page (CRUD + bulk + delete-all
  + Upload + Operator-actions row + Danger Zone) shipped
  W10 / PR #1706.
- **Quick Setup Observers slot** — Session Home + new-session
  form both upload a CSV with the same shape as the Setup
  page (W12 / PR #1754). Renders only when
  `observers_enabled` is on.
- **Extract Setup Observers row + bundle** — per-row CSV
  download (`observers.csv`) + inclusion in the Zip-all
  bundle, gated on the same toggle (W13 / PR #1755).
- **Per-instrument visibility policy** — operators can
  author Raw / Anonymized / Summarized for the `observer`
  audience on each instrument's Band 3 visibility editor
  (W15 + the per-window mode pair columns from S14).
- **`/me/sessions/{id}/collation` placeholder route** — page
  renders the reviewer-surface chrome with the caption
  "Observer view of the session"; gated on
  `require_observer_in_session` (W3 / P6, PR #1713). No
  body content yet.
- **Cross-role lobby support** — observers appear on
  `/me/` with the amber `observer` role pill if they're on
  any session's roster (W18, polish through #1715). Their
  role-navigator chip strip links to `/me/sessions/{id}/collation`.

## Paused work items (folded into the re-design above)

- **W17 — Observer collation surface body.** Reshape per the
  Scenario A / B split above before resuming. The
  cross-reviewee table sketched in the archived
  `guide/archive/participant_model_upgrade.md` §7 is the
  right shape for Scenario B; Scenario A may not need a
  surface at all.
- **W5 — `app/services/collation.py` service.** Still
  bundled with W17. Shape stays
  `build_observer_collation_context(db, *, review_session,
  observer) -> ObserverCollationContext`, paralleling W16's
  `build_reviewee_results_context`. The W7 resolver + the
  per-data-type aggregation helpers from W16's
  `_summarize_field` are the reusable primitives.

## Cross-references

- `guide/archive/participant_model_upgrade.md` — design rationale +
  the full audience taxonomy (§3.1 observer scope, §7
  collation render shape).
- `guide/archive/participant_model_remainder.md` — outstanding
  participant-model items overall; observer-side items
  filed here once this stub took ownership.
- `spec/audience_and_identity_model.md` — authoritative
  audience taxonomy.
- `spec/setup_pages.md` — Observers Setup page contract.
- `app/services/visibility_policies.py::resolve_mode` —
  the resolver W17 calls.
- `app/web/views/_reviewee_results.py::_summarize_field` —
  the per-data-type aggregation primitives W5 will reuse.

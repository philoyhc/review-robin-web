# guide/

**Forward-looking planning and todos.**

Answers the question: *what are we building next, and how?*
Segment-by-segment workplans, cross-cutting checklists, and
ad-hoc todo lists live here. Once a segment ships and its plan
becomes a historical record, move it into `guide/archive/` —
and add a row for it to `guide/archive/README.md` in the same
change (that index is maintained by hand).

| Path | Covers |
|---|---|
| `segment_*.md` | Plans for the current and upcoming segments. |
| `codebase_assessment_*.md` | Codebase-vs-functional-spec snapshots. Only the latest snapshot lives here; older snapshots retire to `archive/` once a newer one supersedes them. |
| `consistency_audit.md` | Point-in-time audit of "same functionality, divergent call paths" — service/route/template/view drift hazards, severity-ranked with `path:line` refs and a remediation order. Dated snapshot; supersede or archive once the drift is resolved. |
| `todo_master.md` | Prioritized sequence — Done / Upcoming roadmap. Read this first when picking up between segments. (Tracks open items directly post-2026-05-10; the earlier `unfinished_business.md` catalog retired to `archive/` once its items shipped or got absorbed into named segments.) |
| `deferred_consolidated.md` | The single ledger of all scoped-but-not-scheduled work, ordered by disposition. **Part A** — features paused but expected pending pilot feedback (ships + why deferred + lift trigger + wire-up per entry). **Part B** — infrastructure / platform hardening deferred until production pressure (Postgres-native types, VNet, Key Vault, etc.). **Part C** — future possibilities deliberately off-roadmap. Consolidated 2026-08-19 from the former `deferred_until_pilot_feedback.md` / `deferred_infra.md` / `future_possibilities.md` (now in `archive/`). Distinct from `todo_master.md` (committed sequence). |
| `archive/` | Shipped segment plans (kept for historical reference; not the source of truth for current behavior — see `docs/status.md` for that). The early `low_intensity_workplan_review_robin_web.md`, `major_refactor.md`, and `rules_table.md` are archived here too — superseded by the segment plans + `todo_master.md` and (for `rules_table.md`) the seed table in `spec/assignments.md` (which absorbed the pre-2026-05-26 `rule_based_assignment.md`, now under `spec/archive/`). `archive/README.md` is a hand-maintained index of every file in the folder — keep it in sync when you archive something. |

Sibling folders:

- **`spec/`** — surface specifications and design intent (what
  the UI should look like).
- **`docs/`** — reference material about the running system (how
  things actually work today).

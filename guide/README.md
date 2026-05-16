# guide/

**Forward-looking planning and todos.**

Answers the question: *what are we building next, and how?*
Segment-by-segment workplans, cross-cutting checklists, and
ad-hoc todo lists live here. Once a segment ships and its plan
becomes a historical record, move it into `guide/archive/`.

| Path | Covers |
|---|---|
| `segment_*.md` | Plans for the current and upcoming segments. |
| `todo_master.md` | Prioritized sequence — Done / Upcoming roadmap. Read this first when picking up between segments. (Tracks open items directly post-2026-05-10; the earlier `unfinished_business.md` catalog retired to `archive/` once its items shipped or got absorbed into named segments.) |
| `future_possibilities.md` | Aspirational directions deliberately *not* on the roadmap — recorded so the design doesn't foreclose them, but not planned to ship. Distinct from `todo_master.md` (committed) and `deferred_until_pilot_feedback.md` (paused but expected). |
| `ui_checklist.md` | Cross-cutting UI primitives + per-page restructure checklist. |
| `archive/` | Shipped segment plans (kept for historical reference; not the source of truth for current behavior — see `docs/status.md` for that). The early `low_intensity_workplan_review_robin_web.md`, `major_refactor.md`, and `rules_table.md` are archived here too — superseded by the segment plans + `todo_master.md` and (for `rules_table.md`) the seed table in `spec/rule_based_assignment.md` §5.4. |

Sibling folders:

- **`spec/`** — surface specifications and design intent (what
  the UI should look like).
- **`docs/`** — reference material about the running system (how
  things actually work today).

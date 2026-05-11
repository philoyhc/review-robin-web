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
| `ui_checklist.md` | Cross-cutting UI primitives + per-page restructure checklist. |
| `all_buttons.md` | Operator-surface button audit — every button (and button-styled anchor) across the operator templates, organised by page and card with continuous numbering and per-button canonical-style labels (per `spec/ui_elements.md` §6). |
| `archive/` | Shipped segment plans (kept for historical reference; not the source of truth for current behavior — see `docs/status.md` for that). The early `low_intensity_workplan_review_robin_web.md` is archived here too — superseded by the segment plans + `todo_master.md`. |

Sibling folders:

- **`spec/`** — surface specifications and design intent (what
  the UI should look like).
- **`docs/`** — reference material about the running system (how
  things actually work today).

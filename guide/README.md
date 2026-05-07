# guide/

**Forward-looking planning and todos.**

Answers the question: *what are we building next, and how?*
Segment-by-segment workplans, cross-cutting checklists, and
ad-hoc todo lists live here. Once a segment ships and its plan
becomes a historical record, move it into `guide/archive/`.

| Path | Covers |
|---|---|
| `segment_*.md` | Plans for the current and upcoming segments. |
| `todo_master.md` | Prioritized sequence — the recommended order for working through the catalog (P0 → P3). Read this first when picking up between segments. |
| `unfinished_business.md` | The catalog itself — every open item with Why / Where / Plan, sized as small PR slices. `todo_master.md` points back at items in here. |
| `ui_checklist.md` | Cross-cutting UI primitives + per-page restructure checklist. |
| `archive/` | Shipped segment plans (kept for historical reference; not the source of truth for current behavior — see `docs/status.md` for that). The early `low_intensity_workplan_review_robin_web.md` is archived here too — superseded by the segment plans + `todo_master.md`. |

Sibling folders:

- **`spec/`** — surface specifications and design intent (what
  the UI should look like).
- **`docs/`** — reference material about the running system (how
  things actually work today).

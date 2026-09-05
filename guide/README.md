# guide/

**Forward-looking planning and todos.**

Answers the question: *what are we building next, and how?*
Segment-by-segment workplans, cross-cutting checklists, and
ad-hoc todo lists live here. Once a segment ships and its plan
becomes a historical record, move it into `guide/archive/` —
and add a row for it to `guide/archive/README.md` in the same
change (that index is maintained by hand).

**Before archiving a plan, run `python3 tools/close_check.py <id>`**
(`19A` for a segment, `19A.3` for one item) **and get exit 0.** It
verifies that the spec edits the plan committed to in its `Doc impact`
section actually happened — the "spec on the way out" half of the phase
rule, which nothing checked before 2026-09-05. It reports; you act. It
cannot tell you whether an edit was *right*, so run `spec-writer` over
the same files afterwards.

| Path | Covers |
|---|---|
| `segment_*.md` | Plans for the current and upcoming segments. |
| `segment_plan_template.md` | Blank segment / item plan with every section prompted — Opportunity → Decision → Semantics → Judgment calls → Blast radius (measured) → PR ladder → Definition of done → Open questions → Out of scope → Doc impact (+ a Status block added when intended and done diverge). Two headings are machine-read by `tools/close_check.py` (`## Doc impact`, `## Status`); do not rename them. `Doc impact` is matched exactly, so suffixing it retires a manifest without deleting it; `Status` tolerates a suffix. The operational guide for using it is the `segment-plan` skill (`.claude/skills/segment-plan/SKILL.md`). |
| `codebase_assessment_*.md` | Codebase-vs-functional-spec snapshots. Only the latest snapshot lives here; older snapshots retire to `archive/` once a newer one supersedes them. **Standard quantitative items:** LOC + biggest files (as before), plus duplication and churn from `python3 tools/code_metrics.py` — added 2026-09-04 after `docs/practice-audit-2026-09-04.md` Appendix A found both unmeasured. Quote the churn figure with its baseline ratio, never alone. **Record them every time; act on them only past a threshold** — duplication at >=10-line blocks rising materially between assessments (the 2026-09-04 baseline is 6.5% for `app/`), or a churn ratio meaningfully above ~1.5x (baseline 1.0x, i.e. deletions are age-blind). The churn figure is deterministic — the tool walks the full merge history, ~76s; `--churn-sample` output is sample-dependent at any size and is not comparable between snapshots. Below those, the numbers are a trend line, not a task: 6.5% duplication is fine, and "improving" it is how a recurring metric turns into make-work. These are reading prompts for a human in a document that is already judgement-based — deliberately not a CI gate, which is the form that gets argued with, raised, then disabled. |
| `todo_master.md` | Prioritized sequence — Done / Upcoming roadmap. Read this first when picking up between segments. (Tracks open items directly post-2026-05-10; the earlier `unfinished_business.md` catalog retired to `archive/` once its items shipped or got absorbed into named segments.) |
| `theme_customizer.md` | Plan for a **theme customizer**, two composable plans sharing one editor core. **First** = a developer *designer* in the `tools/` harness — **✅ v1 shipped as 19C Item 5 (2026-09-04)**: three-part `tools/theme_customizer.html` (real-gallery preview / token editing / click-to-reflect + primitive-picker editing → JSON a coding agent ports into `base.html`). **Stretch** = an operator *tweaker* in the app saving **browser-local** (localStorage + runtime-apply, no migration) — deferred (`deferred_consolidated.md` Part A). DB-backed shared/persistent themes noted as a further future neither plan does. |
| `deferred_consolidated.md` | The single ledger of all scoped-but-not-scheduled work, ordered by disposition. **Part A** — features paused but expected pending pilot feedback (ships + why deferred + lift trigger + wire-up per entry). **Part B** — infrastructure / platform hardening deferred until production pressure (Postgres-native types, VNet, Key Vault, etc.). **Part C** — future possibilities deliberately off-roadmap. Consolidated 2026-08-19 from the former `deferred_until_pilot_feedback.md` / `deferred_infra.md` / `future_possibilities.md` (now in `archive/`). Distinct from `todo_master.md` (committed sequence). |
| `archive/` | Shipped segment plans (kept for historical reference; not the source of truth for current behavior — see `docs/status.md` for that). The early `low_intensity_workplan_review_robin_web.md`, `major_refactor.md`, and `rules_table.md` are archived here too — superseded by the segment plans + `todo_master.md` and (for `rules_table.md`) the seed table in `spec/assignments.md` (which absorbed the pre-2026-05-26 `rule_based_assignment.md`, now under `spec/archive/`). `archive/README.md` is a hand-maintained index of every file in the folder — keep it in sync when you archive something. |

Sibling folders:

- **`spec/`** — surface specifications and design intent (what
  the UI should look like).
- **`docs/`** — reference material about the running system (how
  things actually work today).

# spec/

**Surface specifications and design intent.**

Answers the question: *what is X supposed to look like and behave
like?* Each file is a contract that the templates, services, and
tests should match. When the code drifts from a spec, the spec is
the canonical source — fix the code (or update the spec
deliberately as part of a feature change, never silently).

| File | Covers |
|---|---|
| `architecture.md` | Domain entities, layering, conceptual hierarchy, pair-vs-assignment context. |
| `functional_spec.md` | Technology-neutral functional specification — what the system must do regardless of implementation. |
| `audience_and_identity_model.md` | Conceptual map of who uses Review Robin — audiences (operator, reviewer, plus forward-looking reviewee and sysadmin), auth posture, customization boundaries. The "highest-ranking" doc on identity / audience decisions; visual-style choices follow from it. |
| `visual_style_general.md` | Portable visual design system — palette, typography, spacing, components, patterns. Authoritative for the general visual vocabulary used across all surfaces. |
| `visual_style_rrw.md` | Review-Robin instantiation of the general spec — accent assignments, lifecycle colors, two-row session chrome, status strip, warning surfaces, non-session operator chrome, reviewer-facing chrome. Reads downstream of `visual_style_general.md` and `audience_and_identity_model.md`. |
| `operator_ui_concept.md` | Operator-facing page surface — page taxonomy (Overview, Control Panel, Setup Pages, Preview Pages, Operations Pages), navigation principles, per-page contracts. Reads upstream of `visual_style_rrw.md`. |
| `preview_hub.md` | Functional spec for the Reviewer Experience Preview hub — read-only Operations Page rendering invitation email, response form, reminder email, and responses-received email for an operator-selected reviewer. |
| `quick_setup_card_spec.md` | Functional spec for the Quick Setup card on Session Home — three-slot CSV upload (Reviewers, Reviewees, Assignments-or-rule) with shared confirm + cascade + lifecycle-lock semantics. |
| `reviewer-surface.md` | Reviewer-facing app — multi-instrument-aware response surface (`/reviewer/sessions/{id}/{position}`), dashboard (`/reviewer`), and invitation landing (`/reviewer/invite/{token}`). Supersedes `reviewer_map.md`. |
| `reviewer_map.md` | **Superseded by `reviewer-surface.md`** — kept until the surface rewrite ships, then retired. |
| `assumptions.md` | UI vocabulary — six canonical button styles, typography knob, layout defaults, load-bearing assumptions. |

Sibling folders:

- **`docs/`** — reference material about the running system (how
  things actually work today).
- **`guide/`** — forward-looking plans, todos, segment-by-segment
  workplans.

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
| `operator_map.md` | Operator-facing page surface — chrome, setup nav, lock card, per-page layout and affordances. |
| `assumptions.md` | UI vocabulary — six canonical button styles, typography knob, layout defaults, load-bearing assumptions. |

Sibling folders:

- **`docs/`** — reference material about the running system (how
  things actually work today).
- **`guide/`** — forward-looking plans, todos, segment-by-segment
  workplans.

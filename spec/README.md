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
| `audience_and_identity_model.md` | Conceptual map of who uses Review Robin — audiences (operator, reviewer, plus forward-looking reviewee and sysadmin), auth posture, customization boundaries. The "highest-ranking" doc on identity / audience decisions; visual-style choices follow from it. |
| `visual_style_general.md` | Portable visual design system — palette, typography, spacing, components, patterns. Authoritative for the general visual vocabulary used across all surfaces. |
| `visual_style_rrw.md` | Review-Robin instantiation of the general spec — accent assignments, lifecycle colors, two-row session chrome, status strip, warning surfaces, non-session operator chrome, reviewer-facing chrome. Reads downstream of `visual_style_general.md` and `audience_and_identity_model.md`. |
| `operator_ui_concept.md` | Operator-facing page surface — page taxonomy (Overview, Control Panel, Setup Pages, Preview Pages, Operations Pages), navigation principles, per-page contracts. Reads upstream of `visual_style_rrw.md`. |
| `preview_hub.md` | Functional spec for the Reviewer Experience Preview hub — read-only Operations Page rendering invitation email, response form, reminder email, and responses-received email for an operator-selected reviewer. |
| `quick_setup_card_spec.md` | Functional spec for the Quick Setup card on Session Home — three-slot CSV upload (Reviewers, Reviewees, Assignments-or-rule) with shared confirm + cascade + lifecycle-lock semantics. |
| `setup_pages.md` | UI spec for the per-session Setup Pages (Reviewers / Reviewees / Assignments / Instruments / Settings). Covers the shared body shape, the visibility-toggle pattern shared across the three preview tables, and per-page column orders. |
| `group_scoped_instruments.md` | Forward-looking spec for **group-scoped instruments** — a second instrument flavour where one response covers a group of reviewees rather than one. `Instrument.group_kind` set at creation (not toggleable); duplicate-and-stamp on `Assignment.context` so `Response`'s schema doesn't change. Implementation likely lands alongside or after Segment 13A. |
| `instruments.md` | Locked spec for the per-session **Instruments** operator page (`/operator/sessions/{id}/instruments`) — page layout, header card, per-instrument card structure, response-fields builder. Moved 2026-05-07 from `guide/` since the page has shipped and the file is now a contract, not a forward-looking plan. |
| `sort_by_reviewee.md` | Forward-looking functional spec for **Segment 13B** — reviewer-surface sort UX (operator default sort + reviewer live override) on Manage pages. Display Fields only on the operator side; reviewer side gets clickable column headers with live-only persistence. |
| `reviewer-surface.md` | Reviewer-facing app — multi-instrument-aware response surface (`/reviewer/sessions/{id}/{position}`), dashboard (`/reviewer`), and invitation landing (`/reviewer/invite/{token}`). |
| `domain_assumptions.md` | UI vocabulary — six canonical button styles, typography knob, layout defaults, load-bearing assumptions. |
| `settings_inventory.md` | Single-stop reference for every operator- and per-session setting Review Robin Web persists — operator SMTP config, session metadata, email-template overrides, instrument settings, reviewer / reviewee tags, RuleSets, and the browser-local UI-state primitives (cookies / localStorage / URL params). Names where each setting lives, the UI surface that edits it, and the canonical per-page spec. |
| `operator_button_audit.md` | Operator-surface button audit — every button (and button-styled anchor) across the operator templates, organised by page and card with continuous numbering and per-button canonical-style labels (per `spec/ui_elements.md` §6). Moved 2026-05-10 from `guide/` since it documents the as-shipped surface, not a forward-looking plan. |

Sibling folders:

- **`docs/`** — reference material about the running system (how
  things actually work today).
- **`guide/`** — forward-looking plans, todos, segment-by-segment
  workplans.

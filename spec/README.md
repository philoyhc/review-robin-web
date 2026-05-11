# spec/

**Surface specifications and design intent.**

Answers the question: *what is X supposed to look like and behave
like?* Each file is a contract that the templates, services, and
tests should match. When the code drifts from a spec, the spec is
the canonical source — fix the code (or update the spec
deliberately as part of a feature change, never silently).

Files are grouped by concern below. Within each group, the file
listed first is the natural entry-point.

## Conceptual / domain layer

The "what is this thing?" layer. Read these first when onboarding.

| File | Covers |
|---|---|
| `audience_and_identity_model.md` | Who uses Review Robin — operator / reviewer audiences, plus forward-looking reviewee and sysadmin. Auth posture and customization boundaries. The "highest-ranking" doc on identity / audience decisions; visual-style choices follow from it. |
| `architecture.md` | Domain entities, three-layer split (routes → services → models), conceptual hierarchy, pair-level context (post-15D `relationships` table), audit-event detail schema (canonical envelopes, strict-mode gate). |

## Per-page operator contracts

The actual operator pages. `operator_ui_concept.md` is the
taxonomy + navigation index; the per-page specs below it are the
detailed contracts.

| File | Covers |
|---|---|
| `operator_ui_concept.md` | Operator-facing page surface — page taxonomy (Overview, Control Panel, Setup Pages, Preview Pages, Operations Pages), navigation principles, per-page contracts. |
| `sessions_overview.md` | Sessions lobby (`/operator/sessions`) — table, Create new, Danger Zone bulk delete. |
| `session_home.md` | Session Home / Control Panel — Next Action card, Extract Data card, Quick Setup card, Session Details, Danger Zone. |
| `setup_pages.md` | Setup Pages (Reviewers / Reviewees / Relationships) — shared body shape, visibility-toggle pattern, per-page column orders. |
| `instruments.md` | Locked spec for the per-session Instruments page — per-instrument card, response-fields builder, RTD card. |
| `quick_setup_card_spec.md` | Quick Setup card on Session Home — four-slot CSV upload (Reviewers / Reviewees / Relationships / Settings) with shared confirm + cascade + lifecycle-lock semantics. |
| `preview_hub.md` | Reviewer Experience Preview hub — read-only Operations Page rendering invitation email, response form, reminder email, and responses-received email for an operator-selected reviewer. |
| `operations_pages.md` | Operations pages — Invitations + Responses (reviewer-centric + reviewee-centric monitoring surfaces). |
| `rule_based_assignment.md` | Rule-based assignment engine + Rule Builder page + Rule Based card on the Operations Assignments page. |

## Reviewer-facing

| File | Covers |
|---|---|
| `reviewer-surface.md` | Reviewer-facing app — multi-instrument-aware response surface (`/reviewer/sessions/{id}/{position}`), dashboard (`/reviewer`), and invitation landing (`/reviewer/invite/{token}`). |

## Visual / UI vocabulary

Reading order: `visual_style_general.md` (portable design system)
→ `visual_style_rrw.md` (RRW instantiation) → `ui_elements.md`
(element catalogue mapping primitives to CSS classes) →
`operator_button_audit.md` (per-page button audit).

| File | Covers |
|---|---|
| `visual_style_general.md` | Portable visual design system — palette, typography, spacing, components, patterns. Authoritative for the general visual vocabulary used across all surfaces. |
| `visual_style_rrw.md` | Review-Robin instantiation of the general spec — accent assignments, lifecycle colors, two-row session chrome, status strip, warning surfaces, non-session operator chrome, reviewer-facing chrome. |
| `ui_elements.md` | Element catalogue — canonical name + canonical visual treatment + current implementation per element family (chrome, cards, tables, buttons, forms, banners, badges, layout primitives). |
| `operator_button_audit.md` | Operator-surface button audit — every button (and button-styled anchor) across the operator templates, organised by page and card with per-button canonical-style labels. |
| `domain_assumptions.md` | Load-bearing **domain** (Session + Instrument) assumptions. The UI-vocabulary sections that used to live here were superseded 2026-05-03 and retired 2026-05-11 (UI-mechanics now in `ui_elements.md` §6 + §5a + §10; legacy content preserved at `guide/archive/assumptions_ui_legacy.md`). |

## Reference indexes

| File | Covers |
|---|---|
| `settings_inventory.md` | Single-stop reference for every operator- and per-session setting Review Robin Web persists — operator SMTP config, session metadata, email-template overrides, instrument settings, reviewer / reviewee tags, RuleSets, and the browser-local UI-state primitives (cookies / localStorage / URL params). |
| `csv_contracts.md` | Column shapes + parsing rules for the five extracts (Reviewers / Reviewees / Relationships / Responses / Settings / audit events) and the four importers (Reviewers / Reviewees / Relationships / Settings). Round-trip stability rules, two-phase parse + apply contract for Settings, shared parsing primitives. |
| `email_infra_options.md` | Email backend architecture — pluggable-sender scaffolding, Options A (SMTP) / B (Microsoft Graph) / C (Azure Communication Services) / D (third-party transactional), `email_outbox` schema. |

## Forward-looking segment specs

Specs for shipped-segment-pending features. These describe the
target contract; the code doesn't match them yet.

| File | Covers |
|---|---|
| `sort_by_reviewee.md` | **Segment 13B** — reviewer-surface sort UX (operator default sort + reviewer live override). Display Fields only on the operator side; reviewer side gets clickable column headers with live-only persistence. |
| `group_scoped_instruments.md` | **Segment 13C** — group-scoped instruments (one shared response covers a whole group of reviewees). Plan needs revision post-15D since it originally stamped per-instrument flavour onto the now-dropped `Assignment.context` JSON column. |

---

Sibling folders:

- **`docs/`** — reference material about the running system (how
  things actually work today).
- **`guide/`** — forward-looking plans, todos, segment-by-segment
  workplans.

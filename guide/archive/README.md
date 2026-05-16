# guide/archive/

**Shipped and superseded planning documents — historical reference only.**

These are the segment plans and cross-cutting planning docs that
have served their purpose: the segment shipped, or the plan was
superseded by a later one. They are kept for historical
reference — *what we intended and why* — but they are **not the
source of truth for current behaviour**. For how the system
works today, see `docs/status.md`; for what's planned next, see
`guide/todo_master.md` and the active `guide/segment_*.md`.

> **Maintenance rule.** This README is a manual index — there is
> no automation behind it. **Whenever a file is added to
> `guide/archive/`, add its row to the matching table below in
> the same change.** Archiving a shipped segment plan is part of
> segment closeout (see `guide/README.md`); updating this index
> is part of that same step. A file in the directory with no row
> here is a bug.

Line counts below are approximate and not kept in lockstep with
edits — they are a rough size signal, not a tracked metric.

## Reference & cross-cutting

| File | ~Lines | Covers |
|---|---:|---|
| `functional_spec.md` | 1174 | The technology-neutral functional specification — the contract the codebase assessments audit against. Moved here from `spec/` on 2026-05-11; its §21 / §22 / §23 numbering is still cited. |
| `low_intensity_workplan_review_robin_web.md` | 1127 | The project's original low-intensity AI-assisted workplan — the first end-to-end plan. Superseded by the segment plans + `todo_master.md`. |
| `major_refactor.md` | 1017 | The May 2026 refactor that split `routes_operator.py` and `views.py` into feature-area / by-concern packages. Still cited by `CLAUDE.md` for the slice-boundary rationale. |
| `rules_table.md` | 91 | Early canonical RuleSet cases table — superseded by the seed table in `spec/rule_based_assignment.md` §5.4. |
| `unfinished_business.md` | 1669 | The retired open-items catalog. "Catalog #N" references in `todo_master.md` point here. Retired 2026-05-10 once its items shipped or were absorbed into named segments. |
| `segment_1-10_unfinished.md` | 438 | Audit of unfinished items across Segments 1–10. |
| `assumptions_ui_legacy.md` | 119 | The legacy UI section carved out of `spec/domain_assumptions.md`. |
| `ui_elements_parts_2_3_restyle_history.md` | 111 | Historical UI-elements catalogue, Parts 2 + 3. |

## Segment plans

Segments 1–8 each carry both an original `_plan.md` and a later
`…A.md` *Agreed Plan* (the revised version actually built).
Where a segment was re-scoped, the superseded plan is kept
alongside its replacement.

| File | ~Lines | Covers |
|---|---:|---|
| `segment_01_repository_setup_plan.md` | 967 | Segment 1 — repository setup + AI-friendly project skeleton. |
| `segment_02_azure_hello_world_deployment_plan.md` | 408 | Segment 2 — Azure hello-world deployment. |
| `segment_03_authentication_poc_plan.md` | 456 | Segment 3 — authentication proof-of-concept. |
| `segment_04_core_data_model_migrations_plan.md` | 478 | Segment 4 — core data model + migrations (original plan). |
| `segment_04A.md` | 287 | Segment 4A — core data model + migrations (agreed plan). |
| `segment_05_operator_session_setup_mvp_plan.md` | 374 | Segment 5 — operator session-setup MVP (original plan). |
| `segment_05A.md` | 421 | Segment 5A — operator session-setup MVP (agreed plan). |
| `segment_06_import_validation_mvp_plan.md` | 322 | Segment 6 — import + validation MVP (original plan). |
| `segment_06A.md` | 489 | Segment 6A — import + validation MVP (agreed plan). |
| `segment_07_assignment_generation_mvp_plan.md` | 287 | Segment 7 — assignment generation MVP (original plan). |
| `segment_07A.md` | 478 | Segment 7A — assignment generation MVP (agreed plan). |
| `segment_08_reviewer_surface_mvp_plan.md` | 338 | Segment 8 — reviewer review-surface MVP (original plan). |
| `segment_08A.md` | 582 | Segment 8A — reviewer review-surface MVP (agreed plan). |
| `segment_09_superseded_single_plan.md` | 487 | Segment 9 — original single-plan (invitations / monitoring / reminders / instrument open-close); superseded. |
| `segment_09_invitation_monitoring_reminder_split_plan.md` | 201 | Segment 9 — superseding plan that split it into 9.1 → 9.5. |
| `segment_09_1_session_readiness_activation_response_window_plan.md` | 44 | Segment 9.1 — session readiness, activation lifecycle, response-window control (plan). |
| `segment_09_1A.md` | 241 | Segment 9.1A — session readiness / activation / response-window gates (implementation plan). |
| `segment_09_2_invitations_dev_outbox_plan.md` | 30 | Segment 9.2 — invitations, dev outbox, reviewer-access links (plan). |
| `segment_09_2A.md` | 188 | Segment 9.2A — invitations, dev outbox, reviewer-access tokens (implementation plan). |
| `segment_09_3_monitoring_reminders_plan.md` | 26 | Segment 9.3 — monitoring + reminders (optional plan). |
| `segment_09_3A.md` | 155 | Segment 9.3A — monitoring + reminders (implementation plan). |
| `segment_09_4_operator_ui_restructure_plan.md` | 323 | Segment 9.4 — operator UI restructure to the target page map (plan). |
| `segment_09_4A.md` | 260 | Segment 9.4A — page chrome + breadcrumbs + sessions-list reshape. |
| `segment_09_4B.md` | 128 | Segment 9.4B — session-detail four-card restructure + inline validate-summary + Delete Data. |
| `segment_09_4C.md` | 74 | Segment 9.4C — Manage-page reshapes + instruments index + `/setupinvite` stub + close-out. |
| `segment_09_5A.md` | 57 | Segment 9.5A — setup-readiness lifecycle states. |
| `segment_10_instrument_builder_mvp_plan.md` | 542 | Segment 10 — instrument builder MVP (plan). |
| `segment_10A.md` | 663 | Segment 10A — response-field builder + reviewer-surface refactor. |
| `segment_10B.md` | 245 | Segment 10B — display-fields picker + operator preview (umbrella plan). |
| `segment_10B_1.md` | 483 | Segment 10B-1 — data-driven reviewer-surface render. |
| `segment_10B_2.md` | 589 | Segment 10B-2 — operator display-field builder. |
| `segment_10B_3.md` | 460 | Segment 10B-3 — operator preview route. |
| `segment_10C.md` | 337 | Segment 10C — operator UI clean-up (first round). |
| `segment_10D.md` | 910 | Segment 10D — Instruments page rebuild. |
| `segment_11A_cleaning_up_unfinished_business.md` | 74 | Segment 11A — cleaning up unfinished business. |
| `segment_11B_session_home.md` | 297 | Segment 11B — Session Home rebuild. |
| `segment_11C_operations_consolidation.md` | 428 | Segment 11C — Operations consolidation (Invitations + Responses) + outbox audit-log scaffolding. |
| `segment_11D_v2_sweep_non_session.md` | 701 | Segment 11D — v2 sweep across the non-session-centric pages. |
| `segment_11E_email_template_editor.md` | 919 | Segment 11E — operator-editable email template editor + SMTP scaffolding. |
| `segment_11F_previews_page.md` | 827 | Segment 11F — Previews page (pre-flight reviewer-experience hub). |
| `segment_11G_validate_page.md` | 621 | Segment 11G — Validate page. |
| `segment_11H_placeholder_card_scaffolds.md` | 443 | Segment 11H — placeholder card scaffolds (Quick Setup + Extract Data). |
| `segment_11J_quick_setup_card.md` | 566 | Segment 11J — Quick Setup card. |
| `segment_11K_audit_event_detail_schema.md` | 594 | Segment 11K — the audit-event `detail` schema convention. |
| `segment_11L_instrument_short_label.md` | 410 | Segment 11L — Instruments page friendly short label. |
| `segment_12A-1_export.md` | 1204 | Segment 12A-1 — session export (settings + reviewers + reviewees + assignments CSVs). |
| `segment_12A-2_import.md` | 802 | Segment 12A-2 — session settings import (absorbed into 12A-3 PR 3). |
| `segment_12A-3_export_import_updates.md` | 443 | Segment 12A-3 — export / import updates for 15D. |
| `segment_12B_audit_retention.md` | 309 | Segment 12B — audit-events export. |
| `segment_12C_self-review_revamp.md` | 891 | Segment 12C — self-review revamp + Quick Setup upload semantics + chrome reorder. |
| `segment_13_multi_instrument_sessions_superseded.md` | 345 | Segment 13 — multi-instrument sessions (original plan; superseded). |
| `segment_13A_rulebased_assignment_builder.md` | 1491 | Segment 13A — Advanced (RuleBased) assignment mode. |
| `segment_13A_1_rule_based_editor_revamp.md` | 428 | Segment 13A-1 — Rule Based editor revamp. |
| `segment_13B_sort_tables.md` | 558 | Segment 13B — sortable tables (reviewer + operator surfaces). |
| `segment_13D_db_prep.md` | 531 | Segment 13D — DB prep for the library / per-session-copy split. |
| `segment_13E_db_prep.md` | 209 | Segment 13E — DB prep for the 12C / 15D block. |
| `segment_15_operator_polish_and_documentation.md` | 138 | Segment 15 — operator polish + documentation (umbrella). |
| `segment_15A_friendly_labels.md` | 670 | Segment 15A — pervasive friendly labels. |
| `segment_15B_per_instrument_assignments.md` | 783 | Segment 15B — per-instrument assignments. |
| `segment_15C_operator_libraries.md` | 379 | Segment 15C — operator RTD / RuleSet libraries. |
| `segment_15D_assignments_revamp.md` | 783 | Segment 15D — Assignments revamp: Pair Context as Setup primary. |
| `segment_15E_operations_workflow_card.md` | 632 | Segment 15E — Operations Workflow Card. |
| `segment_15F_enhanced_setup_pages.md` | 710 | Segment 15F — enhanced Setup pages (per-row inline edit). |
| `segment_16A_sys_admin_page.md` | 848 | Segment 16A — Sys Admin page + admin user role. |
| `segment_16B_role_delegation.md` | 331 | Segment 16B — user role management + role delegation among operators. |
| `segment_16C_richer_audit_views.md` | 376 | Segment 16C — richer audit views (in-app audit-log viewer). |
| `segment_17A_housekeeping.md` | 184 | Segment 17A — housekeeping: file splits + test-suite runtime. |
| `segment_18B_date_and_time_settings.md` | 452 | Segment 18B — date and time settings (display formatting + timezones). |

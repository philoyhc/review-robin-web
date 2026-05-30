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
| `seg9stuff` | 67 | Segment 9 planning Q&A — the open-question / decision scratch notes (lifecycle enum, token path, edit-while-active) settled before the 9.1 → 9.5 split. |
| `assumptions_ui_legacy.md` | 119 | The legacy UI section carved out of `spec/domain_assumptions.md`. |
| `ui_elements_parts_2_3_restyle_history.md` | 111 | Historical UI-elements catalogue, Parts 2 + 3. |
| `ui_checklist.md` | 197 | The v1 restructure + v2 `body.ui-v2` sweep per-page tracking checklist — both passes complete; retired to archive 2026-05-19 once the sweep stopped being a living tracker. |
| `spec_sweep_11may.md` | 657 | The 2026-05-11 `spec/` drift + consolidation audit proposal (F1-F8 / C1-C5 / S1-S5) — all items merged, proposal closed. Its "Done vs Remaining" coverage-gap list is the input for Segment 19 Part 1. |
| `codebase_assessment_09may.md` | 373 | Codebase-vs-functional-spec snapshot, 2026-05-09. Superseded by later assessments; the latest active snapshot lives at `guide/codebase_assessment_30may.md`. |
| `codebase_assessment_11may.md` | 420 | Codebase-vs-functional-spec snapshot, 2026-05-11. Frequently cited from archived segment plans (16B / 16C / 18A / 18C) — those references were redirected to this archive path when it moved. |
| `codebase_assessment_16may.md` | 452 | Codebase-vs-functional-spec snapshot, 2026-05-16. Anchored Segment 17A housekeeping + 17B reviewer-surface refinements. |
| `codebase_assessment_17may.md` | 235 | Codebase-vs-functional-spec snapshot, 2026-05-17. |
| `codebase_assessment_18may.md` | 234 | Codebase-vs-functional-spec snapshot, 2026-05-18. |
| `codebase_assessment_19may.md` | 269 | Codebase-vs-functional-spec snapshot, 2026-05-19 (the close of Segment 13C / 14A / 17A and the 18-family up to 18E + 18D). Archived 2026-05-28 once superseded by `guide/codebase_assessment_28may.md` (since archived). |
| `codebase_assessment_28may.md` | 458 | Codebase-vs-functional-spec snapshot, 2026-05-28 (the close of Segment 18K / 18L / 18M / 18N first half). 2,010 tests; ~63.8k production LOC; biggest file `_instrument_crud.py` at 1,928 LOC. Archived 2026-05-30 once superseded by `guide/codebase_assessment_30may.md`. |

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
| `segment_13C_enhanced_instrument.md` | 647 | Segment 13C — enhanced instruments (group-scoped instruments + the Replicate-instrument button). |
| `segment_13D_db_prep.md` | 531 | Segment 13D — DB prep for the library / per-session-copy split. |
| `segment_13E_db_prep.md` | 209 | Segment 13E — DB prep for the 12C / 15D block. |
| `segment_13F_more_db_prep.md` | 786 | Segment 13F — DB prep for the 16A / 16B / 18A / 18B / 18G ride-along. Five of seven PRs shipped (1 / 2 / 3 / 6 / 7); the two outstanding (PR 4 `reminder_settings`, PR 5 `retention_*`) plus the pending scheduled-lifecycle schema audit were folded into **Segment 18G Part 0 — Schema pre-positioning** on 2026-05-20 and the plan retired here. |
| `segment_14A_production_hardening.md` | 588 | Segment 14A — production hardening (in-app ladder: logging, error handling, index review, permission audit, docs, deploy-workflow hardening). |
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
| `segment_17B_reviewer_surface_refinements.md` | 468 | Segment 17B — reviewer surface refinements. Phase 1 shipped 2026-05-16 (`routes_reviewer/` package split, action-row reorder + keyboard nav, visible-progress pills; sticky headers investigated and dropped); Phase 2 shipped 2026-05-20 (PR A: six-column lobby with two status columns + `sessions.activated_at` + the pre-ready "not opened" state; PR B: per-session participation-summary page + `{code}_my_responses.csv` download; URL rename `/reviewer/` → `/user/` considered and deferred per `participant_model_upgrade.md`). Cell autosave / filter-to-incomplete / return-to-place / chrome polish carved out to `deferred_until_pilot_feedback.md`. |
| `segment_18A_sessions_lobby_enhancements.md` | 619 | Segment 18A — Sessions lobby enhancements (tagging, archiving, cloning, search, sort). |
| `segment_18B_date_and_time_settings.md` | 452 | Segment 18B — date and time settings (display formatting + timezones). |
| `segment_18C_retention_deletion.md` | 159 | Segment 18C — operator-triggered purge ("Purge and archive" expander action). |
| `segment_18D_export_and_import_update.md` | 426 | Segment 18D — export / import update (Parts 3 / 5 ride 13C and deferred 18G Part 5). |
| `segment_18E_small_enhancements.md` | 157 | Segment 18E — small enhancements holding pen (Parts 1-3 shipped 2026-05-18: column-visibility chips, eligible-pair count cache, friendly-label Fields-with-data pills). Closed 2026-05-20; future small enhancements land on Segment 18H. |
| `segment_18F_workflow_optimization.md` | 519 | Segment 18F — workflow optimization (Prepare/Activate split + pre-activation invitations + reviewer pre-open state). Created 2026-05-19; Parts 1/2 shipped 2026-05-20; closed and archived 2026-05-22 after codebase check found no additional committed Part 3+ scope. |
| `segment_18G_scheduled_events.md` | 939 | Segment 18G — scheduled events (anchors + offsets model; Parts 0-3 shipped, Parts 4-5 deferred). Renumbered from 18F on 2026-05-19; closed and archived 2026-05-22 after remaining items were explicitly deferred. |
| `segment_18H_post_assessment_update.md` | 269 | Segment 18H — small post-assessment-update holding pen following the 19may codebase assessment. Closed and archived after its items shipped or got absorbed into named segments. |
| `segment_18J_new_model_takeover.md` | 753 | Segment 18J — new-model takeover mopping-up. Six-wave plan that closed every parity gap with the legacy individual + group instrument cards (Waves 1-3), refactored Lock/Unlock + readiness gating (Wave 4), retired the RuleSet library + the `is_new_model` flag (Wave 5), and landed a five-cluster polish tail (Wave 6 — RTD card retirement, operator preview ↔ reviewer surface parity, Save dirty-tracking, Band 1 caption affordance, Band 2 preview member-list accuracy). Shipped 2026-05-24 → 2026-05-26 (PRs #1393 → #1475); archived 2026-05-26. |
| `new_model_instruments_outstanding.md` | 707 | The Gap / Rec catalog Segment 18J consumed verbatim — Gap 1 → Gap 10 + Rec A → Rec E. Status banner at the top records all Gaps shipped; entries cross-link to the closing PRs. Archived 2026-05-26 alongside `segment_18J_new_model_takeover.md`. |
| `segment_18K_visibility.md` | 287 | Segment 18K — Completing instrument visibility (Band 3) on the reviewer surface. Six PRs across 2026-05-27 → 2026-05-28: summary HTML + reviewer-record CSV filter response fields by `visible` (PR #1487), spec rewrite to match the actual Band 2 chip/pill UI, Replicate copies `visible` as-is (PR #1545), Band 2 chip un-pin confirm guard with `acknowledged_drop` (PR #1549), and the reviewer-surface dropped-fields banner (PR #1550). Twelve regression tests in `tests/integration/test_reviewer_summary_visibility.py`. Archived 2026-05-28. |
| `segment_18L_single_page_surface.md` | 587 | Segment 18L — Multi-page reviewer surface (operator-defined). Reviewer surface paginates by operator-defined pages — one per run of instruments between Segment 18M page breaks — at `/reviewer/sessions/{id}/{page_n}`. The original lock called for a single-page-all-instruments model; PR #1522 reshaped mid-flight into the multi-page model. Shipped 2026-05-27 → 2026-05-28 (PRs #1518 → #1528). |
| `segment_18M_instrument_layout.md` | 537 | Segment 18M — Operator instrument ordering + page breaks. Drag-handle reorder on the operator Instruments page, plus an inline ``+`` page-break separator between instruments (mirrored to the reviewer surface as the multi-page boundary that Segment 18L consumes). Shipped 2026-05-27 → 2026-05-28. |
| `segment_18N_housekeeping.md` | 359 | Segment 18N — Housekeeping (file splits + reviewer-surface asymmetry + settings round-trip). Five PRs across 2026-05-28: PR 1 (#1556) aligned the reviewer-surface page-validity check between GET / POST save / preview; PRs 2 (#1557) / 3 (#1558) / 4 (#1559) split the three biggest production files into per-concern slices (``_instrument_crud.py`` 1,928 → 1,052; ``routes_operator/_instruments.py`` 1,497 → 1,027; ``responses.py`` 1,444 → 976); PR 5 (#1560) closed the settings CSV round-trip catch-up — the eight 18G ``ReviewSession`` columns plus the response-field inline type / bounds / visible (silently dropping every semantic bound for ~2 weeks after 18J Wave 2 PR iii-b4) plus ``Instrument.column_widths`` / ``starts_new_page`` / ``band2_state``. Six new round-trip regression tests in ``tests/unit/test_apply_session_config.py``. Archived 2026-05-28. |
| `instrument_builder_project.md` | 992 | Multi-segment design plan for the per-instrument card. Parts 0 / 1 / 1b / 1c / 1d / 2 shipped under Segments 18I + 18J; the original Parts 3-9 (Links 4 / 5 / 6 — Visibility / Read shape / Release timing including observer audiences) are now covered by the `participant_model_upgrade.md` umbrella for segments 21+, leaving this doc as a historical record of the per-instrument card design. Archived 2026-05-28. |
| `visibility_audit.md` | 240 | Per-route × per-state table of what a reviewer could see at every system state (lifecycle × instrument-accepting × deadline × submission). Built from the codebase, not the spec. Archived 2026-05-28 once Segment 18K closed the Band 3 per-field tail of the same story — `spec/reviewer-surface.md` + `spec/instruments.md` now carry the current per-route contract. Keep as a historical snapshot of the cross-product matrix; the per-route prose in those specs is the source of truth going forward. |
| `extract_data.md` | 1254 | Extract data — Session Home card split + new Operations tab + Data shaper. Two-phase landing. **Phase 1 (2026-05-29 → 2026-05-30, PRs #1565 → #1627)** shipped the Session Home card rename (Extract data → Extract setup), the new Extract data Operations tab, the per-instrument / Reviewer-metadata / Reviewee-metadata cards, and the full Data shaper with saved `data_shapes` (CRUD routes, file gen, Zip-all integration, Settings CSV round-trip). **Phase 2 (2026-05-30, PRs #1642 → #1647)** shipped the three-state *Self-review handling* chip on the two metadata cards + the Data shaper scope row — column-name suffix (`_self` / `_noself` / `_both`), filename suffix, audit `context.self_review_handling`, per-shape persistence on `data_shapes.self_review_handling`, Settings round-trip. Q4 (per-individual rows × `exclude_self`) pinned at the conservative interpretation in `data_shape_extract.py:578`. Archived 2026-05-30. |
| `self_review_consolidate.md` | 737 | Self-review consolidation — DB column + canonical helper sweep. Five-PR ladder that landed `Assignment.is_self_review` as the single source of truth for self-review classification. PR 1 (#1633) added the column + migration + the canonical `classify_self_review` helper, backfilled inert via the whole-group rule. PR 2 (#1634) wired every write path (regenerate, manual add, instrument clone / replicate, four edit triggers: reviewer email, reviewee identifier, reviewee boundary tag, relationship pair-context tag, instrument `group_kind`) to call the recompute helper. PR 3 (#1635) switched every reader (the two extracts, `count_self_reviews_in_assignments`, the per-instrument Self-review pill, the bulk toggle backend) to consume the column and **fixed the latent ``by_instrument_extract.py:436`` bug** that hardcoded `SelfReview = FALSE` on group-scoped rows. PR 4 (#1636) landed the post-regenerate continuous-gate invariant (`verify_self_review_classification`; strict in tests, log + auto-correct in production), updated `spec/assignments.md` to name the column as the source of truth, and dropped the bug-fix scope from `guide/extract_data.md`'s queued Self-review chip section. Shipped 2026-05-30; archived same day. **Addendum — chip-controlled drop of empty rows on the Data shaper + cross-card consistency sweep (PRs #1654 → #1660).** PR 6 (#1654) added the `include_empty_rows` boolean column + scope-row cycling-pill chip (`All rows` ↔ `Rows with data`) + `_Acc.is_empty()` drop predicate; closes Q4 (per-individual × `exclude_self` with empty aggregates) by implication. PR 7 (#1656) reverted the placeholder `Number of data rows: —` pill from PRs #1651 / #1652 after cost analysis ruled out live preflight. PR 8 (#1657) converted the three existing empty-row-drop chips on By instrument / Reviewer / Reviewee metadata cards to two-state cycling pills with explicit labels per state. PR 9 (#1658) swept the spec + settings-inventory + codebase-assessment + todo_master and archived this plan. PR #1659 unified preview-table labels across saved + edit modes (identity columns with a space, aggregate columns drop the self-review suffix, `both` no longer duplicates). PR #1660 closed out stale "placeholder" / "wiring slice still ahead" references in the spec intro. |

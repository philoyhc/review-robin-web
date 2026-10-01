# Sweep — corpus (2026-10-01)

**Swept:** 2026-10-01 at `68f28224` · **Scope:** `spec/` + `docs/` + root
practice docs (68 files) · **Previous sweep:**
`guide/sweep_2026-09-05_spec-docs.md` · **Trigger:** due by merges, 618 of
500 in 26 days of 56 (`guide/post_assessment_1oct.md` E3).

<!-- sweep-scope: corpus -->

**Read in full, all 68.** Nine `spec-writer` reads ran in verify mode, split
by area. Each read every file in its area against the code that file
describes, and none edited a spec. **This sweep changed no file in scope.**
Every divergence is recorded in `guide/findings_2026-10-01_corpus.md` with
who decides it. The register is where to act from; this record says what
was read and what was found, file by file.

## 0. Carried forward

The previous sweep's eight findings are closed (seven actioned, one
declined), per its ledger. Three declines from 2026-05-11 remain, and each
was re-read:

| Finding | From | Age | Now | Note |
|---|---|---|---|---|
| Tier 2 #6: standalone Relationships spec | 2026-05-11 | 143 d | declined | Still a section of `setup_pages.md`. Its trigger, pilot feedback, has not happened. |
| Tier 2 #8: standalone Operator Settings spec | 2026-05-11 | 143 d | declined | Still covered by `settings_inventory.md` §1 and `timezone_display.md`. Nothing this sweep found needs a page spec. |
| Tier 3 #10–12: new-session form, drill-in pages, outbox | 2026-05-11 | 143 d | declined | The new-session form is now specced in `session_owners.md` and `sessions_overview.md`. The other two are unchanged. |

## 1. Write or deepen

- `extract_data.md`: the Archive session (purge) card is unspecced anywhere (D8).
- `csv_contracts.md`: import caps and the `_read_dict_rows` shape (D5).
- `sort_by_reviewee.md`: group instruments and the `-1` key (A25).
- `operator_button_audit.md`: about 40 unaudited controls (E31).
- `visual_style_general.md`: a contrast-floor paragraph (E28).
- `rrw_functional_spec.md`: branching rules (G22); tags, owners, `/guide` and the theme (G25).
- `sessions_overview.md`: the expander's draft-only fields (C10).

## 2. Update in place

Ids are in the findings register. A **bold** count means a high-severity
finding is among them.

- `spec/instruments.md`: 4 (A1–A4).
- `spec/reviewer-surface.md`: **8** (A5–A12).
- `spec/participant_model.md`: 5 (A13–A17).
- `spec/visibility_policy.md`: **4** (A18–A21).
- `spec/sort_by_reviewee.md`: **6** (A22–A27). The operator UI it describes is not what ships.
- `spec/assignments.md`: **7** (B1–B7).
- `spec/workflow_card.md`: **7** (B8–B14).
- `spec/lifecycle.md`: 12 (B15–B26).
- `spec/validate_page.md`: 4 (B27–B30).
- `spec/setup_pages.md`: 7 (C11–C17).
- `spec/quick_setup_card_spec.md`: **6** (C1–C6).
- `spec/session_home.md`: 3 (C1, C7, C8).
- `spec/sessions_overview.md`: 2 (C9, C10).
- `spec/timezone_display.md`: 3 (C18–C20).
- `spec/preview_hub.md`: 1 (C21).
- `spec/csv_contracts.md`: 6 (D1–D6).
- `spec/extract_data.md`: **7** (D7–D13).
- `spec/roundtrip_coverage.md`: 2 (D14, D15).
- `spec/rehydrate.md`: 5 (D16–D20).
- `spec/settings_inventory.md`: 4 (D21–D24).
- `spec/email_template_editor.md`: **3** (D25–D27).
- `spec/ui_elements.md`: 9 (E1–E9).
- `spec/color_tokens.md`: 2 (E10, E11). All 80 primitives, 107 semantic rows and 16 scale tokens match.
- `spec/visual_style_rrw.md`: 8 (E12–E19).
- `spec/visual_style_general.md`: 5 (E25–E29), all rulings.
- `spec/operator_ui_concept.md`: 5 (E20–E24).
- `spec/operator_button_audit.md`: 6 (E30–E35).
- `spec/architecture.md`: **8** (F1–F8).
- `spec/permissions.md`: 2 (F9, F10).
- `spec/audience_and_identity_model.md`: 1 (F11).
- `spec/role_landing_and_visibility.md`: 1 (F12).
- `spec/role_navigator.md`: **2** (F13, F14).
- `spec/domain_assumptions.md`: 2 (F15, F16).
- `spec/operations_pages.md`: **4** (F17–F20).
- `spec/email_infra_options.md`: 4 (F21–F24).
- `spec/blob_storage.md`: 1 (F25).
- `spec/README.md`: 1 (F26), plus the Peer reviewer audience line.
- `spec/rrw_functional_spec.md`: 25 (G1–G25).
- `docs/architecture.md`: 5 (H1–H5).
- `docs/database.md`: 1 (H6).
- `docs/local_setup.md`: 1 (H7).
- `docs/security_posture.md`: 3 (H8–H10), plus G21.
- `docs/deployment_dev.md`: **6** (H7, H11–H15).
- `docs/deployment_nus.md`: **5** (H11, H16–H19).
- `docs/cli_setup.md`: 4 (H27–H30).
- `docs/backup_restore.md`: 2 (H31, H32).
- `docs/operations_runbook.md`: 1 (H13).
- `docs/README.md`: 1 (I11).
- `docs/known_limitations.md`: 2 (I3, I10).
- `docs/unenforced_conventions.md`: 1 (I20).
- `docs/status.md`: **5** (I1, I2, I7–I9), in its Capabilities and table sections, which are live. The timeline is history.
- `README.md`: 4 (I1, I2, I5, I6).
- `rrw_design_rationale.md`: **4** (I1–I3, I5).
- `rrw_sdd_in_practice.md`: 1 (I14).
- `CLAUDE.md` / `AGENTS.md`: 4 (I15–I18).
- `new_project_practices_setup.md`: 1 (I19), through `tools/practice_kit.py`.

## 3. Consolidate

- `docs/deployment_nus.md` and `docs/nus_azure_status_v7.md`: v7 is the status and `deployment_nus.md` the runbook. Move the settled open items out of the runbook (H16).
- `rrw_functional_spec.md` §13.2 should point at `validate_page.md` for the readiness rules (G12).
- `operator_ui_concept.md`'s Validate page section should point at `validate_page.md` (E23).

## 4. Retire

- `docs/azure_provision.md`, overtaken by the NUS environment (H21).
- `docs/azure_github_setup.md` (H24), into `deployment_nus.md`.
- `azure_ask.md`, answered differently (I12). It is already queued in `guide/post_azure_todo_checklist.md`.
- Sections:
  - `email_infra_options.md` "Doc impact" (F24).
  - `visual_style_rrw.md` "Doc impact" (E19).
  - `ui_elements.md` `.btn-cta` (E1).

Repoint each inbound reference before deleting; the dead-reference command in `guide/sweep_template.md` finds them.

## 5. Move

- `operations_pages.md`'s tree measurements go to `guide/app_responsiveness.md`, keeping the flat rule (F20).

## 6. Read, no action

- `spec/reconciling_regeneration.md`: algorithm, audit counts, Prepare dry-run and cache exclusion all match.
- `spec/session_owners.md`: templates, routes, services, cookie and middleware match.
- `docs/troubleshooting.md`.
- `docs/nus_azure_status_v7.md`.
- `CONTRIBUTING.md`.
- `constitution.md`.
- `docs/practice-audit-2026-09-04.md` and `docs/status_history.md`: dated records, read as history.

## 7. Not read

None. The parts read but **not verified** were:

- JavaScript-only and layout behavior, checked by identifier and CSS rule only. This covers the builder and data-shaper clients, sort clicks, and the E8 grid gap.
- The button-audit Notes cell by cell.
- The reviewer-pacing rationale in `visual_style_rrw.md`.
- Branch protection and CI timings.

## Mechanical entry points

- **Staleness.** 12 of 68 files were untouched since 2026-09-05, the stalest at 86 days (`rrw_design_rationale.md`), and 10 of those 12 had findings (`CONTRIBUTING.md` and `troubleshooting.md` did not). Eight are the `docs/` deployment set, last edited 2026-08-19.
- **Dropped commitments.** 707 of 719 committed paths were honoured. Of the 12 that were not, 9 no longer exist; none pointed at a spec this sweep found unread.
- **Orphan specs.** 17 files map to no routing module. All are cross-cutting, or describe a model rather than a route; none surprised.
- **Dead references.** Almost all are dated history in `docs/status.md`. The one live hit is outside scope: `.env.example` cites `guide/segment_05A.md`.
- **App diff since 2026-09-05.** 199 files changed. The surfaces 19T rebuilt (instruments, reviewer surface, sort) carry the most findings.

## Headline numbers

| | |
|---|---|
| In scope | 68 (40 `spec/`, 19 `docs/`, 9 root) |
| Read | 68 |
| Findings | 242: write 9 / update ~215 / consolidate 3 / retire 6 / move 1. Rows overlap where one finding names two specs. |
| Code defects | 6, plus 7 stale code comments (register §2) |
| Rulings needed | about 50, in about 35 groups (register §1) |
| Carried in / closed / still open | 3 / 0 / 3 (all declined) |
| Untouched since the previous sweep | 12 of 68; stalest 86 d |

**What this sweep says about the cadence.** The previous sweep read 13
files and found 8 findings. This one read all 68 and found about 240: 61
merges a week does more to specs than any close catches. The worst drift is
where 19T rebuilt a surface in place (sorting, reviewer surface,
instruments). The next worst is in documents whose subject moved without
a plan naming them: the deployment docs, which have been untouched since the
NUS environment was provisioned, and `docs/status.md`'s Capabilities
section. **Three specs say email identity is casefolded, but the code uses
`.lower()` deliberately**, and two separate reads found it. The most consequential findings are rulings,
not spec edits (register §1). Several look like code defects that reach
reviewers: email times in UTC, scheduled sends firing only on a Session
Home visit, and a session-wide write gate.

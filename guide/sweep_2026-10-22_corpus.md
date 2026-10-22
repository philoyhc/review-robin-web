# Sweep — corpus (2026-10-22)

**Swept:** 2026-10-22 at `00501f2e` · **Scope:** `spec/` + `docs/` + root
practice docs + `cordware/spec/` (63 files) · **Previous sweep:**
`guide/archive/sweep_2026-10-07_corpus.md` · **Trigger:** asked for by
the author with the 22 October assessment; not due by the cadence (15 of
56 days, 285 of 500 merges).

<!-- sweep-scope: corpus -->

**Read in full, all 63**, the long `docs/cordware_*` and `rrw_*` files
spot-checked (§6). Since 2026-10-07 the corpus gained the two
`cordware/spec/` files (segment 21), and 59 of the other 61 changed;
only `CONTRIBUTING.md` and `constitution.md` did not (`close_check --stale`). Six
`spec-writer` reads ran in verify mode, split by area, each reading every
file in its area against the code; none edited a file. **This sweep
changed no file in scope.** Every divergence is in
`guide/findings_2026-10-22_corpus.md` with who decides it. A bug sweep
ran beside it at the same commit (`guide/findings_2026-10-22_bugs.md`).
The mechanical passes: no dead cross-reference in `spec/`, `docs/` or
`cordware/spec/`; one surprising orphan, `spec/session_owners.md` (B7).

## 0. Carried forward

The 2026-10-07 register was archived with nothing open on 2026-10-09;
three items stayed carried by name:

| Finding | From | Age | Now | Note |
|---|---|---|---|---|
| old B27 = old G6: scheduled sends fire only from page loads | 2026-10-01 | 21 d | carried | Six pages now run the pass (16 Oct L4); a worker still awaits Azure, `guide/post_azure_todo_checklist.md` §7. |
| old D4: `responses_import._stage` overwrites duplicate rows | 2026-10-03 | 19 d | carried | Rehydrate, `guide/deferred_consolidated.md`. Its cousin D1 is new here. |
| old D19: Rehydrate is incomplete | 2026-10-01 | 21 d | carried | Same entry. |

## 1. Write or deepen

- `spec/architecture.md`: the `refuse_oversized_ids` dependency (F3).
- `spec/operator_button_audit.md`: the date-time field's buttons (E1).
- `spec/rehydrate.md`: the rule-set refusals at the settings apply (D5).
- `docs/deployment_dev.md`, `docs/deployment_nus.md`: `CORDWARE_APPS` (H8).

## 2. Update in place

Ids are in the register; a **bold** count includes a medium finding.

- `spec/instruments.md`: 1 (A3).
- `spec/reviewer-surface.md`: 1 (A3).
- `spec/participant_model.md`: 1 (A3).
- `spec/visibility_policy.md`: 1 (A3).
- `spec/role_landing_and_visibility.md`: 1 (A3).
- `spec/sort_by_reviewee.md`: 1 (A1).
- `spec/timezone_display.md`: 1 (A2).
- `spec/lifecycle.md`: **2** (B1, B6).
- `spec/session_home.md`: 1 (B2).
- `spec/validate_page.md`: **1** (B3).
- `spec/workflow_card.md`: 1 (B4).
- `spec/sessions_overview.md`: 1 (B5).
- `spec/rehydrate.md`: **3** (D1, D2, D9), plus D5 above.
- `spec/settings_inventory.md`: 3 (D3, D4, D9).
- `spec/roundtrip_coverage.md`: 3 (D4, D9, D10).
- `spec/email_infra_options.md`: 1 (D6).
- `spec/extract_data.md`: 1 (D7).
- `spec/csv_contracts.md`: 2 (D8, D9).
- `spec/setup_pages.md`: 1 (D9).
- `spec/ui_elements.md`: 2 (E6, E7).
- `spec/operator_button_audit.md`: 1 (E6), plus E1 above.
- `spec/visual_style_rrw.md`: 5 (E2–E6).
- `spec/operator_ui_concept.md`: 2 (E6, E7).
- `spec/architecture.md`: 2 (F1, code F2), plus F3 above.
- `spec/permissions.md`: 1 (F4).
- `spec/audience_and_identity_model.md`: 2 (F5, F6).
- `spec/README.md`: 1 (F7).
- `spec/rrw_functional_spec.md`: 1 (F8), plus F11 below.
- `cordware/spec/identity.md`: author F9.
- `docs/operations_runbook.md`, `docs/known_limitations.md`,
  `docs/database.md`, `docs/troubleshooting.md`, `docs/backup_restore.md`:
  **1** each (H1); `docs/known_limitations.md` also H3.
- `docs/deployment_nus.md`: **3** (H1, H3, H4), plus H7.
- `docs/README.md`, `docs/architecture.md`: **1** each (H3); `docs/architecture.md` also H7.
- `docs/cordware_stage0_baseline.md`: 1 (H5).
- `docs/local_setup.md`: 1 (H6).
- `docs/security_posture.md`: 1 (H7).
- `docs/deployment_dev.md`: 1 (H9), plus H8 above.
- `CONTRIBUTING.md`: **1** (H2).
- `rrw_sdd_in_practice.md`: 1 (H10).
- `rrw_design_rationale.md`: 1 (H11).

## 3. Consolidate

- `spec/rrw_functional_spec.md` → the narrower specs it restates (F11):
  survivors are the area specs; the donor keeps §1–3, §5, §8, §13, §14,
  §18, §19. Author.

## 4. Retire

- `spec/visual_style_rrw.md` "Sign-in surface", or mark it deferred (E5).
  Author.

## 5. Move

None.

## 6. Read, no action

- `spec/color_tokens.md` (80 primitives, 101 semantic rows, 14 scale
  tokens and every ratio match), `spec/visual_style_general.md`,
  `spec/quick_setup_card_spec.md`, `spec/session_owners.md` (content;
  B7 is its mapping), `spec/assignments.md`, `spec/email_template_editor.md`,
  `spec/operations_pages.md`, `cordware/spec/host.md`.
- `docs/unenforced_conventions.md`, `docs/setup_codespaces.md`,
  `docs/cli_setup.md`, `README.md`, `CLAUDE.md` / `AGENTS.md` (twins
  identical), `constitution.md`, `new_project_practices_setup.md`,
  `azure_ask.md`.
- **Spot-checked only:** `docs/cordware_nus_azure_status_2026-10-16_v8.md`
  (header, banner, commands), `docs/cordware_repository_strategy_v0.8.md`
  (§1, the stage lists, code references), and the narrative sections of
  `rrw_sdd_in_practice.md` and `rrw_design_rationale.md`.

## 7. Not read

None in scope. Not verifiable from here: Azure resource facts, what the
dormant dev slot serves, Codespaces behavior, rendered layout and
browser-only behavior, and Postgres lock semantics (read, not run).

## Headline numbers

| | |
|---|---|
| In scope | 63 |
| Read | 63 (4 in part) |
| Findings | 49 (write 4 / update 43 / consolidate 1 / retire 1 / move 0) |
| Carried in / closed / still open | 3 / 0 / 3 |

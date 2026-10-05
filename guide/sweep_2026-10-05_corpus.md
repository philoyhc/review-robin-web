# Sweep — corpus (2026-10-05)

**Swept:** 2026-10-05 at `2d7e5b5f` · **Scope:** `spec/` + `docs/` + root
practice docs (58 files) · **Previous sweep:**
`guide/archive/sweep_2026-10-03_corpus.md` · **Trigger:** asked for by the
author with a new codebase assessment; not due by the cadence (2 of 56 days,
53 of 500 merges).

<!-- sweep-scope: corpus -->

**Read in full, all 58.** The corpus is ten files smaller than on
2026-10-03: four specs folded or retired (#2813–#2816) and `docs/`'s status
pair and three Azure and audit documents archived (#2796, #2812, #2826).
Nine `spec-writer` reads ran in verify mode, split by area, each reading
every file in its area against the code. None edited a file. **This sweep
changed no file in scope.** Every divergence is in
`guide/findings_2026-10-05_corpus.md` with who decides it; act from the
register. This record says what was read and what was found, file by file.

## 0. Carried forward

Every finding of the 2026-10-03 register is closed (archived with nothing
open, #2808); three were carried by name and stay so:

| Finding | From | Age | Now | Note |
|---|---|---|---|---|
| old B27 = old G6: scheduled sends fire only from Session Home | 2026-10-01 | 4 d | carried | `guide/post_azure_todo_checklist.md` §7; awaits Azure. |
| old D4: `responses_import._stage` overwrites duplicate rows | 2026-10-03 | 2 d | carried | Rehydrate, `guide/deferred_consolidated.md`. |
| old D19: Rehydrate is incomplete | 2026-10-01 | 4 d | carried | Same entry. |

Two older findings were fixed only in part and are re-reported: old A5 as
A9, and the functional spec's old G3 and G17 as G18 and G17.

## 1. Write or deepen

- `instruments.md`: the per-concern route inventory (A6).
- `workflow_card.md`: the `archived` state (B11).
- `validate_page.md`: the query parameters (B14).
- `extract_data.md`: `include` filtering across the lenses (D6).
- `csv_contracts.md`: per-cell length limits (D11); required Settings fields and `csv_list` (D22).
- `operator_button_audit.md`: the Rehydrate page, the sort-error Cancel, the builder's row buttons (E4–E6).
- `ui_elements.md`: fifteen uncatalogued `base.html` primitives (E15).
- `rrw_functional_spec.md`: empty super-admin list, Invite by email, the visibility-grid audit, Link 3's Self reviews control (G13–G16).

## 2. Update in place

Ids are in the register. A **bold** count means a medium-or-higher finding
is among them.

- `spec/instruments.md`: **8** (A2–A6, A11, A12, A16).
- `spec/reviewer-surface.md`: 6 (A7–A10, A13, A14).
- `spec/participant_model.md`: 4 (A1, A10, A13, A14).
- `spec/visibility_policy.md`: 1 (A17).
- `spec/sort_by_reviewee.md`: 2 (A13, A15).
- `spec/lifecycle.md`: **7** (B1–B7).
- `spec/workflow_card.md`: **4** (B8–B11).
- `spec/validate_page.md`: **3** (B12–B14).
- `spec/assignments.md`: **7** (B15–B21).
- `spec/setup_pages.md`: **9** (C1–C5, C9–C11, C16).
- `spec/quick_setup_card_spec.md`: 3 (C12, C14, C16).
- `spec/session_home.md`: 3 (C8, C12, C16).
- `spec/sessions_overview.md`: **4** (C6, C7, C14, C17).
- `spec/session_owners.md`: **2** (C13, E7).
- `spec/csv_contracts.md`: **8** (D1, D2, D7–D11, D22).
- `spec/extract_data.md`: **3** (D5, D6, D21).
- `spec/roundtrip_coverage.md`: **4** (D1, D14, D15, D20), plus A17's note on its :89.
- `spec/rehydrate.md`: **6** (D15–D19, D21).
- `spec/settings_inventory.md`: 4 (D3, D4, D20, D21).
- `spec/email_template_editor.md`: **4** (D12, D13, D21, D23).
- `spec/ui_elements.md`: **7** (E1, E2, E8, E12, E13, E15, E16).
- `spec/color_tokens.md`: 1 (E3). All 80 primitives, 103 semantic and 14 scale tokens and every ratio match.
- `spec/visual_style_general.md`: 2 (E13, E16).
- `spec/operator_ui_concept.md`: 2 (E11, E12).
- `spec/operator_button_audit.md`: **9** (E4–E10, E12, E13).
- `spec/architecture.md`: **5** (F1–F5).
- `spec/permissions.md`: **4** (F1, F8, F9, F11).
- `spec/audience_and_identity_model.md`: **2** (F1, F10).
- `spec/operations_pages.md`: 1 (F12).
- `spec/email_infra_options.md`: 1 (F13).
- `spec/README.md`: 3 (C15, F6, F7).
- `spec/rrw_functional_spec.md`: **26** (G1–G26).
- `docs/security_posture.md`: **5** (H1, H4, H5, H7, H8).
- `docs/database.md`: 2 (H2, H12).
- `docs/deployment_dev.md`: 1 (H3).
- `docs/known_limitations.md`: 3 (H4, H5, H10).
- `docs/architecture.md`: 1 (H6).
- `docs/local_setup.md`: 2 (H9, H12).
- `docs/deployment_nus.md`: 1 (H11).
- `docs/cli_setup.md`: 1 (H14).
- `rrw_sdd_in_practice.md`: **3** (I1, I6, I9).
- `new_project_practices_setup.md`: **3** (I2–I4).
- `rrw_design_rationale.md`: 1 (I5).
- `constitution.md`: 1 (I6).
- `CLAUDE.md` / `AGENTS.md`: 1 (I7).
- `README.md`: 1 (I8).

## 3. Consolidate

- `rrw_functional_spec.md`: rules stated twice within it (G19).
- `ui_elements.md`'s precedence line becomes a pointer to `visual_style_rrw.md`'s override table (E2).

## 4. Retire

- `operator_button_audit.md`'s retired rows kept "because other documents cite them"; nothing does (E10).
- `settings_inventory.md`'s `?rule_based_error` row, a parameter with no code (D4).

## 5. Move

- `email_infra_options.md`'s ship-state ticks and migration path to `guide/segment_14B_email_infrastructure.md`, if the author rules so (F13).

## 6. Read, no action

- `spec/role_landing_and_visibility.md`: the one file untouched since the last sweep; §1–§6 match.
- `spec/timezone_display.md`.
- `spec/visual_style_rrw.md`: matches `base.html`; E2 is `ui_elements.md`'s.
- `docs/README.md`, `docs/backup_restore.md`, `docs/nus_azure_status.md`, `docs/operations_runbook.md`, `docs/troubleshooting.md`, `docs/unenforced_conventions.md`.
- `CONTRIBUTING.md`; `azure_ask.md` (a dated record).

## 7. Not read

None. Read but **not verified**:

- Browser-only behavior: layout, hover and focus, the builder, data shaper,
  roster expanders and reviewer-surface scripts, and the 1px or 2px chip
  edge as drawn.
- Postgres-only behavior: the over-length 500s (D11) and unordered extract
  rows (D9) are inferred from the column types and the queries.
- Azure-side state, secrets, `gh` scopes and CI timings.
- Rehydrate end to end (gated off).

## Mechanical entry points

- **Staleness.** 1 of 58 files untouched since 2026-10-03
  (`spec/role_landing_and_visibility.md`); read, current.
- **Dropped commitments.** 535 of 550 live committed paths honored (97%);
  178 committed paths no longer exist, most of them files this window
  retired or folded, which plans committed to when they were live.
- **Orphan specs.** 13, from 17: the four retired or folded specs left the
  list. None surprised.
- **Dead references.** None in `spec/` or `docs/`.
- **App diff since 2026-10-03.** 79 files, +1,353 / −1,360, over 174
  commits.

## Headline numbers

| | |
|---|---|
| In scope | 58 (35 `spec/`, 14 `docs/`, 9 root) |
| Read | 58 |
| Findings | 156 (write 14 / update ~120 / consolidate 2 / retire 2 / move 1), about 25 of them trims |
| Code defects | 1 high, 14 medium, and low items, stale comments and dead CSS (register §1) |
| Rulings needed | 30 (register §2) |
| Carried in / closed / still open | 3 carried / — / 3 carried; old A5, G3, G17 re-reported as partly fixed |

**What this sweep says.** The third full read in five days found 156
findings against about 236 and 242 before it, on a corpus ten files
smaller. Fewer are provenance this time: the two earlier registers stripped
most of it. What remains is detail that drifted under the last week's
behavior changes, and a sharper set of defects than either earlier sweep
found. One is a privilege bug: any admin can create an admin through
Invite, past the super-admin rule that Promote enforces (F1). Two lose or
corrupt data on ordinary actions: the Instrument card's Save commits half
an edit before it refuses the other half (A16), and older visibility rows
make a card's Save fail and block a settings re-import (A17). Four were
reproduced in the data paths: a Settings export that does not round-trip
byte-stable, a phantom email override, silently dropped response rows, and
CSV text longer than its column. The weakest document is again the
functional spec, at 26 findings, most of them behavior the per-surface
specs have since changed.

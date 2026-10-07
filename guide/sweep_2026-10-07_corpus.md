# Sweep — corpus (2026-10-07)

**Swept:** 2026-10-07 at `ff7f4425` · **Scope:** `spec/` + `docs/` + root
practice docs (58 files) · **Previous sweep:**
`guide/archive/sweep_2026-10-05_corpus.md` · **Trigger:** asked for by the
author once the 2026-10-05 register was fully worked through; not due by
the cadence (2 of 56 days, 46 of 500 merges).

<!-- sweep-scope: corpus -->

**Read in full, all 58.** The corpus has the same 58 files as on
2026-10-05; 48 of them changed since, under the 2026-10-05 register's fixes
(#2828 → #2865). Nine `spec-writer` reads ran in verify mode, split by
area, each reading every file in its area against the code. None edited a
file. **This sweep changed no file in scope.** Every divergence is in
`guide/findings_2026-10-07_corpus.md` with who decides it; act from the
register. This record says what was read and what was found, file by file.

## 0. Carried forward

Every finding of the 2026-10-05 register is closed (archived beside this
record with nothing open); three were carried by name and stay so:

| Finding | From | Age | Now | Note |
|---|---|---|---|---|
| old B27 = old G6: scheduled sends fire only from Session Home | 2026-10-01 | 6 d | carried | `guide/post_azure_todo_checklist.md` §7; awaits Azure. Re-found as B3 and G4. |
| old D4: `responses_import._stage` overwrites duplicate rows | 2026-10-03 | 4 d | carried | Rehydrate, `guide/deferred_consolidated.md`. Re-found and reproduced as D1. |
| old D19: Rehydrate is incomplete | 2026-10-01 | 6 d | carried | Same entry. |

Two older findings were fixed only in part and are re-reported: old H14 as
H4, and old F13's ship ticks as F14. One re-found finding stays declined:
H8 is old H13.

## 1. Write or deepen

- `quick_setup_card_spec.md` / `session_home.md`: the archived state in the availability table (C1).
- `csv_contracts.md`: what a roster re-upload deletes (D3).
- `ui_elements.md`: the shared table-sort primitives (E9).
- `permissions.md`: the 401 with no identity headers (F9).
- `rrw_functional_spec.md`: the lobby expander's Code and Tags, Duplicate's names, the outbox statuses (G7, G8).

## 2. Update in place

Ids are in the register. A **bold** count means a medium-or-higher finding
is among them; *code* ids are defects where the file is right.

- `spec/instruments.md`: **4** (A1, A4, A6, G1).
- `spec/reviewer-surface.md`: 4 (A3, A5, A6, A8).
- `spec/visibility_policy.md`: 2 (A6, A7).
- `spec/role_landing_and_visibility.md`: 1 (A6).
- `spec/sort_by_reviewee.md`: code **A2**.
- `spec/lifecycle.md`: **5** (B1, B2, B4, B5, B8), plus carried B3.
- `spec/workflow_card.md`: 1 (B8).
- `spec/assignments.md`: 1 (B6).
- `spec/validate_page.md`: code B7.
- `spec/quick_setup_card_spec.md`: 2 (C1, C5).
- `spec/session_home.md`: 3 (C1–C3).
- `spec/sessions_overview.md`: 2 (C6, C7), plus code C4.
- `spec/setup_pages.md`: 1 (C7).
- `spec/rehydrate.md`: 3 (D2, D6, D8), plus carried D1.
- `spec/csv_contracts.md`: 4 (D3, D5, D7, D8).
- `spec/email_template_editor.md`: code D4.
- `spec/roundtrip_coverage.md`: 1 (D8).
- `spec/settings_inventory.md`: 3 (B5, D8, D9).
- `spec/ui_elements.md`: 8 (E1, E2, E4, E5, E8, E9, E12, E13), plus code E7.
- `spec/operator_button_audit.md`: 3 (E3, E9, E10).
- `spec/visual_style_rrw.md`: 1 (E5).
- `spec/color_tokens.md`: 1 (E6). All 80 primitives, 104 semantic and 14 scale tokens and every ratio match.
- `spec/operator_ui_concept.md`: 1 (E14).
- `spec/operations_pages.md`: **2** (F1, F2).
- `spec/architecture.md`: 4 (F3, F4, F11, F12).
- `spec/audience_and_identity_model.md`: 2 (F5, F6).
- `spec/permissions.md`: 4 (F7–F10).
- `spec/email_infra_options.md`: 2 (F13, F14).
- `spec/rrw_functional_spec.md`: **7** (G1–G3, G5–G8), plus carried G4.
- `docs/security_posture.md`: **2** (H2, H7).
- `docs/backup_restore.md`: **2** (H1, H6).
- `docs/operations_runbook.md`: **1** (H1).
- `docs/known_limitations.md`: 2 (H3, H5).
- `docs/cli_setup.md`: 1 (H4).
- `docs/architecture.md`: 1 (H6).
- `docs/deployment_nus.md`: 1 (H6).
- `docs/database.md`: 1 (H7).
- `docs/unenforced_conventions.md`: 1 (H7).
- `rrw_sdd_in_practice.md`: **4** (I1–I4).
- `README.md`: 2 (I5, I6).
- `rrw_design_rationale.md`: 1 (I7).
- `new_project_practices_setup.md`: 1 (I8).
- `azure_ask.md`: 1 (I10), a dated record.

## 3. Consolidate

- `sessions_overview.md`: Rehydrate's default and Go to Archive each stated two or three times (C6).

## 4. Retire

- `ui_elements.md`'s `.card.placeholder`, if the author rules it unused (E12).

## 5. Move

None.

## 6. Read, no action

- `spec/participant_model.md`, `spec/timezone_display.md`, `spec/extract_data.md`, `spec/session_owners.md`, `spec/visual_style_general.md`, `spec/README.md` (35 rows, current).
- `docs/README.md`, `docs/local_setup.md`, `docs/deployment_dev.md`, `docs/nus_azure_status.md`, `docs/troubleshooting.md`.
- `CLAUDE.md` / `AGENTS.md` (byte-identical), `CONTRIBUTING.md`, `constitution.md`.

## 7. Not read

None. Read but **not verified**:

- Browser-only behavior: layout, the builder's Name lock (G1) and the
  group preview (A4) as drawn.
- Azure-side state, secrets, `gh` scopes and CI timings.
- Rehydrate end to end (gated off); D1 was reproduced at the service.

## Mechanical entry points

- **Staleness.** 10 of 58 files have no commit since `2d7e5b5f`
  (`close_check.py --stale`, which compares dates, counts 3); all read.
- **Dropped commitments.** 535 of 550 live committed paths honored (97%);
  39 of 50 plans fully honored; 178 committed paths no longer exist.
  Unchanged since 2026-10-05: no plan closed in the window.
- **Orphan specs.** 13, the same cross-cutting set. None surprised.
- **Dead references.** None in `spec/` or `docs/`.
- **App diff since 2026-10-05.** 94 files, +2,200 / −1,198, over 39 merges
  and 121 commits.

## Headline numbers

| | |
|---|---|
| In scope | 58 (35 `spec/`, 14 `docs/`, 9 root) |
| Read | 58 |
| Findings | 86 (write 6 / update ~75 / consolidate 1 / retire 1), about 15 of them trims, 3 outside the corpus |
| Code defects | 1 high, 3 medium, 8 low, and stale copy and comments (register §1) |
| Rulings needed | 22 (register §2) |
| Carried in / closed / still open | 3 carried / — / 3 carried; old H14 and F13 re-reported as partly fixed |

**What this sweep says.** The fourth full read in seven days found 86
findings against 156 two days before, on the same 58 files, after every
row of that register was worked through. About 15 of the 86 are trims, and
several of those are provenance the last round of fixes wrote back in:
finding ids and ruling dates in the specs they changed. One defect is high, and the
sweep's read got it wrong: removing a user deletes every session they
created, whoever owns it now (H1), which the read had down as a
Postgres-only 500 until Codex's review of this PR traced the ORM cascade
and it was reproduced. Three are medium: a Details Save that refuses a
rename because the stored Start has passed (B4), an Instrument Save that
demotes a validated session with nothing changed (A2), and a per-row
reminder that writes no audit row (G3). The functional spec is no longer the
weakest document by count; `ui_elements.md` is, at nine, nearly all
detail drifted under the last week's visual fixes.

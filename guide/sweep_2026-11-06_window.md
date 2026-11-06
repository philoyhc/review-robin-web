# Sweep — the 14E / 14F / 22G–22I window (2026-11-06)

**Swept:** 2026-11-06 at `78118652` · **Scope:** the 40 files of `spec/`,
`docs/`, `cordware/spec/` and the root that changed since the 3 November
snapshot (`cc364ed0`) · **Previous sweep:** `guide/sweep_2026-10-22_corpus.md`
· **Trigger:** asked for by the author once the 2026-11-06 assessment's
register was retired; not due by the cadence (15 of 56 days, 315 of 500
merges).

<!-- sweep-scope: partial -->

Four `spec-writer` reads ran in verify mode, split by area; none edited a
file. **This sweep changed no file in scope.** Every divergence is a row
of `guide/findings_2026-11-06_sweep.md`. Coverage was a full read for
read B's five files and a read of each file's changes since `cc364ed0`
plus targeted checks for reads A, C and D; the prose they did not reach
is listed in §5.

## 0. Carried forward

The 2026-10-22 corpus sweep's register (`guide/archive/findings_2026-10-22_corpus.md`)
was archived with nothing open. Its three carried items stand as there:

| Finding | From | Age | Now | Note |
|---|---|---|---|---|
| old B27 = old G6: scheduled sends fire only from page loads | 2026-10-01 | 36 d | done | 14E's clock runs the pass (#3577 → #3583); sending on it waits on 14G. |
| old D4: `responses_import._stage` overwrites duplicate rows | 2026-10-03 | 34 d | carried | Rehydrate, `guide/deferred_consolidated.md`. |
| old D19: Rehydrate is incomplete | 2026-10-01 | 36 d | carried | Same entry. |

## 1. Write or deepen

- `docs/security_posture.md`: no word on the outbound mail surface (W1).

## 2. Update in place

- `rrw_design_rationale.md`: 1 (U4).
- `docs/known_limitations.md`: 1 (U5; outside the scope, met in passing).
- `docs/deployment.md`: 1 (U7).
- `spec/rrw_functional_spec.md`: 1 (U6).
- `spec/csv_contracts.md`: 3 (U1, U8, U9).
- `spec/architecture.md`: 1 (U3).
- `spec/ui_elements.md`: 1 (U2).
- `spec/visual_style_rrw.md`: 1 (U10).
- `spec/extract_data.md`: 1 (U11).

## 3. Consolidate

None.

## 4. Retire

None.

## 5. Read with no finding, and not read

- **No finding:** `spec/lifecycle.md`, `email_infra_options.md`,
  `email_template_editor.md`, `operations_pages.md`, `settings_inventory.md`,
  `workflow_card.md`, `session_home.md`, `sessions_overview.md`,
  `validate_page.md`, `visibility_policy.md`, `role_landing_and_visibility.md`,
  `setup_pages.md`, `instruments.md`, `assignments.md`, `operator_ui_concept.md`,
  `operator_button_audit.md`, `reviewer-surface.md`, `permissions.md`,
  `audience_and_identity_model.md`, `visual_style_general.md`, `spec/README.md`;
  `README.md`, `CLAUDE.md` / `AGENTS.md`, `CONTRIBUTING.md`, `docs/README.md`,
  `docs/database.md`, `docs/local_setup.md`, `rrw_sdd_in_practice.md`,
  `cordware/spec/host.md`, `cordware/spec/identity.md`.
- **Checked and not findings:** `rrw_sdd_in_practice.md`'s 8,451 tests
  (passed) and 8,463 (collected) agree, the 12 skips between them; its 173
  `EVENT_SCHEMAS` types at `c912ae53` are right (the dict's keys, parsed).
  `spec/csv_contracts.md`'s one legitimate schedule-chain failure (closed
  before End, then released) still occurs: Close session needs only `ready`.
- **Not reached:** the unchanged prose of the long files reads A, C and D
  spot-checked (the functional spec, `security_posture.md`,
  `local_setup.md`, `identity.md`, `architecture.md`); `spec/extract_data.md`
  from line 1084 (the group-scoped tag aggregates); client-only behavior
  (expanders, `beforeunload`, branching scripts). The next corpus sweep
  reads them.

## 6. Entry-point commands

- Staleness: `python3 tools/close_check.py --stale` (not due).
- The window: `git diff --stat cc364ed0..78118652 -- spec docs cordware/spec '*.md'`.

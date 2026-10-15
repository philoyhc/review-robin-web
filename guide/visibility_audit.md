# Visibility audit

**Opened:** 2026-10-15 · **Theme:** the database refuses an illegal
visibility cell, so nothing is left for a card to audit · **Related:**
`spec/visibility_policy.md`, `spec/operator_ui_concept.md`

A standalone plan at the author's naming, in the shape of
`guide/import_error_reporting.md`: one item, with its own
`### Doc impact` and `### Status`, checked by hand at close
(`tools/close_check.py` reads only `segment_*` files).

---

## Item 1 — Enforce the per-cell rule in the database; retire the audit card

### Opportunity

Sessions Diagnostics carries a read-only **Visibility grid audit** card
(19C Item 10): every stored `instrument_view_policies` cell whose mode
its `(audience, window)` pair does not allow. The author asked why it
sits there (2026-10-15). Nothing else on the page concerns visibility,
and the card is there only because the check spans every session. Its
first paragraph is reasoning, not operating guidance. And the list is
empty by construction: the Band 3 editor and the Settings import both
refuse an illegal cell, and migration `14db60023e88` normalized the
cells written before those guards. The card checks after the fact for a
write that something cheaper could have refused.

### Decision

A `CHECK` constraint on `instrument_view_policies` encodes the per-cell
rule (`spec/visibility_policy.md` §3.1), so any write path, present or
future, is refused at the database. With that in place the card can
only ever read empty, so it retires: the template card, its view module,
the route's context key and its test file. Its reasoning moves into
`spec/visibility_policy.md`.

Rejected: **a Sys Admin tab of its own**, which gives the card an honest
home but leaves a whole tab for a normally empty list, and still only
detects. Rejected: **a flag on the instrument's own visibility card**,
which shows the owner a bad cell where they would fix it but drops the
workspace-wide view and still only detects. Only the constraint
prevents.

### Semantics

- **What it allows**, per row: `audience` is one of `peer_reviewer`,
  `reviewee`, `observer`. Each window's `(granularity, identification)`
  pair is both NULL (off) or one of `(row, identified)` = Raw,
  `(row, deidentified)` = Anonymized, `(aggregated, deidentified)` =
  Summarized. Half-set pairs, `(aggregated, identified)` and unknown
  values are refused. On top of that, each cell is limited to the modes
  `_PER_CELL_VALID_MODES` allows: the reviewer's ongoing cell is Raw
  only; the reviewer's released cell is off or Raw; the reviewee's
  ongoing cell is off only; the observer's ongoing cell is off or
  Summarized; the released cells of the reviewee and the observer take
  any of the three modes, or off.
- **A missing row** is untouched: the constraint governs stored rows,
  and the resolver's missing-row rule (§4) is unchanged.
- **A refused write** surfaces as an `IntegrityError` (a 500). Every
  writer validates first (`upsert_policy`, the Settings import,
  Duplicate and Replicate through `upsert_policy`), so a refusal means a
  new path skipped the validator. A loud failure is the right signal,
  and it is the case the card existed to catch.
- **Existing rows.** The upgrade first re-applies `14db60023e88`'s
  normalization, under the same ruling (2026-10-05: nearest legal cell,
  never wider than what the row granted in effect), and logs how many
  rows it rewrote. The constraint therefore cannot fail to apply on a
  stray row, and the log line answers what the card was going to be
  read for on real data.

### Judgment calls — decided

- The rule lives twice, in `_PER_CELL_VALID_MODES` and in SQL. A test
  inserts every combination of audience × pair × pair and asserts that
  the database accepts exactly what the Python rule accepts, so the two
  cannot drift without a red test.
- One named constraint, `ck_view_policy_cell`, not one per window: a
  refused write names the rule, and the downgrade drops one name.
- `after_release_reviewer_identity` is not constrained here. The card
  never audited it; see Out of scope.
- A row with an unknown audience stops the upgrade with its ids rather
  than being deleted: nothing reads it, but deleting data is not the
  migration's call (2026-10-15).

### Blast radius (measured)

Taken 2026-10-15 at `3070350c`.

- Card code: 4 app files (`grep -rln 'visibility_audit\|VisibilityAuditRow' app`):
  `_sys_admin.py`, `views/__init__.py`, `views/_visibility_audit.py`
  (204 lines), `sys_admin_sessions.html`.
- Tests: `tests/integration/test_sys_admin_visibility_audit_card.py` <!-- path-ref-ok -->
  (301 lines), the only test that names the card.
- Prose naming the card (`grep -rln -i 'visibility grid audit\|visibility_audit' spec docs guide/*.md`):
  `spec/operator_ui_concept.md`, `spec/rrw_functional_spec.md`,
  `spec/operator_button_audit.md`, `spec/permissions.md`,
  `spec/ui_elements.md`, `guide/post_azure_todo_checklist.md` (item 1).
- Writers of the table: `visibility_policies.upsert_policy`; the
  Settings import and Duplicate / Replicate call it. No raw SQL writes
  it outside migrations.

### Status

Build, 2026-10-15:

- **Rungs 2 and 3 landed as one PR.** The card's tests seed the illegal
  rows it reports, which the constraint now refuses, so the constraint
  cannot land with the card still standing. The author accepted the
  single PR (2026-10-15).
- **Tests that seeded an illegal row moved to a legal one.** The
  observer-collation tests (and those reusing their seed helper, in
  `test_reviewer_identity_level.py` and `test_profile_value_render.py`)
  stored an observer `raw` / `anonymized` grant on `while_ongoing`. They
  now put the per-row mode on `after_release` with the release window
  open, the one way the product allows it. Two tests that pinned
  behavior for such a row (a legacy reviewee ongoing grant, Replicate
  skipping an illegal cell) were retired, since the row can no longer
  exist.
- The migration logs the rewritten rows' ids as well as their count, so
  `guide/post_azure_todo_checklist.md` item 1 can name whom to tell.
- **Reads.** Two `diff-reviewer` reads. The read of the build commit found one
  real defect: the observer CSV's archive-guard test had gone vacuous
  once its seed moved to `after_release`. That test now relaxes the
  release-window predicate. The read also asked for a test of the
  migration's log line, which is now asserted, and for prose that
  still called an illegal stored row reachable, now reworded.
  `spec-writer` found §4 claiming that a reviewer row with both windows
  off persists, which the constraint refuses; that line is now
  scoped. The second read, of those fixes, found the same claim in
  `_reviewee_results.py` and `spec/role_landing_and_visibility.md`,
  and that §3.1 had dropped what the card checked. A third read found
  the same idea in §3.1's import paragraph and in
  `spec/settings_inventory.md` §4. All of these are fixed.

### PR ladder

1. **This plan** (prose only).
2. **The constraint.** A migration that re-normalizes and then adds
   `ck_view_policy_cell` (batch mode on SQLite, both directions on
   Postgres); the model's `__table_args__`; the exhaustive agreement
   test; `spec/visibility_policy.md` §3.1 says the database enforces the
   rule. Must not touch the card.
3. **Retire the card.** Remove it from `sys_admin_sessions.html`, drop
   `views/_visibility_audit.py`, the route's `visibility_audit_rows` and
   the card's test file; move the card's reasoning into
   `spec/visibility_policy.md` §3.1; update every spec that names the card;
   rewrite `guide/post_azure_todo_checklist.md` item 1 around the
   migration's log line; add the browser check.

### Definition of done

- `alembic upgrade head` and the `downgrade base + upgrade head`
  round-trip pass on Postgres (`ci-postgres`).
- The agreement test covers every audience × pair × pair combination.
- `grep -rn -i --exclude-dir=archive --include='*.py' --include='*.html' --include='*.md' 'visibility grid audit\|visibility_audit\|VisibilityAuditRow' app tests spec docs | grep -v 'guide/visibility_audit\.md'` finds nothing. The filter drops citations of this plan, from the model and the test, which are not the card.
- `spec/visibility_policy.md` names `ck_view_policy_cell` and carries
  what the card's paragraph said.
- `### Doc impact` current; `spec-writer` flags adjudicated.
- `### Status` compacted; the item recorded in `guide/README.md`.

### Open questions

None.

### Out of scope

- **Constraining `after_release_reviewer_identity`** (level, and only
  on the reviewee and observer rows). It is validated on write the same
  way, and could take the same treatment in a later item if wanted.
- **The resolver's tolerance of a corrupt row** (`decode_pair_to_mode`
  reads one as off). It becomes unreachable but stays, as cheap defense.

### Doc impact

- `spec/visibility_policy.md` — §3.1: the database enforces the per-cell rule (`ck_view_policy_cell`), and what the retired card checked and why it is no longer needed (Item 1).
- `spec/operator_ui_concept.md` — Sessions Diagnostics drops the audit card (Item 1).
- `spec/rrw_functional_spec.md` — the Sys Admin pages drop the audit card (Item 1).
- `spec/operator_button_audit.md` — the card note under Sessions Diagnostics goes (Item 1).
- `spec/permissions.md` — the `/operator/sys-admin/*` row drops the card (Item 1).
- `spec/ui_elements.md` — the role-pill row drops the card as a renderer (Item 1).
- `guide/post_azure_todo_checklist.md` — item 1 reads the migration's log line instead of the card (Item 1).
- `guide/things_to_check_in_browser.md` — Sessions Diagnostics no longer shows the card (Item 1).

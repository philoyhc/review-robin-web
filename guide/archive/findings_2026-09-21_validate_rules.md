# Findings — the validation rule registry, 2026-09-21

Two discrepancies the `spec-writer` pass at **19R Item 5's close**
surfaced and did **not** act on. Neither is that item's doing: one
predates it by several segments, the other by a wave. They are here
rather than fixed because `rrw_sdd_in_practice.md` §4 makes `spec/`
the contract, so a pass that finds spec and code disagreeing may not
quietly rewrite the spec to match — each is a choice between *fix the
code* and *change the contract deliberately*, and that is the author's
call.

The item's own spec debt is not here: `spec/validate_page.md` §3.1 /
§5.1 / §7 and `spec/workflow_card.md`'s signature listing were all
edited at that close.

| # | Kind | Where | What | What deciding it involves |
|---|---|---|---|---|
| 1 | spec-internal | `spec/validate_page.md` §3.2 | The registered-rules table lists `reviewees.unreachable_for_results` last, 22nd of 22. In `REGISTERED_RULES` it is 7th, right after `reviewees.duplicate_id`. Registration order **is** a contract — §2.4 makes source order within a gate follow it, and `tests/integration/test_validation_issue_parity.py`'s golden is keyed on it — so the table no longer matches the thing it documents. Predates 19R; the rule landed in W8. | Reorder the table row, or state in §3.2 that the table is not declaration-order. Cheap either way; the question is only which the table is *for*. |
| 2 | spec-vs-code | `spec/instruments.md` (the Validate-rules paragraph) | It says `instruments.stale_generated` "raises no findings; it is inert by design". That is `instruments.no_rule_pinned`, which returns before yielding (`app/services/validation.py`). `_check_instruments_stale_generated` is an active check and has emitted real warnings since **19N** — its own docstring narrates the Wave 5 PR 5.1 → 19N window when it *was* a no-op, which is the state this prose still describes as current. | Correct the prose to name the inert rule, and say the staleness check is live. No code question — the code is right and the spec is stale — but it is `spec/instruments.md`'s owner's edit, not a close's. |

**Both rows actioned 2026-09-21 by 19R Item 6**, which is why this
file is archived rather than live. Row 1's table row moved to registry
position 7; row 2's bullet was replaced with the live check's
behavior. The item also records the option neither row took — a test
deriving §3.2's key column from `REGISTERED_RULES` — so it is not lost
with this file.

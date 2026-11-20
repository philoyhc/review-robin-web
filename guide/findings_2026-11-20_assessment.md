# Findings — codebase assessment (2026-11-20)

**Found by:** the defect read and the package read of
`guide/codebase_assessment_20nov.md` · **Read at:** `6003c8084` (#4063) ·
**Open:** all rows.

RRW's defects and notes from the assessment's reads; the fix checklist, struck
by the PR that fixes each row, or marked declined with the reason. Spec drift is
in the sibling register `guide/findings_2026-11-20_corpus.md`, which also holds
the author decisions the snapshot's §8 names (B4, B6, E1, E2, E3). The packages'
defects are in each package's own register: `applydesk/guide/findings_2026-11-20.md`,
`residentialapps/guide/findings_2026-11-20.md` and
`utilityapps/guide/findings_2026-11-20.md`.
CONFIRMED means reproduced by a scratch test; *by trace*, read through without
one. Line numbers are at `6003c8084`.

## Defects

- **D1** (medium, code, CONFIRMED) — **the lobby's Due pill lights on a linked
  session whose card shows nothing due.**
  - `sessions_with_something_due` (`app/services/due_actions.py:192-199`) and
    `due_actions` (`:84-114`) do not check `Lock.EMAIL`; `build_due_lines`
    (`app/web/views/_workflow_card.py:252-256`) does. `lobby_due_session_ids`
    (`app/web/views/_sessions_table.py:193-199`) lights the pill.
  - A handoff create may carry `session.scheduled_activate_at` and the offsets
    (`session_linked_errors` refuses only release and observers rows). Once an
    offset passes, the pill lights and cannot be cleared: details answer 409, a
    re-send 422 `not_owned`.
  - Scratch test: card due lines `[]`, lobby due ids `{1}`. Introduced by 14F's
    due prompts (#3668) with 23F's email lock (#3925, #3934). Contradicts
    `spec/linked_sessions.md` §`email`. Same defect as the corpus register's B1.
  - Fix: skip `Lock.EMAIL` sessions in `due_actions`. **For the author:** may a
    linked create carry offsets at all?
- **B2, B3** (low): in the corpus register, found by the sweep's narrative read
  of `spec/lifecycle.md` and `spec/workflow_card.md`; listed there.

## Notes, not defects

- **N1** — the lobby runs `due_actions` once per listed session, and that runs
  `monitoring.per_reviewer_progress` when an entry is due: N+1 work, a
  performance note only.
- **N2** — a re-send that moves Start or End does not recheck existing invite or
  reminder offsets against the new anchor.
- **N3** — CI's `test (unit)` shard carries every package suite and now takes
  2m24 (43 s on 2026-11-06); the Postgres shards are uneven again, integration-a
  3m11 against integration-b 1m57.

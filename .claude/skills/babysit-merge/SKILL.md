---
name: "babysit-merge"
description: Work through a batch of pre-planned PRs end to end — push, clear CI, repo checks and Codex review, then merge each one — stopping only for rulings. Use when the user says "keep going, merge each PR when it passes", "babysit and merge", or hands over a sweep of small fixes or a fully planned segment item.
---

# Babysit and merge

Use this for work that is already decided: a batch of low-intensity fixes from a sweep, or a segment item whose plan (`guide/segment_*.md`, per `segment-plan`) is complete. The user has delegated merging. They have NOT delegated design decisions, the segment close, or final sign-off — that comes after their browser checks.

`CLAUDE.md` ("Where work runs") and `CONTRIBUTING.md` ("When to wait for CI") are the authority for the gates below. If they have changed since this skill was written, they win.

## The batch

1. Establish the queue before starting: the list of PRs (existing numbers, or planned rungs/items to turn into PRs) in order. Write it as a task list so progress is visible.
2. For an item ladder, note which rung you expect to be the item's **last build rung** — it carries the cumulative `diff-reviewer` read. Record the `main` SHA before rung 1 merges in rung 1's PR body, so the last rung can cite it.
3. Work one PR at a time. Do not open the next PR's branch until the current one is merged or parked.
4. Branch each new PR from up-to-date `main` (`git fetch && git switch main && git pull`), so every PR is tested against what is really there. For a PR that already exists, check out its branch (`gh pr checkout <n>`) before classifying it or running any gate, so the local checks run on the PR's head and not on `main`; then `git fetch origin main` (checkout fetches only the PR head) and, if that head is behind `origin/main`, merge `origin/main` into it and push first — a merge commit, never a rebase or force-push on a branch you did not create — so both the local checks and CI test the tree that will land.
5. Open each new PR as a **draft** (`gh pr create --draft`). Codex review is triggered by marking it ready, so it must not start ready.

## Classify each PR

Before the loop, classify the PR from its diff (`git diff --name-only main...HEAD`). The class decides which gates apply.

- **Prose-only** — touches nothing under `app/`, `tests/` or `alembic/` (plan opens, rung closes, `Status` compaction, `guide/todo_master.md`, README rows, registers, spec sweeps). No `diff-reviewer` read.
- **Code, inside an item ladder** — `diff-reviewer` only on the item's last build rung, on the cumulative diff `git diff <base SHA>..HEAD`. If a later rung reopens `app/` or `tests/` after that read, that rung takes its own read.
- **Code, outside any ladder** (one-off fix, CI repair, scaffold — most sweep fixes) — `diff-reviewer` on its own diff.
- **Database-reaching** — touches `alembic/`, `app/db/`, or any service that issues queries. Must wait for `CI - Postgres`; see Merge.

## Per-PR loop

For each PR, repeat until it passes all gates or hits a stop condition.

**Stage 1 — CI and repo checks, concurrently.** Pushing starts CI (`CI` and `CI - Postgres`). While it runs, run the repo checks in the session container instead of waiting idle:
- `pytest -n auto` and `ruff check .`, with `node` present. **Read the skip list, not just the exit code** — `tests/integration/test_inline_scripts_parse.py` skips silently without `node`. A lint-only pass is not evidence: the doc-convention tests (`test_doc_references.py`, `test_index_currency.py` and the rest) only run under `pytest`.
- `diff-reviewer`, if this PR's class calls for it (see above). It reports; you decide. Act on findings in this PR.
- `spec-writer`, as a verification pass, when the PR touches `spec/`, touches a path its plan's `Doc impact` names, or is the closing slice (`CLAUDE.md` "Where work runs"). Outside a close it reports divergence and does not re-align; act on its flags in this PR.
- If the suite could not run at all, say so in the PR body and name what did run.

Then `gh pr checks <n> --watch`.
- CI failure → read the failing job log (`gh run view <run-id> --log-failed`), reproduce locally, fix.
- Repo-check, `diff-reviewer` or `spec-writer` finding → fix (or, for a reader finding you judge wrong, note why in the PR body).
Batch fixes from all of these into one push where possible, then repeat Stage 1.

**Stage 2 — mark ready.** Only when BOTH CI is green on the head commit AND the repo checks (including any required `diff-reviewer` read and `spec-writer` pass) have passed on that same commit, mark the PR ready: `gh pr ready <n>`. This triggers the Codex review, so it must see the commit that is actually a merge candidate. If anything is still running or has findings outstanding, stay in Stage 1. If the PR is already ready (an existing PR, or one step 4 just updated), `gh pr ready` cannot re-trigger Codex: post a PR comment `@codex review` instead whenever the latest Codex review is not on the head.

**Stage 3 — Codex review.** Wait for a review **on the current head commit** — a review of an earlier commit does not count. Triage every comment:
- Real defect within this PR's scope → fix, push, reply on the thread with the commit SHA.
- False positive, or out of scope → reply with a one-line reason; change nothing. Note out-of-scope items for the hand-off report.
- Needs a judgment call → STOP (see below).

**Codex stalls** (author's ruling, 2026-10-23). Codex sometimes shows "running" on the head and never reports. Time both marks from the trigger (the PR marked ready, or the `@codex review` posted after a push); the 15-minute re-ping does not restart the clock:
- **15 minutes** with no review on the head → post one PR comment `@codex review`, saying the review stalled.
- **30 minutes** still silent → a **prose-only** PR merges on green CI with the other gates held; say in the PR body and the hand-off report that Codex did not review the head. Any **other** class → STOP and ask for a ruling.
- An explicit instruction from the user ("merge as soon as CI is green") skips the Codex wait for that PR; every other gate still holds.

**After any fix pushed while the PR is ready:** the PR stays ready. Re-run Stage 1 on the new head (the `pytest`/`ruff` gates are owed on every push). Once CI is green again, check whether Codex has reviewed the new head; if not, post a PR comment `@codex review` to request it. Do not toggle the PR back to draft and ready again to force a review.

**Merge.** `main` has no branch protection by design — the gate is this checklist. Merge only when all hold on the head commit:
- `CI` green.
- `CI - Postgres` green — **required** for database-reaching PRs. Every merge to `main` deploys and runs `alembic upgrade head` against Azure Postgres without waiting on CI, so a Postgres-only failure that lands is found in production. For prose-only and `tools/`-only PRs, merging ahead of a still-running `CI - Postgres` is allowed by `CONTRIBUTING.md`; never merge on a red one.
- Repo checks pass; any required `diff-reviewer` read and `spec-writer` pass done and acted on.
- The latest Codex review is on the head commit and has no unaddressed actionable comments — or, for a prose-only PR, Codex stalled past the 30 minutes above.

Then `gh pr merge <n> --squash --delete-branch --match-head-commit <sha>` (or the repo's established merge method if different), where `<sha>` is the head commit the checklist above passed on. If the head has moved, the merge is refused: restart the gates on the new head. Then pull `main` and move to the next PR.

## Stop and ask for a ruling when

- A Codex comment, `diff-reviewer` finding or failure raises a design, spec or behaviour question rather than a bug.
- The fix would touch migrations, auth, deployment/infra config, a spec contract, or public interfaces beyond what the plan covered.
- The only way to get green is to skip, delete, loosen or `xfail` a test.
- A PR has gone 5 fix rounds without clearing, or a check is flaky (fails, then passes with no change — say so rather than re-running silently).
- The plan turns out to be wrong or incomplete for what the code actually needs.

When stopping: park that PR (leave it open), say exactly what the ruling is with the options, and wait. Do not skip ahead to later PRs unless the user says to.

## Never

- Force-push to `main`, or merge with any check red.
- Merge a database-reaching PR before `CI - Postgres` is green.
- Merge a PR whose Codex review is stale (older than the head commit), except a prose-only PR under the stall rule in Stage 3.
- Widen a fix beyond its comment — no opportunistic refactors mid-batch (`CLAUDE.md` forbids bundling).
- Claim browser or end-to-end verification. That is the author's; when a PR touches UI or anything the suite can't exercise, say so in the PR body.

## Finishing — do not close out

Merging is delegated; the close is not. When the queue is empty:
- Do NOT run the `segment-plan` close (no `tools/close_check.py`, no closing `spec-writer` pass, no `Status`/`Doc impact` close edits), close the tracking issue, or declare the work complete.
- Post a hand-off report:
  - each PR: number, title, class, merged SHA, fix rounds taken
  - `diff-reviewer` reads: how many, on which PRs, and what they turned up (the item's `Status` block needs this at close)
  - Codex comments declined, with the reason; PRs merged under the stall rule
  - out-of-scope items noted for later
  - parked PRs and the ruling each needs
  - **browser checklist**: the pages, flows and roles to exercise at `http://127.0.0.1:8000/reviewrobin/`, derived from what the merged PRs touched
- Then wait for the user's browser checks. Fix anything they find as a new PR through the same loop. Run the close only when they say so.

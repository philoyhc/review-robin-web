# Segment AD4A — The User Lobby is the signed-in person's

**Opened:** 2026-11-28 · **Theme:** `/me` shows the signed-in person's own applications and the exercises open to them · **Related:** `applydesk/guide/ad4_series.md`, rulings 41, 46 and 84 (`applydesk/guide/todo_master.md`), `applydesk/spec/applications.md` ("The lobbies and the applicant's application")

## Opportunity

- **`/me` shows a fixed sample person.** *My applications* is `sample_data.MINE`, two fixed application IDs, whoever signs in. *Open to me* lists every Published or Closed exercise, whoever may apply. *You are invited* reads a retired label (`"Invitation only"`), which nothing sets since AD2I.
- **Another applicant's application opens for anyone.** `/me/exercises/<id>/applications/<id>` answers for any application ID. The page only hides the results of an application that isn't in `MINE`.
- **The Form's *Who may apply*** (AD2I) is saved, but nothing on the applicant's side reads it.

## Decision

- **The viewer is the signed-in person** (`people.resolve`), and every `/me` page reads their own records.
  - *My applications*: their applications from the store, in every live exercise, drafts included.
  - An application page answers only its own applicant. Anyone else gets a 404.
- ***Open to me*** lists each Published or Closed exercise whose Form admits the viewer, read by one service, `applydesk/eligibility.py`:
  - **Anyone signed in:** every signed-in person.
  - **Invitees:** a person on the invite list, matched by their person row.
  - **Dossiers:** a person holding a live *Create dossiers* entry.

  The chip says why: *You are invited* or *A dossier is held for you*. An exercise with no form, or a form not yet open, is still listed with its state, as now.
- ***Dossiers I am asked to evaluate*** shows nothing until AD5 pairs evaluators with dossiers. It no longer shows `MY_REVIEWS`.
- **The gate stays:** `/me` still answers only on a local run or for the super-admin (`gate.placeholders_only`). AD4C opens it to everyone, once there is something to submit.

**Rejected:**
- **Opening `/me` to every signed-in person now.** With no submit, it would only show people pages they cannot use.
- **Matching invitees by address on read.** A person row is what the invite list and the entries hold (ruling 73), so the match is by person row.

## Semantics

- **An unbound viewer** (someone signed in who has no person row yet) gets one from `people.resolve`, as the operator pages do. They then see what any newcomer sees.
- **The super-admin** sees their own applications, like anyone else. Seeing every applicant's is the operator pages' job.
- **A sample exercise's applications** are the seed's people. A local run's fake identity owns none unless a test or the seed gives it one.
- **A removed invitee** or **a retired entry** no longer admits the person. The person's existing applications still show.

## Judgment calls — decided

- **Eligibility is one function**, `eligibility.may_apply(session, exercise, person)`, which AD4C's submit will call too (2026-11-28).

## Blast radius (measured)

Taken 2026-11-28 at `c14ac325b`.

| What | Count | Command |
|---|---|---|
| Readers of the sample applicant | 8 lines | `grep -rn "MINE\b\|my_applications\|MY_REVIEWS" applydesk --include=*.py --include=*.html \| grep -v tests` |
| `/me` routes | 4 | `grep -n "@router.get" applydesk/routes_me.py` |
| `/me` templates | 4 | `ls applydesk/templates/applydesk/me/` |
| Test files naming `/me` | 28 | `grep -rln "/me\b\|/me/" applydesk/tests` |

## Status

**Closed 2026-11-28** (#4271 plan, #4272, #4273, #4274, and this close). Intended versus done:

- **The ladder held** (rungs 2–4). Rung 4 also took the fixes from the cumulative read, and rung 3 took two Codex findings before it merged.
- **The logic is in `applydesk/participant.py`,** a module the plan did not name: `signed_in`, `my_applications`, `owns`, `open_to`, `archived_ids`, `on_me`, `lobby` and `may_see`. The route only calls it.
- **Decisions confirmed at build:**
  - *Completed* shows on `/me`. It is the status an exercise made with *New exercise* reaches when every stage has completed; it stays, as Closed does (`participant.ON_ME`).
  - An exercise made with *New exercise* shows by its status as its stages give it (`locks.exercise_status`). Its stored state stays Draft.
  - Archiving is read from the row (`archived_at`) for every exercise.
  - *Applications open* reads the stored form state (`workflow.form_state`), not the placeholder flag.
  - The exercise page answers only someone admitted or with an application there.
- **Reads:** one cumulative `diff-reviewer` read at rung 4 (base `e858ac262`), 13 findings, all acted on:
  - an archived ordinary exercise was shown;
  - the viewer was resolved twice;
  - stages were read before eligibility;
  - *Completed* was unexplained;
  - the form flag was read as a constant;
  - the exercise page lacked an eligibility check;
  - a rule lived in the route;
  - a duplicated Create dossiers check;
  - a test helper's identity;
  - seven missing tests;
  - the spec rows (at close).

  Codex found two on #4273, both also in the read: the form state and the archived exercise.
- **Left as is:**
  - `sample_data.MINE`, `MY_REVIEWS` and `my_applications` stay as test fixtures only; no page reads them. They go when the samples are retired.
  - The `/me` dossier page is not gated per person (AD5 pairs evaluators with dossiers).

## PR ladder

1. **Plan** (this file), and the series file. Prose only.
2. **Eligibility.** `applydesk/eligibility.py` with `may_apply`, plus tests for each *Who may apply*. Must not touch: any page.
3. **The User Lobby reads the viewer.** *My applications* and *Open to me* come from the store and eligibility. *Dossiers I am asked to evaluate* is empty. `MINE` and `MY_REVIEWS` are gone from `/me`.
4. **An application page answers its own applicant only.** Its results show for the applicant, read from the store.
   - **Last build rung:** `diff-reviewer` on the cumulative diff from rung 2's base.
5. **Close:** `spec-writer` on `applydesk/spec/`; Status compacted; the plan archived.

## Definition of done

- A person sees their own applications and no one else's, and another's application page is a 404 (tests).
- *Open to me* follows each *Who may apply* (tests).
- `grep -rn "MINE\b\|MY_REVIEWS" applydesk/routes_me.py applydesk/templates/applydesk/me` finds nothing.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD4A` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- None open.

## Out of scope

- *Save draft* and *Submit* (AD4C). *Withdraw* (AD4D).
- Opening `/me` to every signed-in person (AD4C).
- The evaluator's card (AD5).

## Doc impact

- `applydesk/spec/applications.md` — the User Lobby and the applicant's application, read from the signed-in person.
- `applydesk/spec/permissions.md` — who reaches an application page.
- `applydesk/spec/architecture.md` — `applydesk/eligibility.py` in the module map.
- `applydesk/guide/ad4_series.md` — the AD4A row (at plan and close).

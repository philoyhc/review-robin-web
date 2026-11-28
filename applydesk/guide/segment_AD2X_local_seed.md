# Segment AD2X — Local test data, built for browser checks

**Opened:** 2026-11-28 · **Theme:** the localhost seed becomes a small set of exercises built through the app's own services, for the author's browser checks; the samples stay as test fixtures · **Related:** `applydesk/guide/ad2_series.md`, ruling 74 (`applydesk/guide/todo_master.md`), `applydesk/seed.py`

## Opportunity

- **The localhost seed loads the test fixtures.** `python -m applydesk.seed` loads every sample exercise (`sample_data.EXERCISES`). They were written for tests and for the AD1 simulation, not for checking a new capability in a browser. None of them has an open form with filled-in applications made the way the app makes them.
- **The directory is derived from the samples.** On localhost, `directory._local_users` builds the people search from the sample panels, applicants and assessors. Retiring a sample silently shrinks the directory.
- **Seeing the app as someone else means editing `.env`** and restarting. Local Operator is the Owner, the super-admin and (in this plan) an applicant and a panel member. So an ordinary applicant's view, or another person's 404, cannot be checked without editing `.env` and restarting.

## Decision

- **Two seeds.**
  - **The localhost seed** (`python -m applydesk.seed`) builds the scenario exercises below. It goes through the services the pages call (`exercises.make`, Process's and Form's saves, publishing, the form's state, `candidates`, `panels_store`, `applications`), so the audit trail looks real and the seed breaks visibly when behavior changes.
  - **The test seed** (`seed.seed()`, used by `applydesk/tests/conftest.py`) keeps loading the samples for the tests that need them.

  New capabilities add a scenario as they land.
- **The local directory is a fixed list** in its own module: the names and addresses of the RA exercise's panels (the 30 current RAs, the offices, the residential staff), written out as data and not derived from `sample_data`. Cordware's fake accounts stay first.
- **Scenario 1 — an open application form.**
  - The Form's stage is published and open. Its window starts when the seed runs and closes 30 days later.
  - The Form covers short text, long text, a choice and *Select people* from a panel. *Who may apply* is anyone signed in.
  - Six directory people have applied: four submitted, two drafts, all with answers.
  - Local Operator has not applied. Submitting through the page is AD4C's.
- **Scenario 2 — Create dossiers.**
  - A *Create dossiers* stage only, with two dossiers per person.
  - Five people (name and email), Local Operator among them, each with two dossiers, ten in all, each with a title.
  - The Dossiers page is populated. The author adds the Form by hand.
- **Panels.** Each scenario exercise gets its own two panels (panels are per exercise), drawn from the directory, with Local Operator on one of them.
- **Two identities on localhost.** Cordware's account menu offers *Switch to …* between Local Operator and a second fake account, a plain applicant who applied in Scenario 1 and does not operate. The choice lives in a cookie. It is honored only with `ALLOW_FAKE_AUTH` on and `APP_ENV=local`, the same guard as fake auth. Like fake auth, it serves the whole host, Review Robin included.

**Rejected:**
- **Deleting `sample_data.py` now.** 163 test files name the samples. Retiring them is its own work, done as features read stored data.
- **Keeping the samples on localhost beside the scenarios.** The author asked for a clean, growing set.
- **Seeding by writing rows directly.** It is faster, but it would drift from what the pages do and skip the audit trail.
- **Switching identity by `.env` and a restart.** Too slow for a check that flips views back and forth.

## Semantics

- **Re-running** changes nothing. A scenario is found by its name among the exercises the seed's Owner created, and skipped. A half-built one is refused, pointing at `--reset`, which empties the database first, as now. `--blank N` keeps its meaning. `--owner` goes with `--samples` only, because the scenarios are built as Local Operator.
- **Dates** are set from the run, so re-seeding after a month needs `--reset` to reopen the form. The seed's output says when the window closes.
- **The second identity** is bound like any sign-in (`people.resolve`) the first time it is used. It is never super-admin and never on the operator allowlist. Switching back restores Local Operator. Outside local, the cookie is ignored and the menu item is absent.
- **A directory person** who is seeded as an applicant, panel member or dossier holder becomes a person on record. The rest stay directory-only until someone adds them.
- **Refusals:** the seed still refuses to run outside `APP_ENV=local` (ruling 74).

## Judgment calls — decided

- **The second identity is a plain applicant**, not a second operator, because the views most worth checking are the applicant's and the outsider's (2026-11-28).
- **The identity switcher lands wired, in one rung.** It is a localhost-only development affordance, not a product page, so the scaffold-first rule's purpose (iterating a page's shape) does not apply (2026-11-28).

- **The scenarios post what the pages post** to Apply Desk's own routes, in process, as Local Operator (`applydesk/local_seed.py`), rather than calling each service. The route's transaction is the page's, so the seed cannot drift from it. The cost is that the seed needs fake auth on, which a local run has (2026-11-28, rung 4).
- **Answers are not stored until AD4C.** The seeded applications are stored rows. Their answers are derived as the samples' are (`extract.form_answers`) until submit stores them (2026-11-28, rung 4).

## Blast radius (measured)

Taken 2026-11-28 at `37ae6ec49`.

| What | Count | Command |
|---|---|---|
| Test files calling the seed | 10 | `grep -rln "seed\.\|from applydesk.seed\|seed(" applydesk/tests \| wc -l` |
| Non-test modules importing `sample_data` | 25 | `grep -rln "sample_data" applydesk --include=*.py \| grep -v tests \| wc -l` |
| Test files naming the samples | 163 | `grep -rln "sample_data\|wa9juxbc2t\|k7mfr3pq8z" applydesk/tests \| wc -l` |
| Readers of the local directory | 1 | `grep -rn "_local_users" applydesk --include=*.py \| grep -v "def "` |
| Account-menu templates (sign-out link) | 3 | `grep -rln "Sign out" applydesk/templates app/web/templates cordware/web/templates` |
| Specs naming the seed | 3 | `grep -rln "seed" applydesk/spec` |

## Status

**Kept open** (author, 2026-11-28): AD2X does not close. Each new capability adds its scenario to `applydesk/local_seed.py` here, so rung 7's close is struck and the plan stays in `guide/`.

- Rungs 2–6 built (#4277, #4278 and after). The cumulative read (base `5f8492747`) found 11, and the build acted on:
  - the second account took Review Robin's fake-user roles (`Identity.is_alternate`, never granted, never super-admin);
  - a refused form move or rejected CSV rows passed silently;
  - a half-built scenario was skipped as there;
  - submissions predated the window;
  - the plain applicant sat on a panel;
  - five applications without a second account;
  - a README sentence dropped.
- Left for whoever next writes the spec: `cordware/spec/identity.md`, `cordware/spec/host.md` (the route, the cookie, the Azure note), `cordware/spec/header_chrome.md` §4, `spec/permissions.md` (done), and the `local_seed.py` and `local_directory.py` rows in `applydesk/spec/architecture.md`.

## PR ladder

1. **Plan** (this file), its README row, and the AD2 series row. Prose only.
2. **The local directory as a fixed list.** A module of names and addresses, read by `directory._local_users`. Must not touch: the seed, the samples.
3. **Two identities on localhost.** Cordware's settings for the second fake account, the cookie, `resolve_identity` honoring it under the guard, and *Switch to …* in the account menus (Apply Desk, Review Robin, Cordware's landing). Must not touch: Easy Auth parsing.
4. **The scenario seed and Scenario 1.** `seed_local()`, run alone by a test for now: panels, the open form and its applications, through the services. Must not touch: the CLI's default.
5. **Scenario 2.** Create dossiers with five people, ten dossiers and two panels.
6. **The CLI loads the scenarios.** `python -m applydesk.seed` runs `seed_local()`; tests keep `seed()`; the local setup docs say what is seeded and how to switch identity.
   - **Last build rung:** `diff-reviewer` on the cumulative diff from rung 2's base.
7. ~~**Close:** `spec-writer` on the specs below; Status compacted; the plan archived.~~ Struck: the segment stays open (author, 2026-11-28).

## Definition of done

- `python -m applydesk.seed --reset` on a fresh checkout makes exactly the two scenario exercises and no sample exercise (a test runs `seed_local()` and checks the exercises, applications, dossiers and panels it made).
- The local people search finds the RA panels' people with `sample_data` not imported (test).
- *Switch to …* flips the signed-in person on a local run, and is absent with the cookie ignored outside local (tests).
- `applydesk/tests/conftest.py` still seeds the samples, and the suite passes.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD2X` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- ~~Who is the second identity?~~ Divya Petrova (`FAKE_AUTH_ALT_*`), a local-directory person who applies in Scenario 1 (rung 3).

## Out of scope

- Submitting a form through the page (AD4C).
- A Form on Scenario 2 (the author's, by hand).
- Retiring `sample_data.py` from the tests.
- Switching between several real Microsoft accounts on Azure. Easy Auth keeps one session per browser, so it is *Sign out*, then sign in with the account picker. Recorded in `cordware/spec/host.md` at rung 3, not built.

## Doc impact

- `applydesk/spec/architecture.md` — the `seed.py` row (two seeds, the scenarios), the new local directory module, the `directory.py` row.
- `cordware/spec/host.md` — the second fake identity, its cookie and guard; switching Microsoft accounts on Azure (sign out, then the account picker).
- `cordware/spec/header_chrome.md` — *Switch to …* in the account menu on a local run.
- `applydesk/README.md` — the seed command: what it makes, and switching identity.
- `applydesk/guide/ad2_series.md` — the AD2X row, and "The samples are seeds" now reads: the samples seed the tests; localhost seeds the scenarios.
- `applydesk/guide/todo_master.md` — ruling 74's seed clause amended to the same effect (at close).

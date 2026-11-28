# Apply Desk — the AD4 series: the applicant's side

**Opened:** 2026-11-28 · **Roadmap:** AD4, *Applicant forms and portal* (`applydesk/guide/todo_master.md`, "MVP roadmap") · **Gates:** G1 and G4 (`applydesk/docs/applydesk_functional_spec_v0.6b_agent_handoff.md` §15.2)

AD4 is a series of segments, as AD2 is (author, 2026-11-28), taken before AD2H. Today an operator can build, save and lock a form, but no one can fill one in. The `/me` pages are read-only views of sample data, and they open only on a local run or for the super-admin. Each segment below makes one part real, and each closes on its own.

## Rulings for the series (author, 2026-11-28)

- **A submission writes its dossier at submit.** If a *Create dossiers* step has already made the applicant's dossier, the submission writes to it. Otherwise the submission creates the dossier and writes to it. This replaces ruling 81's "at submit or at the form's close, the operator's choice": there is no such setting.
- **A withdrawn submission frees a place** (G4): it does not count toward the Form's *Max dossiers per person*. While the form is open, the applicant may submit again.
- **Each application is a new record.** A second application starts fresh, with its own answers and dossier; earlier ones stay as they were. A withdrawn application is never reopened.
- **G1 is settled by what is built:** Apply Desk's own form engine (`applydesk/form_store.py`, the Form page's renderer), not a shared package with Review Robin. The series records any deviation from Review Robin's field rules where it occurs.

## What every AD4 segment holds to

- AD2's rules (`applydesk/guide/ad2_series.md`, "What every AD2 segment holds to"): the database, localhost, the layering, people by tenant and object ID, every change audited, revision guards, and nothing hard-deleted.
- **The applicant is the signed-in person** (`people.resolve`). No page reads `sample_data.MINE` once AD4A closes.
- **What an applicant may do is checked on the server**, never only on the page: who may apply, the form's window, the per-person maximum, and withdrawal's limit (ruling 49).

## The segments, in order

| Segment | Lands | Plan |
|---|---|---|
| **AD4A — The User Lobby is the signed-in person's** | `/me` reads the signed-in person: their own applications from the store, and the exercises open to them by the Form's *Who may apply* (anyone signed in, the invite list, or the dossiers made for them). The sample `MINE` goes | `applydesk/guide/segment_AD4A_user_lobby.md` |
| **AD4B — The form as published** | Publishing the form's stage freezes a version of its questions. An application answers a version, and later edits never change what was asked | — |
| **AD4C — Drafts and submit** | The application page becomes a form: *Save draft*, and *Submit* within the window. Answers are stored and checked against the version's rules on the server (required, bounds, list options, Select people from the directory). Opens `/me` to every signed-in person | — |
| **AD4D — Dossiers from submissions, and withdrawing** | At submit, the dossier is written to or created, as the series ruling says. *Withdraw* until a gate holding the dossier completes (ruling 49). *Max dossiers per person* is enforced at submit, race-safe, with withdrawn applications freeing a place | — |
| **AD4E — The photo answer** | The photo field (ruling 12; `applydesk/docs/photo_field_design.md`): taken, cropped to its ratio, and kept as the stated JPEG | — |
| **AD4F — A later Form over existing dossiers** | Ruling 83's entry rule: a Form that follows *Create dossiers* admits the dossiers' people and writes to their dossiers. Which of a person's several dossiers a submission writes to is settled in that plan | — |

**Order:** AD4A, then AD4B before AD4C (an answer needs a version to answer), then AD4D. AD4E and AD4F follow, in either order.

## Outside the series

- What evaluators see of a dossier, and the evaluator's `/me` card: AD2V and AD5.
- Sending the applicant's emails (receipt, reminder): AD7.
- Conditional questions: deferred (`applydesk/guide/todo_master.md`, "Open decisions").

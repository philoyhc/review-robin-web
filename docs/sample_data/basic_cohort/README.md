# Basic cohort

A peer-review cohort for a local run (`uvicorn`, fake auth as
`operator@example.edu`). Every file imports cleanly into one session,
in this order, on its Setup page or through Quick Setup; checked
2026-10-17 through the four roster importers.

| File | Rows | What it holds |
|---|---|---|
| `mock_reviewers.csv` | 154 | Everyone reviews: Tutor (6), Group (`TW01`–`TW11`, one tutor each) and Team (33, each inside one group) tags, and a profile link. |
| `mock_reviewees.csv` | 154 | The same people and tags, as reviewees. |
| `mock_relationships.csv` | 15 | Pairs tagged `Official` (`Mentor`, `Supervisor`, `COI`) and `Social` (`Friend`, `Roommate`), one, the other or both. `operator@example.edu` is on both sides: mentor and supervisor of three, a COI with one outside their group, and a friend or roommate of three. |
| `mock_observers.csv` | 4 | `operator@example.edu` (Coordinator), one reviewer (`kenji.russo`, Student rep), and two tutors in no other roster (`margaret.liu`, `samuel.adeyemi`). |

`operator@example.edu` is "Operator Example" in every roster, so the
cross-roster name check passes. Observers take one unlabeled tag
(`ObserverTag1`); the others carry friendly labels in their headers
(`spec/csv_contracts.md`, the header label grammar).

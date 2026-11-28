# applydesk/

Apply Desk: applications, assessment through Review Robin, and applicant
communication, mounted under Cordware at `/applydesk`. Segments AD1 to
AD1K built every page of its URL map as a working scaffold on sample data;
the AD2 series moves it into its own database, segment by segment (AD2B:
an exercise's settings, Details and the Operator Lobby). Rulings and the MVP
roadmap are in `guide/todo_master.md`.

**On localhost** (segments AD2A and AD2X, ruling 74), from the repository
root with the virtualenv active and `APP_ENV=local`, `ALLOW_FAKE_AUTH=true`
in `.env`, build Apply Desk's database (a SQLite file, `applydesk.db`,
unless `APPLYDESK_DATABASE_URL` says otherwise) and seed it:

```bash
alembic -c applydesk/alembic.ini upgrade head
python -m applydesk.seed
```

The seed builds the scenario exercises (`local_seed.py`) as Local Operator,
by posting what the pages post:

- **Community Project Grant 2027**: a published Form, opened 10 days before
  the seeding and open for 30 days after it, that anyone signed in may apply to; six applications, four
  submitted and two drafts (answers are derived until AD4C stores them).
- **Peer Mentor Nominations 2027**: *Create dossiers* alone, two dossiers a
  person; five people, Local Operator among them, ten dossiers in all.
- Each has two panels, *Readers* (Local Operator among them) and *Mentors*.

New capabilities add a scenario as they land. The tests keep the sample
exercises (`seed.seed()`); `--samples` loads those instead.

Flags: `--reset` empties Apply Desk's local database first (its own tables
only), and `--blank N` adds N blank drafts Owned by the same person, as *New
exercise* makes them. The open form's window starts at the seeding, so
re-seed after a month with:

```bash
python -m applydesk.seed --reset
```

The seed is idempotent (a scenario already there is left alone) and refuses
to run unless `APP_ENV=local` with fake auth on. An operator's pages answer
the platform super-admin, or someone on the operator allowlist who operates
the exercise, and 404 otherwise (`gate.py`). With `FAKE_AUTH_SUPER_ADMIN=false`
the fake identity is an ordinary operator, the Owner the seed made it. A run
that fails part-way is refused next time, not skipped: `--reset` rebuilds.

**Two identities.** The account menu's *Switch to …* flips between Local
Operator and a second fake account, Divya Petrova (`FAKE_AUTH_ALT_*`), a plain
applicant who applied to the open form: Review Robin and the landing page
offer it too. Only on a local run with fake auth on.

The local people search finds Cordware's fake accounts and the 48 people of
`local_directory.py`, each with a name and an address
(`directory.for_request`).

| Path | Holds |
|---|---|
| `main.py`, `routes_*.py`, `lookups.py` | The factory, `/health`, the pages (the super-admin's operator list among them, AD2A), and the path lookups they share |
| `gate.py`, `ids.py`, `web.py`, `sample_data.py` | Who reaches the pages (operators by their grants, AD2A), public IDs, templates and chrome, sample data |
| `stages.py`, `workflow.py`, `locks.py` | Stages, gates, outcomes and rules; each item's state, the status row and emails owed; what a published stage fixes |
| `timeline.py`, `home_ops.py` | The timeline Home and the applicant's page share; Home's operator part |
| `extract.py`, `paging.py` | Extract data's files; a long table's pages and sort |
| `db.py`, `models.py`, `alembic.ini`, `alembic/`, `seed.py` | Apply Desk's own database, `applydesk` (segment AD2A): engine and session from `APPLYDESK_DATABASE_URL`, its tables, its migration history and the localhost seed |
| `templates/applydesk/` | Templates; `base.html` carries the favicon and the bar |
| `tests/` | Apply Desk's tests, with a host harness (`tests/_host.py`) |
| `docs/applydesk_functional_spec_v0.6b_agent_handoff.md` | The functional baseline (v0.6b, 2 November 2026); where a ruling in `guide/todo_master.md` differs, the ruling wins |
| `docs/data_and_visibility_model.md` | Draft of an eventual spec (2026-11-21): the store, the dossier and extraction, and who sees each dossier item; the related rulings gathered, with open questions |
| `docs/photo_field_design.md`, `docs/photo_field/` | The applicant photo field's design and mock-ups (2026-11-12), from Utilities' photo proof of concept; in the MVP since ruling 12, built on Form with a ratio per question |
| `docs/chrome/` | Mock-ups of the exercise chrome (2026-11-13), for segment AD1D; its Workflow card was removed on 2026-11-15 |
| `docs/home/` | Mock-ups of Exercise Home (2026-11-17), for segment AD1I: the timeline horizontal (v1, Details locked and unlocked), vertical (v2, desktop and phone) and equal-width (v3, three and five stages and a phone, the one built), and the operator's part below or beside it (v4) |
| `docs/extract/` | Mock-ups of Extract data (2026-11-18), for segment AD1J: download cards after Review Robin's, desktop and phone (v1) |
| `spec/applications.md` | Apply Desk as the host sees it: registry entry, health, running alone, the URL map, and each page's contract |
| `spec/permissions.md` | Accounts and permissions, the target contract (2026-11-22): workspace roles (Operator, Admin, super-admin), an exercise's Owners and operators, participants, what each may do, guards and audit; each part marked built or to build |
| `spec/architecture.md` | Package layout, import boundaries, packaging, tests and CI |
| `guide/todo_master.md` | Rulings, the MVP roadmap and open decisions |
| `guide/ad2_series.md` | The AD2 series: what every AD2 segment holds to (its own database, checkable on localhost) and the segments AD2A–AD2G in order, each with the findings it takes |
| `guide/segment_AD1U_ui_adjustments.md` | AD1U: a standing segment for small UI adjustments the author asks for, each an item closing on its own; Item 1, Admin's pages take the operator pages' layout |
| `guide/ad4_series.md` | The AD4 series, the applicant's side (2026-11-28): what every AD4 segment holds to, the series' rulings (a submission writes its dossier at submit; a withdrawn one frees a place; each application a new record) and AD4A–AD4F in order |
| `guide/segment_AD2X_local_seed.md` | AD2X: the localhost seed as scenario exercises built through the services (an open form with applications; Create dossiers with ten dossiers; two panels each), the local directory a fixed list, and switching between two identities on localhost; the samples stay as test fixtures |
| `guide/segment_AD2Y_directory_on_ingest.md` | AD2Y: every person Apply Desk takes in looked up in the directory, as Review Robin's rosters are: Create dossiers', Invitees' and Panels' uploads, Panels' typeahead as a directory search, and *Recheck* for those not found |
| `guide/segment_AD2H_gate_entries.md` | AD2H: the Dossiers grid's cells in the database: gate entries, result values and outcome decisions with who and when; *Lock* saves; release per audience; *Decided* derived |
| `guide/segment_AD2I_who_may_apply.md` | AD2I: ruling 84 built: the Form's *Who may apply* (Anyone signed in, Invitees, Dossiers) with a stored invite list, Details' setting retired, the first item before gates, and reordering a stage's items |
| `guide/segment_AD2G_retire_simulation.md` | AD2G: retire the simulation. Item 1 makes every exercise an ordinary database exercise (the scratch store removed, *New exercise* and *Duplicate* capped at 50 live per creator, the seed's `--reset` and `--blank`); Item 2, request-scoped loading and paging, is planned when Item 1 closes |
| `guide/things_to_check_in_browser.md` | **Browser checks owed** on merged changes, one section per change, each row ticked and the section deleted once checked (2026-11-22, AD1R and AD1S's moved in from `guide/todo_master.md`) |
| `guide/ad2_deferred_findings.md` | The 2026-11-18 assessment's rows that wait on AD2's persistence and identity (28 rows, moved 2026-11-21); AD2's plan absorbs, rules or drops each |
| `guide/ad3_plus_deferred_findings.md` | The 2026-11-18 assessment's rows that wait on a stage after AD2: Layer B, AD3's lifecycle, AD4's dossier parts and AD7 (6 rows, moved 2026-11-21) |
| `guide/removed_help_lines.md` | A running tab of help lines taken off the pages: what each told the reader, kept until the author decides how such help is shown |
| `guide/archive/README.md` | Closed segment plans (AD2N the latest) and worked findings registers (the 2026-11-18 assessment's among them): AD1 (the package and URL map), AD1B (the Form page), AD1C (Dossiers), AD1D (the exercise's chrome), AD1E (Process), AD1F (Gates and Panels), AD1G (Evaluators and Evaluations), AD1H (the RA model exercise), AD1I (Exercise Home), AD1J (Extract data), AD1K (a status per stage, and what locks) |

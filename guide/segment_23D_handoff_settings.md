# Segment 23D — Interoperability: the handoff takes settings

**Opened:** 2026-11-15 · **Theme:** the handoff bundle may carry a Settings file, so a sender sets up the draft's instruments as well as its rosters · **Related:** `guide/archive/segment_23A_interop_poc.md`, `guide/archive/segment_23B_interop_return.md`, `spec/handoffs.md`, `spec/csv_contracts.md` §3.3, `applydesk/guide/todo_master.md` (ruling 26)

## Opportunity

The handoff creates a draft from rosters only (`spec/handoffs.md` §4: a `settings` file is refused, `handoffs.REQUIRED_FILES` / `OPTIONAL_FILES`), after the 2026-11-04 ruling that v1 sends rosters only (`guide/interoperability.md`). So every handed-off draft arrives with no instrument, and its operator builds one by hand in Review Robin. Apply Desk's ruling 26 (author, 2026-11-15) needs more: a gate's session arrives with its instrument (a field per result, keyed as Apply Desk prescribes, so results come back matched), visibility releasing nothing after the window (Apply Desk's dossier parts decide who sees results), and the schedule from the gate's dates. The author (2026-11-15): extend the proof of concept to send settings that, for example, set up instruments.

## Decision

**The bundle's `files` may carry `settings`: a Settings CSV (`spec/csv_contracts.md` §3.3) applied by Quick Setup's pipeline after the rosters, in the same all-or-nothing create.** Nothing new parses it: `_run_quick_setup_contents` already takes a `settings` slot (`SLOT_ORDER`), and its phase-1 validation, two-phase apply and error details are New session's. A refused settings file refuses the handoff as a refused roster does (`422 invalid_setup`, `slot: "settings"`, the importer's `details`), and the draft goes with it.

The Utilities proof of concept sends one: an instrument with two response fields (a 1–5 score keyed `score`, a comment keyed `comment`), its assignment rules set so `instruments_set_up` reads true, and no release scheduled. Its status card then shows the draft set up, which 23C's diagnostic status already reports.

**Rejected:**
- **A new, smaller instrument format for the handoff.** A second contract for what the Settings CSV already carries, round-trips and validates; a sender exports a session's settings and edits it, as an operator does.
- **A second operation** (`reviewrobin.apply_settings` on an existing draft). Two requests for one click, and the draft would exist half set up between them; one create stays one unit. Sending to an existing draft is the re-send this segment leaves out.
- **Bumping `protocol_version`.** The change is additive: an optional kind. A receiver without it refuses the file by name (`invalid_package`, *Not accepted: "settings"*), which a sender reads as "this Review Robin takes rosters only".

## Semantics

- **Identity.** The session's name and code come from `session_suggestion`, as now. The settings file's `session.name` and `session.code` rows are fill-blanks (`spec/csv_contracts.md` §3.3, "two rules"), and both are set, so the file cannot rename the draft; `description`, `deadline` and `help_contact` fill only where blank, as on New session.
- **Order.** Rosters, then settings, Quick Setup's `SLOT_ORDER`. Symmetric review in the file turns on only while both rosters are empty, so a handoff's file cannot turn it on (rosters are required): it stays off, not refused, as on New session.
- **Instruments** are replace-all, so the draft holds exactly the file's. A `rules_json` or Band 1 rule the card would refuse is refused here, by the same checks.
- **Schedule.** A schedule out of order is an error naming the field. Nothing fires: the draft is not activated (`spec/handoffs.md` §1), and 14E's clock acts only on what an operator set, which a handed-off schedule now is. *Decided at the plan:* a sent schedule is set by the operator's own handoff click, so it counts as set; the holding page and the receipt say nothing is sent.
- **Size.** The 1 MiB body cap (`handoffs.MAX_BYTES`) covers the settings file too; its own caps are §3.3's.
- **Replay.** Unchanged: completion is the recorded `session.handoff_completed`, written after every slot, settings included, has saved.
- **Audit.** `session.handoff_created`'s `counts(files=n)` counts it; the settings apply writes the events New session's settings import writes. No new event type.
- **Status.** Unchanged (version 3): `instruments_set_up` and `instruments` already report what the file set up.

## Judgment calls — decided

- **`results.csv` keys on `FieldKey`**, which the settings file now sets: a sender can prescribe it (ruling 26) without a mapping step.
- **The mock's settings are literal CSV text in `utilityapps/interop_poc/mock.py`**, not generated from Review Robin's serializer: Utilities may not import `app` (`cordware/tests/test_import_boundary.py`). Review Robin's test posts the same shape and asserts it applied.

## Blast radius (measured)

Taken 2026-11-15 at `92d698547`.

| What | Count | Command |
|---|---|---|
| Handoff service, route pipeline | 511, 1,668 lines | `wc -l app/services/handoffs.py app/web/routes_operator/_quick_setup.py` |
| Files naming the rosters-only rule | 4 | `grep -rln "Rosters only\|rosters only\|REQUIRED_FILES\|OPTIONAL_FILES" app tests utilityapps spec docs guide/interoperability.md` |
| Handoff tests; the sender's | 906, 150 lines | `wc -l tests/integration/test_handoffs.py utilityapps/tests/test_interop_poc.py` |
| The mock sender | 94 lines | `wc -l utilityapps/interop_poc/mock.py` |

## Status

- **Rung 2** (2026-11-15): `handoffs.OPTIONAL_FILES` takes `settings`; nothing else in the route changed, the pipeline already applying a settings slot. *Releasing nothing* needs no rows: a draft releases nothing until the operator releases, or a `session.responses_release_at` is set, and the mock sends neither (open question 1 answered).

## PR ladder

1. **Plan** (this file), its README row, the queued entry in `guide/todo_master.md` narrowed to the re-send.
2. **Review Robin takes settings.** `handoffs.py` accepts an optional `settings` kind and hands it to the pipeline; tests: a bundle with settings creates a draft whose instrument is set up; a refused settings file refuses the handoff and deletes the draft, naming the slot; the file's `session.name` and `session.code` do not rename the draft; an unknown kind is still refused. `spec/handoffs.md` §4–§5. Must not touch the sender.
3. **Utilities sends settings.** The mock's settings CSV (two fields, rules set, nothing released) in the bundle; the page's status shows instruments set up; `docs/interoperability_example.md` shows a settings file. Takes the segment's `diff-reviewer` read on rungs 2–3 cumulatively.
4. **Close.**

## Definition of done

- A handoff with a `settings` file creates a draft with its instrument set up (`tests/integration/test_handoffs.py`).
- A refused settings file refuses the handoff, `slot: "settings"`, and leaves no draft (test).
- The Utilities proof of concept's click lands on a draft whose status reads `instruments_set_up` (`utilityapps/tests/test_interop_poc.py`).
- `spec/handoffs.md` names `settings` as optional and its semantics; `guide/interoperability.md` records the change to its rosters-only ruling.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 23D` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **Visibility "releasing nothing"** (ruling 26): whether a draft's defaults already release nothing, or the file must set each instrument's view policies to hidden; settled at rung 2 against `spec/visibility_policy.md`, the mock sending what it needs.
- **The schedule's dates**: whether the mock sends any. Proposed: none, so the proof shows instruments only and the operator sets dates, until Apply Desk sends a gate's.

## Out of scope

- **Sending again to a draft not yet opened** (ruling 24's changes after Send): its own segment, kept as the queued entry in `guide/todo_master.md`.
- **Apply Desk's sender** (AD6), which this contract serves.
- **Observers, relationships and email templates in the mock**: the contract takes them already; the proof shows instruments.

## Doc impact

- `spec/handoffs.md` — §4: `settings` an optional file; §5: applied after the rosters, all or nothing, identity from `session_suggestion`.
- `guide/interoperability.md` — the rosters-only ruling amended: settings may be sent (2026-11-15).
- `utilityapps/spec/utilities.md` — the proof of concept sends a settings file.
- `docs/interoperability_example.md` — a settings file in the example bundle.
- `guide/README.md` — this plan's row (rung 1), moved to `guide/archive/README.md` at close.
- `guide/todo_master.md` — the queued entry narrowed to the re-send (rung 1).

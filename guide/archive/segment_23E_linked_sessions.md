# Segment 23E — Interoperability: sessions linked to another application

**Opened:** 2026-11-15 · **Theme:** a session another application created through the handoff carries a mark naming that application, and Review Robin turns off or rewords what the linked application does in its place · **Related:** `guide/archive/segment_23D_handoff_settings.md`, `spec/handoffs.md`, `spec/visibility_policy.md`, `spec/lifecycle.md`, `applydesk/guide/todo_master.md` (ruling 26)

## Opportunity

Apply Desk's ruling 26 has Apply Desk, not Review Robin, show results: its dossiers' parts decide who sees what, and when. A session it creates (23D) arrives releasing nothing, but every Review Robin control still offers to release: the instrument's visibility card describes what reviewees and observers will see after the window, Session Home offers *Release responses*, the schedule takes *Release from / until*, and the reviewee results and observer collation pages exist. An operator reading the card is misled, and one using the controls would show results Apply Desk meant to hold back. Validate also raises `reviewees.unreachable_for_results` on every dossier key, a warning that means nothing when Review Robin shows no results (an item 23A left open). The author (2026-11-15) proposed a nullable mark on every session: null for a native session, else naming the linked application and what it changes.

## Decision

**A nullable `ReviewSession.linked_app` names the application that created the session through the handoff; what a link changes lives in a code registry, one profile per application.**

- **The mark.** `linked_app`, a short string (`"applydesk"`), null for every native session. Set only by the handoff's create, from the bundle's `source_app` mapped to a known profile; an unknown `source_app` links nothing. Never set by a Settings import, a copy, Extract Setup or Rehydrate. Shown on Session Home as *Linked to Apply Desk*; an owner-only **Unlink** clears it, audited, and the session is native from then on.
- **The profile** (`app/services/linked_apps.py`, `LINKED_APPS`): per application, its display name and the switches below. A profile is code, so a change reaches every linked session on deploy; no per-session feature list.
- **Apply Desk's profile, for this segment:**

| Review Robin feature | Linked to Apply Desk |
|---|---|
| Release window (`responses_release_at` / `_until`) | Off: the schedule's fields disabled, a Settings import's values refused, *Release responses* and *Stop release* not offered |
| Observers | Off (author, 2026-11-15): `session.observers_enabled` false at the create; an `observers` file in the bundle refused; a Settings import turning them on refused; the Observers setup page not offered; the observer collation page closed |
| Visibility card, *after the window* cells | Fixed text in place of the mode (author, 2026-11-15): **See in Apply Desk** for an audience Apply Desk's dossiers can show results to (reviewees, as its *Candidate*; reviewers, as its panels), **Not shown** for any other. No observer column, observers being off. *During the window* cells unchanged |
| Reviewee results page | Closed: no grant resolves on a linked session |
| Validate `reviewees.unreachable_for_results` | Not raised |
| Everything else | Unchanged |

**Rejected:**
- **A per-session feature list stored with the mark.** Each session would freeze its rules at creation, and changing a rule would need a data migration. A per-session override can come later if one session must differ.
- **Reading the link from the audit trail** (`session.handoff_created`). Every page asking "is this linked?" would query audit events, and Unlink would have nothing to clear.
- **A notice only, no lock.** An operator could still release Review Robin-side what Apply Desk holds back.
- **Text sent by Apply Desk.** Review Robin never calls Apply Desk; a line in the bundle could come later. Fixed text for now (author).

## Semantics

- **Existing sessions** stay native: the migration adds a nullable column, no backfill. A session handed off before 23E is not linked (its operator may still release).
- **A replay** finds the session already marked; nothing changes.
- **Unlink** restores every native control at once; a release window left blank stays blank, and observers stay off until the owner turns them on. It does not reopen anything already refused.
- **A Settings import** onto a linked session refuses `session.responses_release_at` / `_until` rows naming a value, with an error naming the link; blank rows pass. The export writes blanks.
- **Lifecycle.** A linked session still activates, runs and expires as a native one; only release is Apply Desk's. Archive and retention are unchanged.
- **The status read** (`spec/handoffs.md` §10) reports `linked_app`, so the sender can confirm the link held.

## Judgment calls — decided

- ~~**Observers stay possible** on a linked session~~ — *reversed by the author, 2026-11-15: observers are off on an Apply Desk session (the profile's table).* Unlink lets the owner turn them back on.
- **The mark is a string, not an enum column**: profiles are code, and a value without a profile reads as native.

## Blast radius (measured)

Taken 2026-11-15 at `eaa9324d9`.

| What | Count | Command |
|---|---|---|
| Templates naming the release window | 4 | `grep -rln "Release from\|responses_release_at" app/web/templates \| wc -l` |
| The visibility card and next-action card | 2 | `grep -rln "view_policies\|Visibility" app/web/templates/operator/instruments_index.html app/web/templates/operator/partials/next_action_card.html` |
| Participant gates to close | 2 | `grep -rln "require_reviewee_with_current_grant\|require_observer_in_session" app/web/routes_reviewer` |
| Observer setup routes (*added 2026-11-15, same tree*) | 1 | `grep -rln "observers_enabled" app/web/routes_operator/_setup_observers.py` |
| Visibility service | 669 lines | `wc -l app/services/visibility_policies.py` |
| Files raising the unreachable warning | 4 | `grep -rln "unreachable_for_results" app --include=*.py` |

## Status

**Closed 2026-11-15.** Built as planned in two build rungs: **#3912** (the mark, with Unlink and the Session details refinements) and **#3913** (the profile's effects).

- **Diverged from the plan:**
  - A second profile, `utilities`, so the Utilities proof of concept's drafts link as Apply Desk's will (the author: "update interop-poc to test out the 23E idea"). Profile text names the application (*See in Utilities*).
  - The *See in …* cells show on the reviewer's card as well as the operator's, since that card would mislead the same way.
  - Observers are refused at a Quick Setup upload too (its slot is not offered), beyond the planned handoff, Save and import.
  - #3912 also carried the author's Create-page offset labels, a separate request in the same round.
- **Decisions confirmed at build:**
  - Unlink lives in Session details as the *Session is linked with* chip, with a *Linked* pill in the status row. Like every card edit, it is reached in draft or validated.
  - The release rule lives in `is_response_release_window_open` and in the release services, not only in the routes.
- **Reads:**
  - One cumulative `diff-reviewer` read of rungs 2–3. Findings: a Quick Setup observers upload turning observers on (high, fixed); Stop release ungated (fixed in the route and the service); `spec/session_home.md` missing from the doc impact (added); three tests weak (strengthened).
  - Codex: one finding on #3913, an observers refusal that ran before the replay lookup (fixed).
  - The close's `close_check` added `spec/quick_setup_card_spec.md` and `spec/workflow_card.md`. `spec-writer` wrote both and flagged nothing.

## PR ladder

1. **Plan** (this file), its README row, the queue entry.
2. **The mark.** The column and migration (both directions on Postgres); `linked_apps.py` with Apply Desk's profile; the handoff's create setting it; the status read reporting it; Session Home's badge and owner-only Unlink, audited (`EVENT_SCHEMAS`). Tests. Must not change any release or visibility behavior.
3. **The profile's effects.** Release window off (schedule, Settings import, Workflow card actions); the visibility card's fixed text; the participant pages closed; Validate's warning suppressed. Tests per row of the profile. Last build rung: `diff-reviewer` reads 2–3 cumulatively.
4. **Close.**

## Definition of done

- A handed-off session from `applydesk` carries `linked_app`; a native one, a Settings import or a copy never does (`tests/integration/test_handoffs.py`, a new `tests/integration/test_linked_sessions.py`).
- On a linked session: observers off, an `observers` file refused at the create, no release action, the schedule's release fields disabled, a Settings import's release values refused, the after-the-window cells reading *See in Apply Desk* / *Not shown*, the results and collation pages 404, no `reviewees.unreachable_for_results` (tests).
- Unlink restores the native controls and is audited (test).
- The migration upgrades and downgrades on Postgres (`ci-postgres`).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 23E` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- ~~**Which audiences read *See in Apply Desk***~~: reviewees and reviewers; no observers row (author, at close).
- ~~**Unlink's place**~~: the details card's *Session is linked with* chip, with a *Linked* pill in the status row (author, rung 2).

## Out of scope

- **Re-sending to an unopened draft**: the queued entry in `guide/todo_master.md`; it may later share the mark.
- **Text or per-part visibility sent by Apply Desk**: fixed text for now (author, 2026-11-15).
- **Apply Desk's side** (sending, reading `linked_app` back): its AD6.

## Doc impact

- `spec/handoffs.md` — §4: an `observers` file refused for a linked application's bundle; §5: the create sets `linked_app`; §10: the status reports it.
- `spec/visibility_policy.md` — a linked session's after-the-window cells and closed participant pages.
- `spec/lifecycle.md` — the release window off on a linked session; Unlink.
- `spec/csv_contracts.md` — §3.3: release rows refused on a linked session.
- `spec/settings_inventory.md` — `linked_app`, not a Settings field.
- `spec/session_home.md` — the details card's *Session is linked with* group, Unlink, the Observers and release fields off, the status row's pill (added at the rung 3 read).
- `spec/quick_setup_card_spec.md` — the Observers slot not offered, and an observers upload refused, on a linked session (added at close, `close_check`).
- `spec/workflow_card.md` — *Release responses* and *Stop release* not offered on a linked session (added at close, `close_check`).
- `guide/README.md` — this plan's row (rung 1), moved to `guide/archive/README.md` at close.
- `guide/todo_master.md` — the queue entry (rung 1); deleted at close.

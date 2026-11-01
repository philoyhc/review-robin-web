# Segment 20B — Symmetric review

**Opened:** 2026-11-01, at the author's request · **Theme:** a session where everyone reviews everyone (the reviewers are the reviewees) is set up from one roster · **Related:** `spec/setup_pages.md`, `spec/csv_contracts.md`, `spec/quick_setup_card_spec.md`, `spec/settings_inventory.md`, `spec/session_home.md`

## Opportunity

A peer review where every participant both gives and receives feedback is a common shape. Today it takes two identical rosters: the operator uploads the same people twice, as reviewers and as reviewees, and keeps the two in step by hand. An edit, a late addition or a withdrawal made on one roster and not the other leaves someone reviewed who cannot review, or the reverse, and nothing says so. The two rows already carry the same fields (`app/db/models/reviewer.py`, `reviewee.py`: name, address, profile link, status, three tags, the directory match); only the roster's name differs.

## Decision

- **A per-session setting, `symmetric_review`**, off by default. It is a **Symmetric review** checkbox on Add new session and a toggle on Session Home's Session details card, beside the Relationships and Observers toggles.
- **While it is on, the Reviewers roster is the only one edited.** Every write to it is mirrored to the Reviewees roster in the same transaction: an upload (replace, append, merge), an add, an edit, a status change, a delete. Both rosters still exist in the database, so assignments, responses and results keep their reviewee rows unchanged.
- **The Reviewees slot is greyed out** in Quick Setup, on Add new session and on Session Home, with the reason ("Symmetric review: reviewees are the reviewers").
- **The Reviewees page stays, read-only** (author, 2026-11-01). Its tab stays and its table shows the mirrored rows. **Everything in its Unlock panel is read-only too:**
  - What reviewees see of their own entry;
  - Upload Reviewees;
  - the tag-labels editor;
  - the Danger Zone.
  
  Its row controls go too. In their place, a note links to Reviewers.
- **Turning it on needs both rosters empty.** Otherwise the toggle is disabled, with the reason. **Turning it off is always allowed**, and leaves two ordinary rosters that then differ only as the operator edits them.
- **Export:**
  - the setup files carry the Reviewers roster only, and no reviewees file;
  - the Settings CSV carries `session.symmetric_review`;
  - a re-import (Duplicate, Rehydrate, Quick Setup) rebuilds the reviewees from the reviewers.

**Keep the Reviewees page, read-only** (recommended; chosen by the author, 2026-11-01). Rejected: *grey out the tab and make the page unreachable.*
- The Reviewees page is where reviewee-only state shows: results acknowledgment, reachability for `/results` (the `reviewees.unreachable_for_results` warning) and the directory match.
- Other pages link to reviewee rows (Responses, Assignments, Validate), and those links would land nowhere.
- A visible mirror lets the operator check it, where a missing page asks them to trust it.
- Keeping the page costs one banner and the read-only switch; removing it costs a route guard, a crawl exception and every incoming link.

## Semantics

- **One reconcile, not N mirrors.** One service function, `sync_reviewees_from_reviewers(db, session)`, matches each reviewee to its reviewer by a stored link, `reviewees.mirrors_reviewer_id` (a nullable foreign key to `reviewers.id`):
  - it adds missing reviewees, updates their fields and status, and deletes reviewees whose reviewer is gone, through the existing reviewee delete and its cascade and confirmations;
  - every reviewer writer calls it before committing (Blast radius lists them);
  - the link survives an address change: correcting a reviewer's address updates the same reviewee in place, so its `id`, assignments and responses are kept (Codex on `#3482`).
  - The mode turns on only with both rosters empty, so every mirrored reviewee is created by the reconcile and carries the link from the start.
  - Turning the mode off clears the links, leaving ordinary rows.
  - The key is `ON DELETE SET NULL`. The reconcile deletes a gone reviewer's reviewee itself, through the reviewee cascade. The key's rule only keeps a reviewer delete that bypasses the reconcile from failing on Postgres.
  
  Rejected: mirroring inside each writer, which would repeat the same logic in eight places that can drift apart.
- **Tags and their labels mirror too.** The three tag slots' labels (`session_field_label`) are copied, so a rule on `Reviewee.tag_1` means what `Reviewer.tag_1` means.
- **Kept per roster:** reviewee-only state (`results_acknowledged_at`).
- **The self-edit list mirrors.** "What reviewees see of their own entry" is read-only under the mode, so `reviewee_self_fields` follows `reviewer_self_fields`: one person, one list of fields. A reviewer's self-edit of a mirrored field is a reviewer write and syncs.
- **Self-review:** with symmetric review on, every person can be paired with themselves. Each instrument's existing Self review toggle decides that pair, and nothing new is added.
- **Imports while on:**
  - a reviewees file in Quick Setup, or in a Rehydrate or Duplicate bundle, is refused with the reason;
  - a Settings CSV that turns the mode on is refused while either roster has rows, as the toggle is;
  - when one Quick Setup carries settings and rosters, the settings apply first, so the reviewers file mirrors.
- **Lifecycle:** the toggle follows the Relationships and Observers toggles' state gates (editable while setup is editable). Turning it off mid-session leaves both rosters as they are.
- **Relationships and Observers are unaffected.** A relationship names a reviewer and a reviewee, and both exist.

## Judgment calls — decided

- **Matching key is a stored link, not the address** (2026-11-01, Codex on `#3482`). With address matching, an address correction would read as one person removed and another added, and the reviewee delete cascades to assignments, responses and relationships. The link costs one nullable column. Matching by `id` alone is impossible, since the two rosters number their rows separately.

- **A reviewer delete warns about the reviewee side** (author's default, 2026-11-01). The mirrored reviewee is deleted through the reviewee cascade, but the Reviewees page's confirmations are read-only under the mode. So with the mode on, Reviewers' delete confirmations also count the reviewee side: its assignments, the responses about them and their relationships. That covers row delete, bulk delete, Delete all and a replacing upload. The counts join the existing confirm text, with no new step.
- **Status mirrors** (author's default, 2026-11-01). Withdrawing a reviewer also withdraws them as a reviewee, so they stop being reviewed as well as reviewing: one person, one status.
- **When the toggle can change** (author's default, 2026-11-01). It follows the Relationships and Observers toggles' gates, and the empty-rosters rule settles nearly every case. Turning it off stays allowed at any stage.
- **Rung 1 previews the mode-on states by `?symmetric_preview=plain|marked`** (2026-11-01). Without the column nothing can turn the mode on, and the tab's look (open question 2) has to be seen to be chosen. The parameter touches no service, and rung 2 deletes it.

## Status

- **Rung 1 (scaffold), 2026-11-01.** Built with these pieces, all inert:
  - the New session checkbox, box first;
  - a Rosters group with a Symmetric review chip on Session Home's details card;
  - the greyed Reviewees Quick Setup slot;
  - the read-only Reviewees page, with its banner pointing to Reviewers and the Unlock panel and row controls gone;
  - the Reviewees tab, plain or marked "mirrored".
  
  The mode-on states show only under `?symmetric_preview=`, and only on the pages that pass it (New session, Session Home, Reviewees). Cumulative-diff base for the item's cold read: `6b3b0a0e`.

## Blast radius (measured)

Taken 2026-11-01 at `2accb87`:
- **Reviewer writers that must call the reconcile:** `app/services/` `reviewers.py`, `csv_imports.py` (import, append, merge, `delete_all_reviewers`), `roster_bulk.py`, `relationships.py`, `session_clone.py`, `session_rehydrate.py`, `session_purge.py` and `session_config_io/`. Counted with `grep -rln "Reviewer(" app/services`, `grep -rln "delete(Reviewer" app/services` and a read of `csv_imports.py`'s model map.
- **Where the toggle joins the existing pair:** `relationships_enabled` appears in 5 service modules (`grep -rln relationships_enabled app/services`) and 6 templates (`grep -rln relationships_enabled app/web/templates`). The new flag follows the same paths.
- **Routes:** 22 handlers in `app/web/routes_operator/_setup_reviewers.py` and `_setup_reviewees.py` (`grep -c "@router"`). The reviewee handlers that write gain a 409 while the mode is on.
- **Specs** naming reviewees, by mention count (`grep -ci reviewee`): `setup_pages` 86, `csv_contracts` 74, `assignments` 70, `extract_data` 58, `settings_inventory` 36, `participant_model` 35, `operator_ui_concept` 21, `quick_setup_card_spec` 20, `session_home` 7.

## PR ladder

1. **Scaffold** (`CLAUDE.md`, consequential UI): the checkbox, the Session details toggle, the greyed Reviewees slot and the read-only Reviewees page with its note. All inert, with no column. It must not touch a service.
2. **The column and the toggle:**
   - `sessions.symmetric_review` and `reviewees.mirrors_reviewer_id` (one migration);
   - its writer, with the empty-rosters rule and audit event;
   - the Settings CSV row;
   - the toggle wired.
3. **The reconcile:** `sync_reviewees_from_reviewers` and its calls from every writer in Blast radius. A test runs each writer with the mode on and checks that both rosters match.
4. **Read-only reviewees and imports:**
   - the reviewee write routes refuse;
   - Quick Setup, Duplicate and Rehydrate refuse a reviewees file;
   - the setup files leave the reviewees file out.
5. **Close:** specs, Guide copy.

## Definition of done

- With the mode on, every writer leaves both rosters with the same people, fields and status, and a test covers each writer. A test changes a reviewer's address and checks that the reviewee keeps its `id` and responses.
- The mode can be turned on only with both rosters empty, and off at any time. The Settings CSV round-trips it.
- The Reviewees page renders read-only with its note, and its write routes answer 409 while the mode is on.
- The setup export has no reviewees file while the mode is on, and a re-import rebuilds the reviewees.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 20B` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

1. ~~**The page: read-only or hidden?**~~ **Read-only, Unlock panel included** (author, 2026-11-01).
2. **The Reviewees tab's look while read-only:** normal, or marked (a lock or "mirrored")? Settled on the scaffold.
3. **Reviewee-only columns in a future upload format,** if any appear: they would need a home on the Reviewers file. None exist today.

## Out of scope

- Partial symmetry (some reviewees are not reviewers). Turn the mode off for that.
- Observers mirrored from reviewers.

## Doc impact

- `spec/settings_inventory.md` — `symmetric_review` in §2 and in the Settings CSV coverage (rung 2).
- `spec/csv_contracts.md` — the Settings CSV row; reviewees files refused while the mode is on (rungs 2, 4).
- `spec/setup_pages.md` — the Reviewees page read-only under the mode; the Reviewers page as the only roster editor (rungs 1, 4).
- `spec/session_home.md` — the Session details toggle and the greyed Reviewees slot (rung 1).
- `spec/quick_setup_card_spec.md` — the greyed Reviewees slot and the refusal (rungs 1, 4).
- `spec/operator_ui_concept.md` — the Add new session checkbox (rung 1).
- `spec/extract_data.md` — the setup export without the reviewees file (rung 4).
- `spec/assignments.md` — self-review under the mode: the instrument's toggle decides (rung 5).
- `spec/architecture.md` — `reviewees.mirrors_reviewer_id`, the reconcile, and the audit event's `EVENT_SCHEMAS` entry (rungs 2, 3).
- `app/web/templates/guide.html` — a paragraph on symmetric review (rung 5).
- `guide/todo_master.md` — the queue entry (at close).

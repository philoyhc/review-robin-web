# Segment 23F — Interoperability: the linked application keeps its draft current

**Opened:** 2026-11-15 · **Theme:** while a linked session is unopened, its rosters and the set-up the linked application sends are that application's: it re-sends them to the draft, and Review Robin stops editing them · **Related:** `guide/archive/segment_23D_handoff_settings.md`, `guide/segment_23E_linked_sessions.md`, `spec/handoffs.md`, `applydesk/guide/todo_master.md` (rulings 24, 26, 27)

## Opportunity

Apply Desk's ruling 24 puts changes after Send in Apply Desk until the Review Robin session opens, then in Review Robin. The handoff only creates (`spec/handoffs.md` §5), so an Apply Desk change after Send has nowhere to go. Meanwhile every Review Robin roster and set-up control stays open on a linked draft, so an operator's edit there would diverge from Apply Desk and be lost or contradicted at the next send. The author (2026-11-15) ruled to lock rosters and Quick Setup on a linked draft and have Apply Desk re-send to it; to keep the lock to rosters and the settings that set the session up; and to treat a session reverted to draft as unopened again.

## Decision

**A second handoff operation, `reviewrobin.update_draft_session`, replaces a linked draft's rosters and its application-owned settings; while the session is unopened, Review Robin refuses its own edits to them.**

### What the linked application owns (for the author's inspection)

Owned while the session is **unopened** (draft or validated). Once it is activated, Review Robin's own rules apply (ruling 24); a revert to draft returns ownership.

| Area | Owned by the linked application | Stays Review Robin's |
|---|---|---|
| Rosters | Reviewers, Reviewees, Relationships (the pairs, ruling 27) | Observers: off already (23E) |
| Session schedule | `session.scheduled_activate_at` (Start = the stage's opening), `session.deadline` (End = its close) | Invite and reminder offsets; display timezone |
| Session switches | `session.relationships_enabled` (follows the Relationships file) | `session.symmetric_review` (refused on a handoff, 23D); release and observers off (23E) |
| Session identity | `session.name` and `session.code`: set at the create from the suggestion, never re-sent | Description, help contact, tags, retention, archive offset |
| Instrument: the instrument itself | `name`; which instruments exist and their order (matched by ordinal) | `description`, `short_label`, `intro_layout`, `accepting_responses` |
| Instrument: its response fields | the field set: `field_key` (prescribed, ruling 24), `label`, `response_type`, `data_type`, `required`, `visible`, `min` / `max` / `step`, `list_csv` options, branching (`branch_*`) | `help_text` and `help_text_visible` *(author's call: proposed Review Robin's)*; `response_layout`, `starts_new_page` |
| Instrument: who reviews whom | `band1_touched_links`, `band2_state`, `rule_set_name` and the `session_rule_sets[N]` it names, `group_kind`, `self_reviews_active`, `self_review_handling` | — |
| Instrument: what reviewers see | — | Display fields (Band 3) and their sort, `display_layout`, column chips and widths |
| Visibility | — (23E fixes the after-the-window text; `view_policies` rows are kept, unread) | — |
| Email templates, participant self-fields | — | All |

### The re-send

- **The operation:** `POST /operator/handoffs/sessions/{session_ref}`, the envelope of §4 with `operation` `reviewrobin.update_draft_session` and no `session_suggestion`; browser-mediated and signed in, as the create.
- **The files:** `reviewers` and `reviewees` required, `relationships` optional: the rosters are the application's whole picture, so an absent Relationships file clears them. `settings` optional: absent leaves the owned settings as they are; present, it may carry only owned rows (any other row refused, naming the field) and applies them as targeted updates, instruments matched by ordinal (added or removed to match), the rest of each instrument kept.
- **All or nothing**, through Quick Setup's pipeline as the create; a validated draft returns to draft (`invalidate_if_validated`).
- **Refused:** a `session_ref` that is not a session linked to this `source_app` (`404 not_linked`); one the operator may not operate (`403`); an opened session (`409 session_opened`); a file refused as the create refuses it (`422 invalid_setup`, `slot`).
- **Replay:** a repeated `transfer_id` answers `200 already_updated` without applying again (audit event `session.handoff_updated`, its context the transfer).
- **Receipt:** `200 {status: "updated", session_ref, session_code, session_home_url}`.

### The locks (linked and unopened)

- **Quick Setup**: the card's roster and settings slots are not offered; the card says the rosters and set-up come from the application, and that Unlink returns them.
- **Reviewers, Reviewees, Relationships pages**: read-only; no import, no row added, edited, deactivated or deleted, no directory add. Refused in the services.
- **Settings import**: refused (it replaces every instrument wholesale); the operator edits Review Robin's settings on their cards, or unlinks.
- **Session details**: Start and End shown, not editable ("From {application}").
- **Instruments page**: the owned fields are fixed switches; the rest edit as now.

**Rejected:**
- **Re-send as a fresh create, discarding the draft.** Every Review Robin-side refinement (display fields, email templates, offsets) would be lost on each change.
- **Lock everything on a linked draft.** The author kept the lock to rosters and the identified set-up; the rest is the operator's.
- **Diff the re-sent rosters row by row.** A draft has no responses and pairs are rebuilt at Prepare, so a whole-roster replace loses nothing and is the import's existing path.

## Semantics

- **Opened** means activated or later; a session reverted to draft is unopened again (author).
- **Unlink** ends ownership at once: every lock lifts, and a later re-send is `404 not_linked`.
- **A settings row naming an instrument ordinal past the re-send's count** removes that instrument and its operator-owned properties; a new ordinal gets the defaults.
- **The release and observers rows** stay refused as 23E refuses them.
- **Concurrent edit**: the re-send takes the session lock the import takes; an operator edit refused by the lock never half-applies.

## Judgment calls — decided

- **A separate operation, not a flag on the create**: the create's replay is by `transfer_id` into a new draft; an update names its draft.
- **Locks only while unopened**: after activation Review Robin's lifecycle already locks setup, and ruling 24 gives later changes to Review Robin.

## Blast radius (measured)

Taken 2026-11-15 at `320e71820`.

| What | Count | Command |
|---|---|---|
| Roster page POST routes | 29 | `grep -c "@router.post" app/web/routes_operator/_setup_reviewers.py app/web/routes_operator/_setup_reviewees.py app/web/routes_operator/_setup_relationships.py` |
| Quick Setup, directory, Settings POST routes | 9, 3, 2 | `grep -c "@router.post" app/web/routes_operator/_quick_setup.py app/web/routes_operator/_directory.py app/web/routes_operator/_settings.py` |
| Instrument POST routes | 23 | `grep -rn "@router.post" app/web/routes_operator/_instruments*.py \| wc -l` |
| Settings field paths exported | 71 | `grep -o '\.[a-z_0-9]*"' app/services/session_config_io/_serialize.py \| sort -u \| wc -l` |

## PR ladder

1. **Plan** (this file), its README row, the queue entry replacing item 3.
2. **The re-send: rosters.** The operation, route, service, replay, refusals, audit (`EVENT_SCHEMAS`); `spec/handoffs.md`. Settings refused on a re-send until rung 3. Tests.
3. **The re-send: settings.** The targeted apply of owned rows; instruments by ordinal. Tests.
4. **The proof of concept re-sends.** Utilities' page sends changed rosters and bounds to its linked draft. Tests.
5. **The locks: rosters and session.** Quick Setup, the three roster pages and directory add, the Settings import, Start and End; each refused in its service. Tests.
6. **The locks: instruments.** The owned instrument fields fixed on the Instruments page and refused in their routes' services. Tests. Last build rung: `diff-reviewer` reads 2–6.
7. **Close**, after the author's browser check.

## Definition of done

- A re-send replaces a linked draft's rosters and owned settings all or nothing; refused when opened, unlinked or another application's; a replay applies once (`tests/integration/test_handoff_update.py`).
- The proof of concept re-sends and its draft changes (`utilityapps/tests/test_interop_poc.py`).
- On a linked, unopened session every lock in the Decision refuses in its service, and Unlink lifts them (tests).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 23F` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **The ownership table**: the author's inspection, before rung 3 (settings) and rung 6 (instruments). Rungs 2 and 5 depend only on the rosters row.
- **Response field help text**: proposed Review Robin's; the author's call with the table.

## Out of scope

- **Apply Desk's sending** (its AD6): Apply Desk's side of the re-send.
- **Changes after the session opens**: Review Robin's, under its own rules (ruling 24).
- **Results back to Apply Desk**: `spec/handoffs.md`'s exports, unchanged.

## Doc impact

- `spec/handoffs.md` — the update operation: envelope, files, refusals, replay, receipt; what a re-sent settings file may carry.
- `spec/csv_contracts.md` — §3.3: the owned rows a re-send applies, and the Settings import refused on a linked, unopened session.
- `spec/session_home.md` — Start and End from the application; the Quick Setup card's line.
- `spec/setup_pages.md` — the roster pages read-only on a linked, unopened session.
- `spec/instruments.md` — the owned instrument fields fixed.
- `guide/interoperability.md` — §5's revisit retired into this segment.
- `guide/README.md` — this plan's row (rung 1), moved to `guide/archive/README.md` at close.
- `guide/todo_master.md` — the queue entry (rung 1); deleted at close.

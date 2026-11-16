# Segment 23F — Interoperability: the linked application keeps its draft current

**Opened:** 2026-11-15 · **Theme:** while a linked session is unopened, its rosters and the set-up the linked application sends are that application's: it re-sends them to the draft, and Review Robin stops editing them · **Related:** `guide/archive/segment_23D_handoff_settings.md`, `guide/archive/segment_23E_linked_sessions.md`, `spec/handoffs.md`, `applydesk/guide/todo_master.md` (rulings 24, 26, 27)

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
| Instrument: who reviews whom (the assignment rules, author 2026-11-15) | `band1_touched_links`, `band2_state`, `rule_set_name` and the `session_rule_sets[N]` it names, `group_kind`, `self_reviews_active`, `self_review_handling`. Two shapes expected: **All – All – Individual** (Links 1–3; the proof of concept's today) and **All – By relationships – Individual** (Link 2 held to the pairs Apply Desk sends, ruling 27) | — |
| Instrument: what reviewers see | — | Display fields (Band 3) and their sort, `display_layout`, column chips and widths |
| Visibility | — (23E fixes the after-the-window text; `view_policies` rows are kept, unread) | — |
| Email templates, participant self-fields | — | All |

### The re-send

- **The operation:** `POST /operator/handoffs/{transfer_id}/update`, naming the draft by the transfer that created it, as the status and results reads do (a sender names its transfer, never a free session reference: interop spec §6.6); the body is the envelope of §4 with its own new `transfer_id`, `operation` `reviewrobin.update_draft_session` and no `session_suggestion`. Browser-mediated and signed in, as the create.
- **The files:** `reviewers` and `reviewees` required, `relationships` optional: the rosters are the application's whole picture, so an absent Relationships file clears them. `settings` optional: absent leaves the owned settings as they are; present, it may carry only owned rows (any other row refused, naming the field) and applies them as targeted updates, instruments matched by ordinal (added or removed to match), the rest of each instrument kept.
- **All or nothing**, through Quick Setup's pipeline as the create; a validated draft returns to draft (`invalidate_if_validated`).
- **Refused:** a creating transfer that is unknown, incomplete, or whose session is not linked to this `source_app` (`404 not_linked`); one the operator may not operate (`403`); an opened session (`409 session_opened`); a file refused as the create refuses it (`422 invalid_setup`, `slot`).
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

## Decision amended (author, 2026-11-16)

The author's lock list supersedes *The locks* above and widens the ownership table. Instruments wait for the author's assignment model.

- **For as long as the session is linked**, whatever its state, not only while unopened. The re-send still applies only to an unopened draft (rung 2). After the session opens, changes come by reverting it to draft (and *Delete data* if it holds responses) for Apply Desk to re-send, or by Unlink.
- **Session details**: the card never unlocks while linked; its chip is display-only.
  - Owned by Apply Desk and re-sent with the session: `session.name`, `session.code`, `session.description`, `session.display_timezone`, `session.help_contact`, the session tags (`session_tags[N].tag`), Start (`scheduled_activate_at`) and End (`deadline`).
  - A re-sent code another session holds is `409 session_code_conflict`, as at the create. Name and code are written on a re-send, not filled only when blank.
  - The lobby's inline edit and bulk tags refuse a linked session's name, code and tags.
- **A *Linked application* card**: half width, at the top of the bottom-left column, where Quick Setup was.
  - It names the application and says the rosters and set-up come from it.
  - It holds the confirm-Unlink, moved out of Session details.
- **Quick Setup**: hidden while linked; the Linked application card takes its place.
- **Owners and Danger zone**: stay active for the MVP. *Delete data* clears responses so Apply Desk can repopulate by a re-send.
- **Rosters** (Reviewers, Reviewees, Relationships):
  - Inactive: uploads and delete-all, row add, edit and delete, directory add, and roster tags.
  - Each is refused in its service.
- **Email**: Review Robin sends none for a linked session; Apply Desk sends from inside itself.
  - The email templates page (`_setup_invite.py`) is inactive.
  - The Workflow card's *Send invites* and *Send reminders* are not offered.
  - The submit acknowledgement (`invitations.queue_responses_received`) is not queued.
  - Apply Desk's emails link to Review Robin's `/me`: a reviewer reaches the session by signing in, matched by email; the token link only stamps *opened*.
- **Settings import**: refused (as planned).
- **Instruments**: decided below (*Instruments decided*), superseding the instrument rows of the table.
- **Defaults at the create** (author, 2026-11-16): the Relationships tab on (`relationships_enabled`), the Email templates tab off.
- **Invitations page**: no *Send* and no *Regenerate*. Apply Desk shares the session link, and a reviewer signs in; per-reviewer tokens are not needed.

## Instruments decided (author, 2026-11-16)

**One instrument per gate**: every gate filters to one set of pairwise assignments (ruling 27), so a different assignment rule, the reason for several instruments in a native session, never arises.

| Instrument part | Owner on a linked session |
|---|---|
| Which instruments exist | Apply Desk: exactly one. *+Instrument*, *Replicate*, *Delete* and page breaks inactive |
| `name`, `short_label` | Apply Desk: the gate's name, both |
| `description` | Apply Desk: the gate's description |
| Assignment rule (Band 1) | **Fixed by Review Robin**, not sent: Link 1 *All*, Link 2 a rule `pair_context.tag1 IS FILLED`, Link 3 *Individual*. In effect: assign where a relationship exists. No Group. |
| Response fields | Apply Desk, in its order: `field_key`, `label`, `help_text`, `help_text_visible`, `response_type`, `data_type`, `required`, `visible`, bounds, `list_csv`, branching |
| Layouts (intro, responses, display), column widths | Review Robin, through the card's Lock / Unlock |
| Display fields | Review Robin, starting from **Name + ProfileLink** (the dossier link). For a blind gate Apply Desk sends the Dossier ID as the reviewee's name, so Review Robin needs nothing new |
| Card colour | Review Robin, as now |
| Visibility | Fixed by 23E |

- **The pair tag**: Apply Desk fills `PairContextTag1` on every relationship it sends, with the evaluator's source (*Nominated*, *Panel A*), so the rule matches every pair it sends and the reviewer sees why.
- **A re-send's settings** carry the instrument's owned rows; anything else on it, the assignment rows included, is refused as not owned. The field set and its order replace the draft's.


## Semantics

- **Opened** means activated or later; a session reverted to draft is unopened again (author). Opened or not, a linked session stays locked (amendment).
- **Unlink** ends ownership at once: every lock lifts, and a later re-send is `404 not_linked`.
- **A settings row naming an instrument ordinal past the re-send's count** removes that instrument and its operator-owned properties; a new ordinal gets the defaults.
- **The release and observers rows** stay refused as 23E refuses them.
- **Concurrent edit**: the re-send takes the session lock the import takes; an operator edit refused by the lock never half-applies.

## Judgment calls — decided

- **A separate operation, not a flag on the create**: the create's replay is by `transfer_id` into a new draft; an update names its draft, by the creating transfer.
- **An absent Relationships file clears the pairs** by the roster replace's own cascade (`csv_imports` deletes a replaced roster's relationships), so the re-send needs no clearing step of its own.
- ~~**Locks only while unopened**~~ — superseded (author, 2026-11-16): the locks hold for as long as the session is linked.

## Blast radius (measured)

Taken 2026-11-15 at `320e71820`; the amendment's rows taken 2026-11-16 at `a7c24897a`.

| What | Count | Command |
|---|---|---|
| Roster page POST routes | 29 | `grep -c "@router.post" app/web/routes_operator/_setup_reviewers.py app/web/routes_operator/_setup_reviewees.py app/web/routes_operator/_setup_relationships.py` |
| Quick Setup, directory, Settings POST routes | 9, 3, 2 | `grep -c "@router.post" app/web/routes_operator/_quick_setup.py app/web/routes_operator/_directory.py app/web/routes_operator/_settings.py` |
| Instrument POST routes | 23 | `grep -rn "@router.post" app/web/routes_operator/_instruments*.py \| wc -l` |
| Email templates page POST routes (amendment) | 3 | `grep -c "@router.post" app/web/routes_operator/_setup_invite.py` |
| Session Home and lobby POST routes (amendment) | 8, 7 | `grep -c "@router.post" app/web/routes_operator/_session_home.py app/web/routes_operator/_lobby.py` |
| Settings field paths exported | 71 | `grep -o '\.[a-z_0-9]*"' app/services/session_config_io/_serialize.py \| sort -u \| wc -l` |

## Status (closed 2026-11-16)

**Intended vs done.** The re-send and the locks shipped as amended, in rungs 2 to 7k (#3918 to #3936) and the close. The ladder became:
- **2** the re-send of rosters (`POST /operator/handoffs/{transfer_id}/update`), with one refusal the plan did not name: `409 session_has_responses` (a reverted draft can hold responses).
- **2a** the switchboard: `linked_apps.Lock` (nine), per-profile locks and owned settings, one check `linked_apps.locks(session, lock)`; 23E's release and observers flags retired.
- **3** the owned session rows, written directly in the save's unit rather than merged into the export and imported (the import rebuilds every instrument and would move the ordinals Apply Desk reads back by).
- **4** Utilities' Re-send. **5** split (Codex, scaffold-first): 5a the Linked application card as a scaffold, 5b the details, Quick Setup and Settings-import locks with the card in Quick Setup's place. **6** the roster, email and invitation-send locks; Relationships on at the create.
- **7** re-cut by *Instruments decided* and split: 7a the fixed rule and display start at the create; 7b the re-send carries the instrument's owned rows (fields replaced by `field_key`); 7c the Instruments page locks.
- **7d to 7k**, from the author's browser checks: 7d roster self-field cards withdrawn, the mock's relationships tagged by panel; 7e the create fills every owned part, the short label follows the name, the page repair skips the lazy seeds; 7f the release and prompt fields hidden; 7g Clear list on the proof of concept; 7h whether a field is required is the application's, fixed regions look fixed, Profile held; 7i Session details' cells placed explicitly; 7j Utilities takes the email locks, with the reviewer page's previews, the Send note and the Email Template pill hidden; 7k the tag `applydesk` alone, the relationship tag never a display field (seed skipped; the repair hides and audits an old row; saves and routes hold it), the description shown as text.
- **Close**: `spec/linked_sessions.md`, by lock so another application is a profile entry (author), with `tests/unit/test_linked_sessions_spec.py`.

**Decisions confirmed at build.**
- Locks are refused at routes or route dependencies, not in services: the handoff's own create and re-send run the same pipeline (Definition of done amended).
- The card's Save ignores owned inputs rather than refusing, since the page posts every band at once.
- A linked instrument's fields stay unbranched; branching from the application is later (Out of scope).
- Tags and display identity are Apply Desk's: `applydesk`; a confidential gate sends "Name redacted" and the Dossier ID.
- The Assignments page's instrument chip needs no lock: it only filters the preview.
- Utilities kept email on through 7i as the switchboard's second profile; from 7j it takes every lock, and a test builds a partial profile instead.

**Reads.** One cumulative `diff-reviewer` read at 7c (no blocking findings; six should-fix, fixed in 6, 7a, 7b and 7c), then one read per later code rung, each acted on in its PR. Codex findings were fixed in their PRs. #3933 (the description box fits its text) shipped beside the segment, outside its ladder.

## PR ladder

1. **Plan** (this file), its README row, the queue entry replacing item 3.
2. **The re-send: rosters.** The operation, route, service, replay, refusals, audit (`EVENT_SCHEMAS`); `spec/handoffs.md`. Settings refused on a re-send until rung 3. Tests.
2a. **The switchboard** (author, 2026-11-16; before rung 3, so every later lock uses it):
   - A profile's switches become a set of named locks, `LinkedProfile.locks: frozenset[Lock]`, from a fixed menu. It covers 23E's release and observers plus 23F's.
   - One check at every gate: `linked_apps.locks(session, Lock.X)`.
   - Each profile lists the settings fields it owns, which is what a re-send accepts.
   - Profiles stay in code, never in the database or the bundle.
   - Apply Desk's profile takes every lock. Utilities' keeps email on (no email or invitation-send locks), so a second profile proves the generality.
   - Policies particular to Apply Desk (the fixed rule, the display default, one instrument per gate) stay its profile's until a second application needs them.
   - No behavior change for Apply Desk. Tests.
3. ~~**The re-send: settings.**~~ Re-cut by the amendment: **the re-send: session settings** — the owned session rows (name, code, description, timezone, help contact, tags, Start, End, relationships switch) merged into the draft's export and imported; code conflicts refused. Instrument rows wait for the assignment model. Tests.
4. **The proof of concept re-sends.** Utilities' page sends changed rosters and session settings to its linked draft. Tests.
5. ~~**The locks: rosters and session.**~~ Re-cut: **the Linked application card and the session locks** — the card with Unlink; Quick Setup hidden; Session details never unlocked; the lobby's inline edit and bulk tags refused; the Settings import refused. Each refused in its service. Tests.
6. **The locks: rosters and email** (new).
   - The roster pages' uploads, rows, directory add and tags.
   - The Email templates tab off, *Send invites* / *Send reminders*, the submit acknowledgement.
   - The Invitations page without *Send* / *Regenerate*.
   - The Relationships tab on at the create.
   - Tests.
7. ~~**The locks: instruments.**~~ Deferred to the assignment model; now **the instrument** (*Instruments decided*):
   - Review Robin fixes the assignment rule on a linked instrument; display fields start from Name + ProfileLink.
   - The re-send carries the one instrument's owned rows.
   - On the Instruments page, the owned parts are fixed and the add, replicate, delete and page-break controls inactive, each refused in its service.
   - Tests.
8. **Close**, after the author's browser check. The last build rung before it takes the cumulative `diff-reviewer` read from rung 2.

## Definition of done

- A re-send replaces a linked draft's rosters and owned settings all or nothing; refused when opened, unlinked or another application's; a replay applies once (`tests/integration/test_handoff_update.py`).
- The proof of concept re-sends and its draft changes (`utilityapps/tests/test_interop_poc.py`).
- On a linked session, opened or not, every lock in the amended Decision refuses ~~in its service~~ at its route or route dependency (amended at build, see Status), and Unlink lifts them (tests).
- `spec/linked_sessions.md` exists: one section per `linked_apps.Lock` (what it hides, refuses and holds, page by page, each pointing to the owning spec), what linking does whatever the locks (the fixed rule, the display start, Relationships on), the profile table (application → locks), and how to add an application; `tests/unit/` fails on a `Lock` member the page does not name (added at the close, author 2026-11-16).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 23F` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- ~~**The ownership table**~~: the session rows settled by the amendment (author, 2026-11-16); the instrument rows wait for the assignment model.
- ~~**Response field help text**~~: Apply Desk's (author, 2026-11-16).
- ~~**How *By relationships* is sent**~~: not sent. Review Robin fixes the rule on a linked instrument, `pair_context.tag1 IS FILLED`; Apply Desk fills the tag (author, 2026-11-16).

## Out of scope

- **Apply Desk's sending** (its AD6): Apply Desk's side of the re-send.
- ~~**Changes after the session opens**~~: superseded by the amendment; a linked session stays locked, and changes come through Apply Desk after a revert, or Unlink.
- **Results back to Apply Desk**: `spec/handoffs.md`'s exports, unchanged.
- **Branching from the application** (author, 2026-11-16): a re-send refuses branch rows and leaves every field unbranched for now; carrying branch rows is later work.

## Doc impact

- `spec/handoffs.md` — the update operation: envelope, files, refusals, replay, receipt; what a re-sent settings file may carry.
- `spec/lifecycle.md` — the release lock named as a switchboard lock (rung 2a); the scheduled sends' `linked_app_email_off` skip (rung 6).
- `spec/architecture.md` — the `linked_app_email_off` reason on the scheduled invite and reminder skips (rung 6, the cold read).
- `spec/csv_contracts.md` — §3.3: the owned rows a re-send applies, and the Settings import refused on a linked, unopened session.
- `spec/session_home.md` — Session details never unlocked while linked; the Linked application card with Unlink; Quick Setup hidden.
- `spec/setup_pages.md` — the roster pages inactive on a linked session.
- `spec/sessions_overview.md` — the lobby's inline edit and bulk tags refuse a linked session (amendment).
- `spec/workflow_card.md` — *Send invites* and *Send reminders* not offered on a linked session (amendment); the release lock named as a switchboard lock (rung 2a).
- `spec/instruments.md` — a linked instrument: the fixed rule, the owned parts fixed, add / replicate / delete inactive, display fields starting from Name + ProfileLink.
- `spec/operations_pages.md` — the Invitations page without *Send* / *Regenerate* on a linked session (instruments amendment).
- `utilityapps/spec/utilities.md` — the proof of concept's Re-send (rung 4).
- `spec/linked_sessions.md` — new at the close (author, 2026-11-16): the single reference for what a link changes, organized by lock so another application is a different selection of locks, not new prose; Apply Desk is likely the median case.
- `spec/ui_elements.md` — §9: a chip inside a linked instrument's fixed region is fixed (rung 7h).
- `guide/interoperability.md` — §5's revisit retired into this segment.
- `guide/README.md` — this plan's row (rung 1), moved to `guide/archive/README.md` at close.
- `guide/todo_master.md` — the queue entry (rung 1); deleted at close.

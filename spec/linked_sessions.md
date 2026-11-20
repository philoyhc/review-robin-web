# Linked sessions

What linking a Review Robin session to another application changes. The
page is organized by lock, so a new application is a profile entry in
`app/services/linked_apps.py` plus a row in **Profiles**, not new prose.
Where an owning spec states a surface in full, this page points to it.

## Purpose

A session is **linked** when `ReviewSession.linked_app` names an
application: set by a handoff's create whose `source_app` has a profile
in `linked_apps.LINKED_APPS`, never by anything else, and cleared by
**Unlink**. A value with no profile reads as native. The handoff
protocol, its create and its re-send are `spec/handoffs.md`.

A **profile** (`LinkedProfile`) is the application's key, the name Review
Robin shows, where results are seen instead (`shows_results`), the set
of `Lock` values it takes, and the settings fields it owns
(`owned_settings`). Profiles live in code, never in the database or a
bundle: they decide what an operator may not touch.

Every gate asks one question, `linked_apps.locks(session, Lock.X)`
(False on a native session); templates ask `linked.has("x")` or
`session | linked_locks("x")`. A lock with no gate has no effect, so a
new `Lock` member names its surfaces here.

**Unlink** (`POST /operator/sessions/{id}/unlink`, audit event
`session.unlinked`) makes the session native at once: every lock lifts
and a later re-send is `404 not_linked`.

## What linking does whatever the locks

- **The badge.** The status row's `Linked: {application}` pill, Session
  Home's *Session is linked with* chip, and `data-linked` on the lobby
  row (`spec/session_home.md`, `spec/sessions_overview.md`).
- **The Linked application card** (`#linked-app-card`, Session Home):
  names the application and holds the confirm-Unlink
  (`spec/session_home.md`).
- **Relationships on at the create.** The draft starts with
  `relationships_enabled` true: the application sends the pairs.
- **The re-send** (`POST /operator/handoffs/{transfer_id}/update`,
  `spec/handoffs.md` §6a) applies only to an unopened draft; locks hold
  for as long as the session is linked, in every state. After the session
  opens, changes come by reverting it to draft (and *Delete data* if it
  holds responses) for a re-send, or by Unlink.
- **The owned settings.** A re-send's settings file may carry only the
  rows the profile owns (`owned_settings`; the field list is
  `linked_apps.SESSION_FIELDS`; any other row is `422`, `reason`
  `not_owned`). They are written directly (`linked_settings`), not
  through the Settings import. A profile that takes `instrument_structure`
  also owns the instrument rows of that section.
- **Where locks are refused.** 23F's locks are refused at routes, not in
  services: the handoff's own create and re-send run the same Quick Setup
  pipeline as the operator's uploads, so a service-level refusal would
  block them. Most route gates answer `409` with
  `linked_apps.off_message` (*"{what} is off: this session is linked to
  {application}."*), through the dependencies and helpers in
  `app/web/routes_operator/_shared.py` (`require_rosters_open_session`
  and its siblings, `require_email_open_session`,
  `require_invitation_send_open_session`, `refuse_locked`,
  `refuse_linked_structure`) and checks inline in a few routes (Quick
  Setup, the Settings import, Session details, the lobby, the Workflow
  card). 23E's `release` and `observers` are also guarded in their
  services (`session_lifecycle`, `sessions`, the Settings import's parse,
  `handoffs.check_linked`), and some of those answer `422` or redirect
  with an error; each lock's section says which.

## The locks

Each section says what the lock hides, what it refuses, and what the
session holds as the application sent it.

### `release`

The application shows results; Review Robin has no release window.

- **Hides:** Session details' Release from / until (`spec/session_home.md`);
  the Workflow card's *Release* and *Stop release*
  (`spec/workflow_card.md`); the visibility card's after-the-window cells
  for reviewer and reviewee read **See in {application}**, fixed
  (`spec/visibility_policy.md` §3.4).
- **Refuses:** a release value from the details save (`422`) and from the
  Settings import (`spec/csv_contracts.md` §3.3); a direct POST to either
  release route redirects with an error.
- **Holds:** `is_response_release_window_open` False whatever the anchors
  say, so no `after_release` grant resolves and the reviewee `/results`
  gate never passes (`spec/lifecycle.md` §8.1). Stored visibility modes are
  kept, unread. The `reviewees.unreachable_for_results` warning is not
  raised (`spec/validate_page.md`).

### `observers`

- **Hides:** the Observers chip (inert, off), the Observers slot of Quick
  Setup, and the Observers row of the visibility card.
- **Refuses:** an `observers` file at the handoff's create or re-send
  (`422 invalid_setup`, `reason` `observers_off`); an Observers file on a
  Quick Setup submit; a details save or Settings row turning
  `observers_enabled` on (`spec/csv_contracts.md` §3.3). The auto turn-on
  after a roster save skips it.
- **Holds:** `observers_enabled` off and the roster empty; the observer
  `/collation` gate answers `404` (`spec/visibility_policy.md` §3.4,
  `spec/quick_setup_card_spec.md`).

### `session_details`

- **Hides:** nothing; the card is display-only.
- **Refuses:** the card never unlocks: `?editing=1` renders display mode,
  *Unlock* is inert, and `POST /config` is `409`; the lobby's inline edit
  is `409` and `bulk-tags` skips the session (`spec/session_home.md`,
  `spec/sessions_overview.md`).
- **Holds:** name, code, description, display timezone, help contact,
  tags, Start and End as the application sent them; a re-send rewrites
  them.

### `quick_setup`

- **Hides:** the Quick Setup card; the Linked application card takes its
  place (`spec/session_home.md`).
- **Refuses:** every Quick Setup upload route (`409`;
  `spec/quick_setup_card_spec.md`).
- **Holds:** rosters and settings as sent; the application's re-send
  fills them instead.

### `rosters`

- **Hides:** the editors on the Reviewers, Reviewees and Relationships
  pages, which render as a locked page naming the application, with no
  revert form; the *What reviewers / reviewees see of their own entry*
  cards (`spec/setup_pages.md` "A linked application's rosters").
- **Refuses:** every roster write: import, add, edit, inactivate,
  reactivate, delete, delete-all, the field-label editor, the self-field
  saves and the directory add and recheck (`409`).
- **Holds:** the rosters as a whole picture the re-send replaces; an
  absent Relationships file leaves no pairs. A linked session's roster
  tags are unused: assignment is by relationship.

### `settings_import`

- **Hides:** nothing of its own (the Settings slot goes with `quick_setup`).
- **Refuses:** the Settings import (`409`): it rebuilds every instrument,
  which is the application's set-up (`spec/csv_contracts.md` §3.3).
- **Holds:** Review Robin's own settings stay editable on their cards.

### `email`

The application sends its own email; reviewers reach the session by
signing in at `/me`, matched by email.

- **Hides:** the Email Template tab and its status pill; the Workflow
  card's *Send invites* and *Send reminders*, its due prompts, its
  auto-send captions and Activate's auto-send cancellation warning
  (`spec/workflow_card.md`); the lobby's Due pill for a due prompt, since
  none is due (`due_actions.due_actions`, `spec/sessions_overview.md`);
  Session details' invite and reminder
  prompts; the email-preview card on the Invitations reviewer page
  (`spec/operations_pages.md`).
- **Refuses (`409`):** the Email Template page (view, save, send test,
  reset; `spec/email_template_editor.md`), `invitations/send-all`,
  `invitations/remind-incomplete` and the per-row Send reminder.
- **Skips, not refused:** scheduled invites and reminders record
  `linked_app_email_off` (`spec/lifecycle.md` §8.2, `spec/architecture.md`
  audit table); the submit acknowledgement is not queued
  (`invitations.queue_responses_received`).

### `invitation_send`

- **Hides:** the Invitations page's per-row actions, which read *Shared by
  {application}* (`spec/operations_pages.md` "On a linked session").
- **Refuses:** the per-row Send, Regenerate, and Regenerate all (`409`).
- **Holds:** the application shares the session link; per-reviewer tokens
  are not needed (a token link only stamps *opened*).

### `instrument_structure`

Which instruments exist and their owned parts (`spec/instruments.md`
"A linked instrument").

- **At the create** (`app/services/linked_instruments.py`): the files must
  make exactly one instrument (else `422 invalid_setup`, `reason`
  `one_instrument`). Review Robin then fixes its assignment rule, not
  sent: Link 1 *All*, Link 2 `pair_context.tag1 IS FILLED`, Link 3
  *Individual*, every link marked set (assign where a relationship
  exists; the application fills the tag on every pair it sends). Its
  display fields start at Name, Email (the fixed pair) and Profile (the
  dossier link, `ProfileLink`); the short label follows the instrument's
  name, cut to 32 characters.
- **Hides:** *+Instrument*, *Replicate*, *Delete* and *+Page break*.
- **Refuses (`409`, `refuse_linked_structure`):** add, replicate, delete,
  page break, the response-field rows and the identity routes. The
  card's Save and the Band 2 save succeed but ignore the rule, identity
  and response fields and write the rest.
- **Holds as sent:** the instrument's name and description, and its
  response fields in the application's order (key, label, response and
  data type, bounds, options, help text and its visibility, visible).
  Whether a field is required is the application's. A field is never
  branched.
- **Shown fixed:** the description renders as text, never an edit box;
  Band 1, the response-field table, the short label and the description
  are muted regions (`data-linked-fixed`, inert even on an unlocked card)
  whose chips are fixed chips (`spec/ui_elements.md` §9).
- **Held display fields:** Profile stays as it stands: both Band 2 saves
  keep it (`hold_profile`) and the per-field display routes refuse it. The
  relationship's tag (`pair_context.*`) is never shown: Prepare's seeds
  add none, and `repair_display_fields` switches off a shown row, audited
  as an `instrument.display_field_updated` with no actor.
- **Stays Review Robin's:** the other display fields and their sort,
  layouts, column widths, card color and visibility.
- **On a re-send:** the instrument rows above are owned (an other row is
  `not_owned`), a draft of other than one instrument refuses them, and the
  reviewee save seeds no display field.

## Coupled locks and limits for reuse

- **`invitation_send` is meant to travel with `email`.** `email` refuses
  the bulk sends and reminders; the per-row Send and Regenerate are
  `invitation_send`'s. Either alone leaves a way to send Review Robin
  email, or to rotate tokens, that the other half hides.
- **`session_details` should accompany the owned session fields.** A
  re-send rewrites them, so a profile that owns them without the lock lets
  an operator edit values the next re-send overwrites.
- **`instrument_structure` assumes the application sends pairs:** one
  instrument per gate, a Relationships file with the tag filled, and
  Review Robin's fixed rule. An application that sends no pairs, or sends
  several instruments, takes a different profile and not this lock as it
  stands.
- **`owned_settings` is per profile but uniform today**; the tags are
  owned when it names `session_tags`.
- **`observers` also governs the handoff's refusal** of an `observers`
  file, so a profile without it accepts one.

## Profiles

| Application (`source_app`) | Name shown | Locks | Owned settings |
|---|---|---|---|
| `applydesk` | Apply Desk | all nine | `SESSION_FIELDS`, plus the instrument rows |
| `utilities` | Utilities | all nine | `SESSION_FIELDS`, plus the instrument rows |

`utilities` is the interop proof of concept (`utilityapps/spec/utilities.md`)
and links as Apply Desk does.

## How to add an application

1. Add a `LinkedProfile` to `LINKED_APPS` in
   `app/services/linked_apps.py`, naming the `Lock` members it takes (the
   default is all) and its `owned_settings` if they differ.
2. Add its row to **Profiles**.
3. Add tests: a session linked to the new key refuses each lock it takes
   and still allows each it leaves; `tests/unit/test_linked_sessions_spec.py`
   fails on a profile with no row here.

A new `Lock` member needs a gate, a section under **The locks** and a
test; the same unit test fails on a member this page does not name.

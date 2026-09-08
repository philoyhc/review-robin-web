# Segment 19H — Additional refinements

**Opened:** 2026-09-08 · **Theme:** operator-facing refinements found by
using the app · **Related:** `guide/archive/segment_19G_post_assessment.md`
(the segment this follows), `spec/instruments.md`

**A named scope, not a standing home.** 19C ran nineteen days as a
holding segment and produced a plan nobody read; 19G replaced that shape
with a finite scope and a close trigger, and closed at ten items the same
day. This segment keeps 19G's shape: items are admitted only from
**operator-facing refinements found by using the app**, each carries its
own evidence, and the segment closes when the queue empties or at the
next assessment snapshot, whichever comes first. Work that is not that
gets its own segment.

Items close independently, so each carries its own `### Doc impact` and
`### Status` and there is no segment-level `## Doc impact`.

### Items

| Item | Covers | State |
|---|---|---|
| **19H.1** | The card's two setup pills go stale after an AJAX Save | Open |
| **19H.2** | A locked instrument card must carry no unsaved edits | Open |
| 19H.3+ | Admitted only for operator-facing refinements found by using the app. | Open — **empty** |

---

## Item 1 — The two setup pills go stale after Save

### Opportunity

The instrument card's **`Set up` / `Not set up`** pill does not change
when the operator saves the card. Reported from use, 2026-09-08;
reproduced from the code.

The pill is server-rendered from
`is_configured_by_instrument[instrument.id]`
(`app/web/views/_instruments.py:737`), which calls
`instruments_service.is_configured`
(`app/services/instruments/_instrument_crud.py:596`). That predicate is
true only when the instrument has at least one visible response field
**and** all three Band 1 links have been touched — and **both of those
are edited on that very card**. So the pill's inputs are exactly what a
save changes, and exactly what never gets re-read.

Nothing re-reads them because Save is deliberately reload-free. The
`dfsave-*` form submit is intercepted
(`instruments_index.html:3603`), `preventDefault`ed, and sent as a
`fetch` to `/save` (`:3616`). The endpoint returns
`JSONResponse({"ok": True})` and nothing else
(`app/web/routes_operator/_instruments.py:940`), and
`newModelOnSaveSuccess` (`:3554–3570`) clears the dirty flag, resets
Save/Cancel and drops the error banner — there is nothing in the
response for it to update a pill *with*.

**Two pills go stale, not one.** `instruments_index.html:278` includes
`operator/partials/session_setup_status_row.html`, whose Instruments
pill (`:82–84`) is the **aggregate** "every instrument is set up" state
from `configured_counts`
(`_instrument_crud.py:625`). One card's save can flip that too. Fixing
only the card pill would leave the two visibly disagreeing on the same
screen, which is worse than both being stale together.

**It is JS-path-only.** The no-JS fallback `/fields/save`
(`_instruments.py:490`) returns a `RedirectResponse` — a full page load,
both pills correct. The staleness arrived with Segment 18R Item 2 PR 3,
when the fetch replaced the redirect.

### Decision

**Both pills, save-triggered.** `/save` returns the freshly computed
state alongside `ok`, and `newModelOnSaveSuccess` swaps both pills.

Rejected: **live evaluation as the operator edits.** It would need
`is_configured`'s rule — one visible response field plus three touched
Band 1 links — reimplemented in the browser, giving two copies of a
predicate that must agree. That is the drift class this repository
spent Segment 19G conceding it cannot check, and it would be a
self-inflicted instance. Save-triggered also matches what the pill
*means*: state as persisted, not state as typed.

Rejected: **reloading the page on save.** It would fix both pills for
free, but it discards the reload-free editing 18R Item 2 built
deliberately, and would undo the card's scroll and open/closed state on
every save.

### Semantics

- **What the response carries.** `is_configured` for the saved
  instrument, and the session's `configured_counts` — both already
  one call each, computed after `db.commit()` so they read committed
  state.
- **Failure path unchanged.** A 422 still renders the validation
  banner; no pill moves, because nothing was saved.
- **The no-JS path stays as it is.** It reloads and is already correct;
  adding fields to a JSON response does not touch it.
- **The aggregate pill is a session-level fact** rendered from a
  partial shared with other pages. Only the copy on this page is
  updated, because only this page has a card that can change it without
  a reload.

### Judgment calls — decided

- **Extend the existing `/save` response rather than add an endpoint**
  (2026-09-08). A second round trip for a boolean the save already
  knows would be slower and could disagree with it.
- **Send the computed booleans, not the underlying counts**
  (2026-09-08). Sending `visible_field_count` and `touched_links` would
  put the predicate back in the browser, which is what the Decision
  rejects.

### Blast radius (measured)

At `14a3811c`:

| What | Where |
|---|---|
| card pill | `app/web/templates/operator/instruments_index.html:852–855` |
| aggregate pill | `operator/partials/session_setup_status_row.html:82–84`, included at `instruments_index.html:278` |
| save endpoint's return | `app/web/routes_operator/_instruments.py:940` (`{"ok": True}`) |
| save success handler | `instruments_index.html:3554–3570` |
| predicate + counts | `_instrument_crud.py:596` and `:625` |
| templates rendering the aggregate partial | 1 (`grep -rln session_setup_status_row app/web/templates`) |
| tests naming `is_configured` / `Not set up` | 3 files / 3 assertions (`grep -rln is_configured tests/`) |

### PR ladder

1. **PR 1 — the response fields, both pill swaps, and the tests.** One
   rung: the endpoint change is inert until the client reads it, and
   the client change is untestable until the endpoint sends it. Must
   not touch: `is_configured` itself, the no-JS `/fields/save` path, or
   the lock layer (that is Item 2).

### Definition of done

- Saving a card that becomes configured flips **both** pills with no
  reload; saving one that becomes unconfigured flips them back.
- A 422 save moves neither pill.
- Verified in a browser against a seeded database — the pill flip is a
  DOM effect the test suite cannot observe. Screenshot and viewport
  width in the PR body.
- `ruff check .` and `pytest -q -n auto` pass.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19H.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- None.

### Out of scope

- **The lock layer's dirty-state handling.** Item 2.
- **Live pill evaluation while editing.** See Decision.

### Doc impact

- `spec/instruments.md` — the per-card `Set up` / `Not set up` pill and
  the aggregate Instruments pill state that they refresh on Save
  without a reload, and that the predicate stays server-side (PR 1).
- `docs/status.md` — row at the close (PR 1).

---

## Item 2 — A locked card must carry no unsaved edits

### Opportunity

Flipping a Band 1 assignment-rule link, **not** clicking Save, then
clicking Lock, produces the confirm *"You have unsaved changes. Lock
anyway? Your changes will be lost."* Accepting it locks the card **with
the flipped value still displayed**.

Reported from use as "the flip persists despite not saving". The audit
below establishes the sharper version, confirmed by the author:
**nothing is persisted — and nothing is lost either.** The warning is
false in both directions.

`newModelTryLock` (`instruments_index.html:3497–3506`) confirms and then
calls `newModelSetLock(card, true)`, which sets attributes, marks the
lock regions `inert`, and — this is the part that produces the illusion
— **copies the edited values into the locked read-only view**, via
`newModelSyncTextViews(card)` and a Band 2 re-render. Its comment says
so deliberately: *"consistent with how the other controls keep their
edited state while locked."* Nothing reverts, and nothing POSTs. The
card then displays, in its locked and authoritative-looking state, a
value the database does not have.

**The author's rule, stated 2026-09-08: a locked card should not carry
any unsaved edits.** That is the invariant this item restores.

### Decision

**Make the warning true: on confirm, discard the edits and lock against
server state.** The copy already promises exactly this; the behaviour is
what disagrees with it, so the smaller and more honest change is to fix
the behaviour rather than reword the promise.

The mechanism already exists. **Cancel** (`newModelCancelEdits`,
`:3382`) discards by reloading the page so the form re-renders from
persisted state, preserving each card's open/closed layout and
suppressing the nav-away guard. Lock-on-a-dirty-card is that same
discard, reloading **without** `?editing=<id>` so the card returns
locked. Reusing it means one discard path, not two that must agree.

Rejected: **refuse to lock a dirty card**, requiring Save or Cancel
first — which is what the Unlock path already does to *other* cards
(*"Another instrument has unsaved changes. Save or cancel it before
editing this one."*, `:3538`). It satisfies the invariant and is
internally consistent, but it removes a legitimate exit: an operator who
has decided the edits were a mistake would have to click Cancel and
confirm a second dialog to reach the same place. The confirm already
offers that exit; it just has to honour it.

Rejected: **reword the warning to describe what happens today**
("changes stay on screen but are not saved"). It makes the sentence true
and the state no less confusing — a locked card showing unsaved values
is the defect, not the wording.

### Semantics

- **Clean card, Lock:** unchanged — no confirm, in-page lock, no
  reload.
- **Dirty card, Lock, cancel the confirm:** unchanged — nothing
  happens, card stays unlocked and dirty.
- **Dirty card, Lock, accept:** page reloads from persisted state; the
  card returns **locked** and clean; other cards' open/closed layout is
  preserved, as Cancel already does.
- **Collapse ⇒ lock** goes through the same `newModelTryLock`, so it
  inherits the fix rather than needing its own.
- **The no-JS path has no lock layer** and is unaffected.

### Judgment calls — decided

- **Discard rather than refuse** (author, 2026-09-08). See Decision.
- **Reuse Cancel's reload rather than reverting inputs in the DOM**
  (2026-09-08). A DOM revert would need to restore every control the
  card can edit — Band 1 links, Band 2 snapshot, response-field rows,
  title, description, help text — which is a second copy of "what the
  server rendered", and the first one to drift wins silently.

### Blast radius (measured)

At `14a3811c`. **The audit the author asked for, and its result: no
editable control on the card persists without Save.**

Every editable control stages into the per-card `dfsave-*` form. Band 2
looks like an exception and is not: `saveBand2State`
(`instruments_index.html:2474`) **stages** into the hidden
`band2_state_snapshot` input and marks the card dirty — its own comment
records that it replaced an immediate `/band2-state` POST, and that the
consolidated `/save` applies it.

Endpoints reachable from the card that **do** write immediately, all of
them discrete actions with their own button and their own page reload,
none of them an edit:

| Endpoint | Control |
|---|---|
| `/open`, `/close` | Open / Close this instrument (response collection) |
| `/delete` | Delete instrument |
| `/replicate` | Replicate |
| `/page-break/create`, `/page-break/delete` | +Page break / remove |

Endpoints that exist server-side but that **this card does not reach**
(0 URL references in the template): `/visibility`, `/identity`,
`/display-fields`, `/fields/add-row`. They are still exercised by tests,
so they are not dead — just not wired to this card. Command:
`grep -c "instruments/{{ instrument.id }}/<ep>" app/web/templates/operator/instruments_index.html`.

Client-side surface for the fix itself:

| What | Where |
|---|---|
| the confirm + lock | `instruments_index.html:3497–3506` |
| what lock does today | `newModelSetLock`, syncs text views on lock |
| the discard to reuse | `newModelCancelEdits`, `:3382` |
| other callers of the lock path | collapse ⇒ lock, and `newModelLockClick` |

### PR ladder

1. **PR 1 — dirty-Lock discards, and the tests.** Must not touch:
   the clean-card lock path, `newModelSetLock`'s inert/aria handling,
   the Unlock path's other-card resolution, or the pill work in Item 1.

### Definition of done

- Flip a Band 1 link, do not save, Lock, accept: the card is locked and
  shows the **persisted** value, not the flipped one.
- The same, but cancel the confirm: card stays unlocked and dirty.
- A clean card still locks in-page with no confirm and no reload.
- Verified in a browser against a seeded database, since every assertion
  above is a DOM effect. Screenshot in the PR body.
- `ruff check .` and `pytest -q -n auto` pass.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19H.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- None. The invariant was decided by the author during the
  investigation.

### Out of scope

- **The four card-unreachable endpoints.** `/visibility`, `/identity`,
  `/display-fields` and `/fields/add-row` are not wired to this card;
  whether they should be retired is a separate question with its own
  evidence, and the tests that exercise them are not proof either way.
- **The pill staleness.** Item 1.

### Doc impact

- `spec/instruments.md` — the card's lock contract states that locking
  a card with unsaved edits discards them, so a locked card never
  displays unpersisted state (PR 1).
- `docs/status.md` — row at the close (PR 1).

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
| **19H.1** | The card's two setup pills go stale after an AJAX Save | **Closed 2026-09-08** |
| **19H.2** | A locked instrument card must carry no unsaved edits | **Closed 2026-09-08** |
| **19H.3** | A night-mode Guide — the sixteen screencaps ship as light/dark pairs | **Closed 2026-09-09** |
| **19H.4** | A screencap replaced under the same name never reaches a cached reader | **Closed 2026-09-09** |
| **19H.5** | A "Fields with data" pill that names a CSV column instead of the column | **Closed 2026-09-09** |
| 19H.6+ | Admitted only for operator-facing refinements found by using the app. | Open — **empty** |

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
| templates rendering the aggregate partial | ~~1~~ **15** (`grep -rln session_setup_status_row app/web/templates`) — the planning-time count was wrong; see `### Status` |
| tests naming `is_configured` / `Not set up` | 3 files / 3 assertions (`grep -rln is_configured tests/`) |

### Status

**2026-09-08 — Item 1 built and landed.** One PR, as the ladder
intended; no rung struck.

**The blast radius was wrong in one row, and it mattered.** The plan
recorded **1** template rendering
`operator/partials/session_setup_status_row.html`. It is **15** — every
operator session page includes it. The command in the table is right;
the number written beside it was not what that command returns. The
consequence is that `data-instruments-configured-pill`, added for the
Instruments page alone, now ships on fifteen pages. It is inert
everywhere else (the repaint helper only exists on the Instruments
page), so the decision stands rather than being reworked into a
page-scoped hook — but it is a wider surface than the plan bought, and
the row above is annotated rather than quietly corrected. Two tests in
`tests/integration/test_band1_not_set_gate.py` assert the aggregate
pill's exact markup and had to be updated for the new attribute; that
is the 15-page surface showing up immediately.

**A first cut of the wiring test asserted nothing.** It checked
`"data-instrument-setup-pill" in body` and
`"data-instruments-configured-pill" in body`. Both passed with the
attributes deleted from *both* templates, because the repaint helper's
own selector strings (`'[data-instrument-setup-pill]'`) put the same
substring in the page. Found by mutation, not by reading. The
assertions now pin the markup context
(`data-instrument-setup-pill>Not set up</span>`,
`data-instruments-configured-pill>`), and all four mutants die: reverting
the endpoint to `{"ok": True}`, dropping either hook, and dropping the
repaint call.

**Decisions confirmed at build:**

- **`configured_counts` unpacked into two keys for the aggregate, not a
  second boolean** (2026-09-08). The response carries
  `instruments_configured` and `instrument_count`, not a
  `configured_counts` field. The aggregate pill *displays* both numbers,
  so it needs them regardless; sending a separate "all configured" flag
  would add a value that could disagree with the numbers beside it. The client
  mirrors the template's three-branch formatting (none / blue / amber)
  and nothing else.
- **The `/save` response is now four keys, not one.** Four existing
  tests asserted `response.json() == {"ok": True}` exactly; each was
  narrowed to `response.json()["ok"] is True`, since none of them is
  about the response's shape.

**Verified in a browser** (Chromium 1440×900, seeded SQLite, fake
auth), one page load throughout — `performance.getEntriesByType(
'navigation').length === 1` after every save:

| Action | Card pill | Aggregate pill |
|---|---|---|
| page load, nothing configured | `Not set up` amber | `0 / 2` amber |
| the three Band 1 link pills clicked, **not** saved | `Not set up` amber | `0 / 2` amber |
| Save | **`Set up` blue** | **`1 / 2` amber** |
| second instrument configured + saved | `Set up` blue | **`2 / 2` blue** |
| first instrument's touched links cleared + saved | **`Not set up` amber** | **`1 / 2` amber** |

The row that stays amber at `1 / 2` while the card goes blue is the
point of fixing both together: the aggregate is a different question
from the card's, and now both answer correctly at the same instant.

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

### Status

**2026-09-08 — Item 2 built and landed.** One PR, as the ladder
intended; no rung struck, and the blast radius held (unlike Item 1's).

**The old behaviour was reproduced before it was replaced.** Rather
than trust the reading of `newModelSetLock`, the pre-fix template was
run in the browser through the same scenario. Accepting *"Your changes
will be lost"* left the card `data-instrument-locked="true"` **and**
`data-instrument-dirty="true"`, with the flipped `All` pill on display
and **Save still enabled on a locked card** — that last part was not in
the plan's account of the defect and is the sharpest statement of it: a
locked card was carrying a live, enabled Save for edits it claimed to
have discarded. After the fix the same scenario ends locked, clean, and
showing `Not set`.

**"No reload" needed a different instrument than Item 1's.** A
navigation counter cannot prove a page did *not* reload, because the new
document's counter starts at 1 too. A `window.__survives_reload` marker
set before the click answers it directly: it survives the clean-card
lock (in-page, as before) and is gone after the dirty-card discard
(reloaded, as intended).

**Decisions confirmed at build:**

- **The discard is factored out, not duplicated** (2026-09-08).
  `newModelDiscardReload(keepEditingId)` now holds the nav-away
  suppression, the open-state capture, the hash and `saved` stripping,
  and the reload; Cancel passes the card id, the dirty lock passes
  `null`. The plan said "reuse Cancel's reload" and this is what reuse
  had to mean — the alternative, calling `newModelCancelEdits` from the
  lock path, would have fired Cancel's *own* second confirm.
- **`newModelTryLock` still returns `true` on the discard path**
  (2026-09-08). Its contract is "did the card end up locked", and it
  did — after the reload. Returning `false` would make collapse ⇒ lock
  re-expand the card a moment before the page went away.
- **A dirty card's URL may not carry `?editing` at all.** Unlock is
  in-page and does not rewrite the URL, so the discard has to handle
  "already absent": `url.href === window.location.href` then falls
  through to `location.reload()`, which re-renders the card locked
  because the server has no `editing` param to honour. Verified in the
  browser, not only read.

**Three spec passages went stale on this change and are fixed with it**
— found by re-reading `spec/instruments.md` for the *consequences* of
the fix rather than for the paragraph it obviously touched:

- The card-title bullet said `newModelSetLock` syncs the view span "so
  the collapsed title reflects an **unsaved-then-locked rename**". That
  state no longer exists; the sync now only ever copies persisted
  values.
- The collapse ⇒ lock invariant said collapsing runs "the usual
  dirty-change confirm" without saying what accepting does, which was
  survivable while accepting did nothing and is not now.
- **The third was found by `spec-writer`, not by me**: Band 2's
  **Description** bullet carried the *identical* staleness the title
  bullet had, and for the identical reason — `newModelSyncTextViews` is
  one function serving both views, so a passage describing either
  described both. I corrected the copy I had gone looking for and
  missed its twin nine sections away. That is the value of the pass
  being a separate reader rather than the same one twice: a
  consequence-hunt anchored on the paragraph you edited finds the
  paragraphs like it, not the paragraphs sharing its mechanism.

**Verified in a browser** (Chromium 1440×900, seeded SQLite, fake auth),
each row a separate run:

| Scenario | Result |
|---|---|
| clean card, Lock | no confirm, locks in place, marker survives — no reload |
| dirty card, Lock, **decline** | unchanged: unlocked, dirty, `All` still shown |
| dirty card, Lock, **accept** | locked, dirty flag cleared, links back to `Not set`, `?editing` dropped, marker gone |
| the same on the **pre-fix** template | locked **and** dirty, `All` on display, Save still enabled |

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

---

## Item 3 — A night-mode Guide

### Opportunity

The Guide's sixteen screencaps are light-theme images on a page that
has a dark theme. The app's theme is two-state and explicit —
`data-theme="dark"` on `<html>`, Light being the bare `:root`,
persisted in `localStorage["rrw-theme"]`, with **no OS-follow**
(`spec/settings_inventory.md`, and `base.html`'s own comment: "Two-state
model: Light is the bare `:root`; there is no `prefers-color-scheme`
block") — so a reader who chooses Dark gets a dark page carrying
sixteen bright rectangles.

**The current design already concedes this in writing.**
`spec/ui_elements.md` §`.guide-figure` says: *"Dark theme is where the
mat earns its keep twice over. The captures are light-theme images, so
on a dark page they are bright blocks whatever their border does; the
dark mat frames them instead of letting them glare off the ground."*
The mat is a mitigation for a defect the spec names and could not then
fix, because there was one capture set. There are now two: the author
has supplied a complete dark set of all sixteen, in the Guide's own
figure order.

Measured at `cf96319a`: sixteen figures, **607,530 bytes** of light
captures (`du -sb app/web/static/guide/`); the dark set is **603,913
bytes**, so the static directory roughly doubles to ~1.18 MB.

### Decision

**Two `<img>` per figure, one hidden by CSS keyed on
`:root[data-theme="dark"]`, both `loading="lazy"`, dark files in the
same flat directory under a `-dark.png` suffix.**

Four CSS rules against the existing `.guide-figure img` and a second
`<img>` per `<figure>`. It is correct at first paint (the no-FOUC head
script sets `data-theme` **before** the body is parsed) and correct on
live toggle (the toggle flips the attribute; CSS re-evaluates), with no
JavaScript of its own.

Rejected: **`<picture>` with `prefers-color-scheme`**, the textbook
answer. It reads the OS, and this app deliberately does not — a reader
in the app's Dark theme on a light OS would be served the light
captures, which is the defect with extra machinery. The signal the page
uses is an attribute, and only a selector can read it.

Rejected: **choosing server-side from a cookie.** The toggle flips the
theme *without a reload*, so a server-chosen `src` is stale the instant
anyone toggles; and it would end the "browser-local only — never synced
to the server" property the theme was given on purpose.

Rejected: **CSS `background-image` on the figure**, which fetches only
the applied image and so avoids the double download. It costs real
`alt` text (`role="img"` + `aria-label` is equivalent for a screen
reader but not for a broken image or for find-in-page), and it forces a
rewrite of `test_guide_screencaps.py`'s literal-`src` grep — whose own
guard, `assert len(REFERENCED) >= 12`, exists precisely because "if the
paths are ever templated rather than literal, the regex silently finds
nothing and every case below passes vacuously". Paying the transfer is
cheaper than trading a real check for a nominal one.

Rejected: **swapping `src` in JavaScript** from the existing `apply()`.
The images are parsed after the head script runs, so a dark reader gets
a flash of light captures before the swap, and a no-JS reader gets
whichever set the markup happened to name.

### Semantics

- **First paint.** The no-FOUC script is synchronous in `<head>`, so
  `data-theme` is already on `<html>` when the `<img>`s are parsed. The
  correct one is visible from the first frame; there is no flash.
- **Live toggle.** `apply()` sets or removes the attribute; the CSS
  re-evaluates. No hook, no listener, nothing to keep in step.
- **No JS, or storage blocked.** Stays light, because light is the copy
  with no hiding rule — the same default the whole theme system takes.
- **Both copies carry the same `alt`.** They are pictures of the same
  UI; the theme is not a fact about the app's behavior. Only one is in
  the accessibility tree at a time (`display: none` removes the other),
  so there is no double announcement.
- **A missing dark twin** shows an empty figure in Dark. That is
  prevented by the pairing check below, not by a runtime fallback: a
  fallback would hide exactly the mistake worth failing on.
- **Transfer cost.** Both copies are fetched where they render.
  `loading="lazy"` on both means a reader who stops after the third
  figure fetches six images, not thirty-two.

### Judgment calls — decided

- **`-dark.png` suffix in the flat directory, not a `dark/`
  subdirectory** (2026-09-09). The suffix makes **every existing check
  extend to the dark set for free**: `test_guide_screencaps.py` collects
  from `STATIC_GUIDE.iterdir()` filtered by `p.is_file()`, so a
  subdirectory's contents are invisible to `committed` while
  `src="/static/guide/dark/x.png"` *is* captured by `REFERENCED` — the
  `committed == set(REFERENCED)` equality would fail and have to be
  rewritten. Flat and suffixed, the served / unreferenced / alt-text /
  capture-family cases all run over 32 files instead of 16 with no
  change at all.
- **Keep the mat** (2026-09-09). Its second job goes away; its first —
  *"these are pictures of this app rendered inside it"* — does not, and
  is the reason it exists. `spec/ui_elements.md` loses the paragraph
  about glare, not the mat.
- **No `figcaption` changes.** Out of scope; the figures caption
  nothing today.

### Blast radius (measured)

At `cf96319a`:

| What | Measured | Command |
|---|---|---|
| figures in the Guide | 16 | `grep -c 'src="/static/guide/' app/web/templates/guide.html` |
| of those, narrow-family | 6 | `grep -c 'guide-figure-narrow' app/web/templates/guide.html` |
| CSS rules to extend | 4 (`base.html:1197`, `:1207`, `:1228`, `:1240`) | `grep -n "guide-figure" app/web/templates/base.html` |
| light captures on disk | 607,530 bytes | `du -sb app/web/static/guide/` |
| dark captures supplied | 603,913 bytes, 16 files | measured from the docx |
| screencap test cases today | 52 | `pytest --collect-only tests/integration/test_guide_screencaps.py` |
| specs naming the captures | 2 (`spec/ui_elements.md` ×3 lines, `spec/architecture.md` static-assets ¶) | `grep -rn "static/guide\|screencap" spec/` |

**The capture-family check already covers the dark set, and it passes.**
`test_narrow_captures_carry_the_narrow_figure_class` splits on actual
pixel width at `NARROW_MAX_WIDTH = 1000`, so a dark twin shot at the
other scale fails rather than rendering wrong. Measured across all
sixteen pairs: **every dark twin lands in its light twin's family** —
6 narrow / 10 wide on both sides — and every height matches within
±4px, consistent with a pure re-shoot.

**One pair is not a like-for-like re-shoot**, and the height outlier is
what found it: `instrument-card-preview` is 1758×893 light against
1756×**777** dark. Read side by side, the dark capture is missing the
`↻ Refresh sample` button, the `Pair context 1` column, the column sort
arrows, and the Rating / Comments input boxes. It is a different app
state, not a different theme. See Open questions.

### Status

**2026-09-09 — Item 3 built and landed.** One PR, as the ladder
intended; no rung struck, and the blast radius held.

**The open question was answered before the build started.** The dark
`instrument-card-preview` capture arrived re-shot: 1756×**890** against
its light twin's 1758×893, with the `↻ Refresh sample` button, the
`Pair context 1` column, the sort arrows and the input boxes all
present. Every one of the sixteen pairs is now within ±4px of height
and in its light twin's capture family. One residual difference, noted
and not acted on: the dark preview's card title reads `#1: Group Peer
Review` where the light one reads `#1`, because the instrument is named
now — the *light* capture is the older of the two, and the difference
is one line of a title rather than a missing control.

**The `-dark.png` suffix paid exactly what the plan said it would.**
Adding sixteen files and thirty-two `<img>` tags took the screencap
suite from **52 cases to 100 with no change to the test file at all** —
served, unreferenced, alt-text and capture-family all re-ran over both
halves. Only then were the new pair checks added, taking it to 134.

**A first cut of the CSS wiring test asserted the wrong thing.** It
ended with `assert "prefers-color-scheme" not in css`, and failed —
because `base.html` names the string twice in **comments**, once in the
pre-existing note saying the app deliberately has no such block and
once in the comment this item added saying the same. An assertion that
fails on prose explaining the rule is an assertion someone deletes, so
it now matches `@media[^{]*prefers-color-scheme` — the thing actually
forbidden. Second time in this segment that a first-cut assertion was
about the wrong text (Item 1's was satisfied by a JS selector string).

**And a verification probe measured the wrong thing too**, which is
worth recording because the number looked plausible. The no-JS check
counted `data-theme-variant="light"` / `"dark"` substrings in the served
document and reported **17 and 18** for sixteen figures, and read
`data-theme="dark"` as present on a page with JavaScript disabled. Both
were the *stylesheet* matching: the CSS contains the selectors and
`:root[data-theme="dark"]`. Re-done against the `<html>` open tag and
`<img>` tags only: root carries no `data-theme`, 16 light and 16 dark
`<img>`s. The lesson is Item 1's, in a third costume — a substring
search over a document that contains its own CSS is not a search over
the markup.

**The `spec-writer` pass found a stale count this item did not
create.** `spec/ui_elements.md` said the captures arrive "six 1× shots
at ~830px and six 2× at ~1680px" and pinned "the wide **six**" at
1200px. Measured: **6 narrow, 10 wide**. Checked against history rather
than assumed — twelve captures landed 2026-09-07 in a genuine 6/6
split, and the four `instrument-card-*` captures added 2026-09-08 are
all wide (1753–1758px), so the sentence went stale the day after it was
written and stayed that way through two segments. Corrected with the
date the split moved, since six-and-six was true when written. Nothing
derives from the number — the test splits on measured pixel width —
which is exactly why nothing caught it. **The same sentence appears
twice more**, in the test file's own header comment and, for the mat's
second job, in `base.html`; both are corrected here, because a spec
fixed while the two comments it was written from still say the old
thing is half a fix.

**Decisions confirmed at build:**

- **`loading="lazy"` on both copies** (2026-09-09). Both are fetched
  where they render, so the offscreen fourteen figures cost nothing
  until scrolled to.
- **The new CSS sits between the base `img` rule and the
  `.guide-figure-narrow` modifier** (2026-09-09). `spec/ui_elements.md`
  requires the modifier to stay *after* the base rule, since equal
  specificity makes source order decide; the swap rules set `display`
  and the modifier sets `width`, so they do not compete, but the order
  the spec names is preserved rather than relied on not to matter.

**Verified in a browser** (Chromium 1440×1000, the real `/guide` page):

| Scenario | Result |
|---|---|
| fresh viewer, no stored choice | 32 `<img>`, 16 visible, all `light` |
| toggle to Dark, no reload | 16 visible, all `dark`; a `window` marker set before the click survives |
| fresh load with `rrw-theme=dark` stored | 16 visible, all `dark` from the first frame |
| JavaScript disabled | `<html>` carries no `data-theme`; 16 light + 16 dark `<img>` tags served; the unconditional dark-hide rule applies, so the light set shows |
| all 32 files requested | no non-200 response under `/static/guide/`, no visible image failed to decode |

### PR ladder

1. **PR 1 — the sixteen dark captures, the markup, the CSS, and the
   pairing test.** One rung: the files are unreferenced dead weight
   until the markup points at them (and the existing test fails on
   exactly that), and the markup is broken until they exist. Must not
   touch: the mat's own rules, the two family widths, the capture
   filenames of the light set, or `NARROW_MAX_WIDTH`.

### Definition of done

- In Dark, every figure shows its dark capture; in Light, its light
  one; toggling flips all sixteen with no reload and no flash.
- With JavaScript disabled the page renders the light set.
- `tests/integration/test_guide_screencaps.py` runs its existing cases
  over 32 files, plus a new case asserting every light capture has a
  `-dark` twin and vice versa.
- Verified in a browser at both themes against a running app —
  every assertion above is a rendering property the suite cannot see.
  Screenshots of one figure in each theme in the PR body.
- `ruff check .` and `pytest -q -n auto` pass.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19H.3` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- ~~**The `instrument-card-preview` dark capture is of a different app
  state** (see Blast radius). Ship the pair as-is and that one figure
  shows different UI depending on the theme — the same drift Item 1's
  first light/dark pair had, caught here before it landed rather than
  after. **Decided by the author**: re-shoot it against the same state
  as the light capture, or replace both with a matched pair. Everything
  else in the set is ready.~~ **Answered 2026-09-09** — re-shot, and
  the pair now matches within 3px of height. See `### Status`.

### Out of scope

- **Retiring the mat.** Its second job ends; its first does not. See
  Judgment calls.
- **A print stylesheet.** The app has none; dark captures in a printout
  are a question that arrives with printing, not with this.
- **Dark captures anywhere else.** The Guide is the only page with
  screencaps — `app/web/static/guide/` is the whole static surface.

### Doc impact

- `spec/ui_elements.md` — the `.guide-figure` section states that the
  captures ship as light/dark pairs selected by `data-theme`, and the
  paragraph justifying the mat as glare protection is replaced by the
  reason the mat survives without that job (PR 1).
- `spec/architecture.md` — the static-assets paragraph records that the
  directory now carries paired captures and that the screencap test
  checks the pairing, alongside the two failure modes it already names
  (PR 1). The theme mechanism itself is unchanged, so
  `spec/settings_inventory.md`'s `rrw-theme` entry is not edited — it is
  named here only as the contract this item reads
  <!-- cites: spec/settings_inventory.md -->.
- `docs/status.md` — row at the close (PR 1).

---

## Item 4 — A replaced screencap that never arrives

### Opportunity

Reported from use the day Item 3 landed: the two Guide screencaps
refreshed in `cf96319a` still showed their **old** pictures, while the
sixteen dark captures added hours later appeared at once.

Both halves of that are the same fact. The dark captures are **new
URLs**, never in anyone's cache, so they must be fetched. The two
refreshed captures kept **the same URL**, so a stored copy could answer
without a request. Confirmed by the author from the app: the same path
with `?v=2` — a URL the cache has never seen — returns the new picture.

The mechanism is a missing header. `StaticFiles` sends `etag` and
`last-modified` and **no `Cache-Control`** (`grep -rn "Cache-Control"
app/` returns nothing), which leaves freshness to the browser's
heuristic: with no stated lifetime a stored copy may be reused for a
fraction of its age without asking the server at all.

**Measured, because the first attempt at measuring it failed.** A
browser driven against a local server picked up a replaced capture
immediately, on both reload and navigation — which looked like a
refutation and was not. Files written seconds earlier have almost no
age, so the heuristic lifetime is almost zero and the browser asks
anyway. Ageing the file ten days before the first visit reproduces the
defect exactly.

### Decision

**Send `Cache-Control: no-cache` from the static mount**, via a
`StaticFiles` subclass that sets the header in `file_response`.

`no-cache` is store-and-revalidate, not do-not-store: the browser keeps
the file and keeps sending `If-None-Match`, so an unchanged capture
still answers 304 with no body and the saving that matters survives.
What goes is the window in which the browser does not ask.

Rejected: **fingerprinted filenames** (`assignments-page.a1b2c3.png`)
with a long `max-age`, the usual answer and a better one for a real
asset pipeline. `spec/architecture.md` says this directory is
deliberately not one — "nothing here is compiled, fingerprinted, or
versioned" — and buying cache-friendliness with a build step is the
trade that paragraph exists to refuse.

Rejected: **a short `max-age`**. It replaces an unbounded stale window
with a bounded one, which is the same defect with a smaller number; and
the number would have to be argued about.

Rejected: **doing nothing and hard-refreshing.** It works, and it asks
every future reader to know that a picture they are looking at may be a
picture of something else.

### Semantics

- **Unchanged capture:** conditional request, 304, no body. `304` keeps
  `cache-control` (it is in Starlette's `NotModifiedResponse` header
  allowlist), so the next visit revalidates too.
- **Replaced capture:** the validator no longer matches, so the same
  conditional request returns 200 with the new bytes.
- **Applies to the whole `/static` mount**, not just `guide/`. It is one
  directory of PNGs; a per-directory rule would be a policy with one
  case and two places to look.
- **Nothing else changes.** No route, no template, no capture.

### Judgment calls — decided

- **Set the header after `super().file_response(...)`** (2026-09-09).
  That method builds the 200 and then swaps in a `NotModifiedResponse`
  for a 304; setting it afterwards lands on whichever came back, where
  setting it on the `FileResponse` first would rely on the allowlist
  copying it across.
- **A subclass, not middleware** (2026-09-09). The rule is a property of
  serving files from this mount, and a middleware would have to
  re-derive which responses it applies to from the path.

### Blast radius (measured)

At `94b2f3e5`:

| What | Measured | Command |
|---|---|---|
| static mounts in the app | 1 | `grep -n "StaticFiles" app/main.py` |
| files it serves | 32 | `find app/web/static -type f \| wc -l` |
| `Cache-Control` anywhere in `app/` | 0 | `grep -rn "Cache-Control\|max-age" app/` |
| test files touching `/static` | 1 | `grep -rln "/static" tests/` |
| specs describing the mount | 1 (`spec/architecture.md`, Static assets ¶) | `grep -rn "static/guide\|StaticFiles" spec/` |

### Status

**2026-09-09 — Item 4 built and landed.** One PR, as the ladder
intended. The change is four lines; the work was establishing that they
were the right four.

**The first measurement said the opposite of the truth.** A browser
driven against a local server picked up a replaced capture immediately,
on a reload *and* on a plain navigation — so the caching account looked
refuted, and shipping a header on the strength of a story would have
been the thing to avoid. The flaw was in the experiment: the files it
served had been written seconds earlier, and heuristic freshness is a
fraction of the age since `Last-Modified`, so a brand-new file is never
reused without asking. Ageing the file ten days before the first visit
made the two configurations separate cleanly.

**An earlier reading was simply wrong and is recorded as such.** A first
probe reported that a reload kept showing the old image; instrumented
properly, that same reload sent `If-None-Match`, got a 200 with the new
bytes, and rendered them. The probe had sampled `naturalWidth` before
the lazy-loaded image re-decoded. It briefly pointed at "the server
lies", which it does not.

**A/B against the same browser, same aged file, same navigation:**

| Mount | `cache-control` served | After the file is replaced |
|---|---|---|
| `StaticFiles` (before) | *(none)* | **stale — the old picture** |
| `_RevalidatingStaticFiles` (after) | `no-cache` | **fresh — the new picture** |

That is the reported defect reproduced and then fixed, rather than
inferred from the header's meaning.

**One of the three tests passes with or without the fix, deliberately.**
`test_a_replaced_screencap_is_served_fresh` pins the *server* half — a
changed file must stop matching the old validator — which was never
broken and is what the failed first measurement briefly cast doubt on.
It is a regression pin on the half the header does not control, and it
is worth having precisely because that half was doubted. The other two
die under all three mutants (subclass reverted, header set only on the
200 branch, `no-cache` swapped for a long `max-age`).

**The `spec-writer` pass changed nothing and confirmed one thing worth
having.** It re-derived the header's placement, the literal `no-cache`,
the unchanged mount and directory, and that "nothing here is compiled,
fingerprinted, or versioned" still holds of a change that adds a
response header rather than a build step. It also read the deployment
docs against this item's open question and found no claim anywhere that
the change falsifies — plus the topology line that narrows the question,
now recorded under `### Open questions`.

**Decisions confirmed at build:**

- **The whole `/static` mount, not just `guide/`** (2026-09-09). One
  directory of PNGs; a per-directory policy would have one case and two
  places to look.
- **Set after `super()`** (2026-09-09), so the header lands on the 200
  and the 304 alike rather than relying on `NotModifiedResponse`'s
  allowlist to carry it — though it does carry it, which is why the 304
  test passes.

### PR ladder

1. **PR 1 — the header, the tests, and the spec.** One rung; the change
   is four lines. Must not touch: the captures, the Guide markup, the
   figure CSS, or the mount's path.

### Definition of done

- A capture replaced under the same filename reaches a reader who has
  the old one cached, demonstrated against a browser holding a stored
  copy — not argued from the header alone.
- An unchanged capture still answers 304 with no body.
- `ruff check .` and `pytest -q -n auto` pass.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19H.4` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- **Whether anything between the app and the reader caches too.** The
  header instructs whatever honours it; a CDN or proxy in the deployed
  path is outside this sandbox's reach and outside this item. If a
  replaced capture is still stale on the dev slot after this ships,
  that is the next thing to look at, and it is a deployment question
  rather than an application one. **Narrowed at the close** (the
  `spec-writer` pass, 2026-09-09): the deployment docs record "No Front
  Door / CDN, no Static Web App", so on the documented topology nothing
  sits between App Service and the browser to cache independently.
  **Answered from the deployed app, 2026-09-09**: no intermediary. A
  fresh Chrome profile showed the new captures at once while Edge kept
  the old ones through a hard refresh, and clearing Edge's cache fixed
  it — the stale bytes were one browser profile's stored entry, created
  **before** the header shipped and therefore still governed by the old
  heuristic rules. The fix stops new stale entries; it cannot reach one
  already saved, which is worth knowing the next time a capture is
  replaced and someone reports it twice.

### Out of scope

- **Fingerprinting, and any asset pipeline.** See Decision.
- **Any other response's caching.** HTML responses are uncached by
  default here and no one has reported otherwise; widening this to the
  whole app would be a policy nobody has needed.

### Doc impact

- `spec/architecture.md` — the static-assets paragraph records that the
  mount sends `Cache-Control: no-cache`, why (a replaced file under an
  unchanged name), and that fingerprinting stays refused (PR 1).
- `docs/status.md` — row at the close (PR 1).

---

## Item 5 — A pill that names a CSV column instead of the column

### Opportunity

Reported from use, 2026-09-09. The "Fields with data" pills on the
three Setup pages are supposed to read what the page's own preview
table heads that column — `views.friendly_fields_with_data`'s docstring
says so. Measured against a seeded session, two of the three pages
disagree with their own tables:

| Page | pills today | preview headers |
|---|---|---|
| Reviewers | `ReviewerName`, `ReviewerEmail`, `Tag 1` | `Name`, `Email`, `Tag 1` |
| Reviewees | `Name`, `Email`, `Tag 1` | same — correct |
| Relationships | `ReviewerEmail`, `Email`, `Pair context 1` | `Reviewer`, `Reviewee`, `Pair context 1` |

**One gap with two faces.** The mapping can only reach the 12
*renamable* field-label slots. `ReviewerName` / `ReviewerEmail` have no
slot, so they fall through to the raw CSV name beside columns headed
`Name` and `Email` — behaviour the spec currently documents as intended,
naming those two columns explicitly. `RevieweeEmail` *does* have a slot,
and on Relationships resolves to the reviewee page's `Email` beside a
column headed `Reviewee` — the right label resolved on the wrong page.

So the same CSV column has **two correct pill texts** depending on which
page is asking, which the mapping's signature cannot express.

### Decision

**Give the mapping the page.** A per-surface label table, consulted
*before* the renamable slots, keyed by a required keyword-only
`surface`.

Before, not after, because the per-page label mirrors a **fixed**
preview header: Relationships heads its identifier columns `Reviewer`
and `Reviewee`, which is a different question from what the reviewee
page calls its identifier column.

Required and indexed (`_SURFACE_LABELS[surface]`, not `.get`), because
a page that forgets the argument or misspells it should raise rather
than quietly render CSV column names — which is this defect, and the
way a silent default would re-introduce it one page at a time.

Rejected: **making reviewer name / email renamable** so they resolve
like the rest. It grows the field-label surface to fix a display
string, and `spec/setup_pages.md` records the identity slots as
deliberately not overridable — the Reviewees page already resolves
`RevieweeName` / `RevieweeEmail` to builtin defaults that no operator
may change.

Rejected: **having each service return page-ready labels.** The
services return CSV column names on purpose — that is the CSV contract,
consumed by extracts and imports as well. Presentation belongs at the
view seam.

### Semantics

- **Reviewers** — `ReviewerName` → `Name`, `ReviewerEmail` → `Email`.
- **Relationships** — `ReviewerEmail` → `Reviewer`, `RevieweeEmail` →
  `Reviewee`. `Status` keeps its CSV name because the preview header is
  also `Status`.
- **Reviewees** — empty map; nothing changes, and the page is listed
  explicitly rather than omitted so the set of surfaces is closed.
- **Unknown surface** — `KeyError`, at the call site, on the first
  request.
- **Renamable slots are untouched.** A renamed tag still resolves
  through the field-label config on every page.

### Judgment calls — decided

- **`surface` names the page, not the entity** (2026-09-09). The CSV
  import error path serves reviewers *or* reviewees and already carries
  a `kind` that is exactly the page; passing it through needed no new
  concept.
- **The map is a module constant beside `_FIELD_LABEL_SLOTS`**
  (2026-09-09), because the two are read together and a reader who
  finds one needs the other.

### Blast radius (measured)

At `2e019030`:

| What | Measured | Command |
|---|---|---|
| callers of `friendly_fields_with_data` | 4 (3 page routes + the CSV-error path) | `grep -rn "friendly_fields_with_data" app/` |
| templates rendering the pill row | 3 | `grep -rln "Fields with data" app/web/templates` |
| tests asserting pill text | 3, all tag-slot or reviewee (none assert the two raw names) | `grep -rn 'pill pill-count' tests/` |
| specs describing the pills | 2 (`spec/setup_pages.md`, `spec/operator_ui_concept.md`) | `grep -rn "Fields with data" spec/` |
| `ReviewerName`/`ReviewerEmail` in tests | 230 occurrences, all CSV-contract | `grep -rn "ReviewerName\|ReviewerEmail" tests/` |

**Found and left alone:** the Assignments page builds a
`fields_with_data` context key that **no template reads**
(`grep -rn "fields_with_data" app/web/templates/operator/session_assignments.html`
returns nothing). Dead context, and a separate question — see Out of
scope.

### Status

**2026-09-09 — Item 5 built and landed.** One PR, as the ladder
intended. The blast radius held: four call sites, three templates
untouched, and **no existing test needed changing** — the three that
assert pill text all assert tag slots or the reviewee identity labels,
none the two raw names this item retires.

**A test I wrote described something that cannot happen, and failed for
that reason.** It claimed the per-page label protects the Relationships
pill from an operator renaming the reviewee email slot. `field_labels.
upsert` rejects that slot outright — the reviewee identity labels are
resolvable to builtin defaults but **not** overridable, which
`test_upsert_rejects_retired_reviewee_identity_slots` has pinned all
along. So the scenario was impossible and the test's premise was
fiction. Replaced with the invariant that is actually load-bearing —
one raw column, two surfaces, two answers — and **the same wrong claim
was corrected in the code comment**, which had said the header holds
"whatever the reviewee email slot has been renamed to". Caught by
running it, not by reading it.

**The `§N` check from 19G.7 caught the spec edit.** A first draft
pointed at `spec/setup_pages.md` §3, which is a numbered *list item*
inside `## Shared body shape`, not a section — the exact
unresolvable-without-guessing form 19G.5 rewrote elsewhere. Repointed
to `§"Shared body shape" item 3`, the idiom the repo already uses. The
check built two items ago earning its keep on the item that came after.

**The `spec-writer` pass found one drift and one regression of mine.**
The drift: `spec/setup_pages.md`'s "Implementation pointers" still
described the mapping as swapping renamable-slot columns for their
label, one file below the corrected account — fixed to name the
required `surface` and point at the three-source order rather than
restate it.

The regression is the same misconception a third time, and this time I
put it into a spec that had been right. The passage I rewrote said "one
of the **nine** renamable tag field-label slots"; I wrote "one of the
**12** renamable slots", taking the count from `_FIELD_LABEL_SLOTS`.
Twelve slots *resolve*; only **nine** are operator-renamable —
`_VALID_SOURCE_FIELDS` allows three reviewer tags, three reviewee tags
and three pair-context slots, and the three reviewee-identity slots
were retired as renamable on 2026-05-31, which `spec/csv_contracts.md`
and `spec/settings_inventory.md` both say correctly. So a correct
number was replaced with a wrong one in the same document that had it
right. Corrected in the spec and in the code comment, which now says
which nine and why that is exactly the reason `_SURFACE_LABELS` has to
exist: `RevieweeEmail` cannot be given a second word by renaming it.

**Three encounters with one fact in one item** — the impossible test
premise, the code comment, and the slot count — each caught by a
different reader: the test run, the test run again, and the
`spec-writer` pass. None by re-reading.

**Decisions confirmed at build:**

- **`surface=kind` on the CSV-error path** (2026-09-09). That handler
  already branches on a `kind` that is literally the page name, so the
  fourth call site needed no new plumbing.
- **Reviewees keeps an explicit empty map** (2026-09-09) rather than
  being absent, so the set of surfaces is closed and a typo raises.

**Verified against rendered pages**, since the pills are markup:

| Page | before | after |
|---|---|---|
| Reviewers | `ReviewerName`, `ReviewerEmail`, `Tag 1` | **`Name`, `Email`**, `Tag 1` |
| Reviewees | `Name`, `Email`, `Tag 1` | unchanged |
| Relationships | `ReviewerEmail`, `Email`, `Pair context 1` | **`Reviewer`, `Reviewee`**, `Pair context 1` |

Four mutants, each run and each killing a test: the reviewers map
emptied, the relationships map emptied, the surface consulted *after*
the renamable slots (which puts `Email` back on Relationships), and
`_SURFACE_LABELS.get(surface, {})` in place of the index.

### PR ladder

1. **PR 1 — the per-surface map, its four call sites, the tests and the
   two specs.** One rung: the parameter is required, so the call sites
   move with it. Must not touch: the services' CSV column names, the
   field-label config, or the preview-table headers.

### Definition of done

- Reviewers reads `Name`, `Email`; Relationships reads `Reviewer`,
  `Reviewee`; Reviewees is unchanged — asserted against rendered pages.
- A misspelled surface raises rather than falling back.
- `ruff check .` and `pytest -q -n auto` pass.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19H.5` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- None.

### Out of scope

- **The Assignments page's dead `fields_with_data` context.** Whether
  it should render a pill row or drop the key is a design question with
  its own evidence, and nothing renders wrong today.
- **Making the identity slots renamable.** See Decision.

### Doc impact

- `spec/setup_pages.md` — the "Fields with data" item states the
  three-source resolution and the per-page layer, replacing the
  sentence that documented the raw-CSV fall-through as intended
  (PR 1).
- `spec/operator_ui_concept.md` — the Info-card bullet stops saying the
  pills list CSV column names (PR 1).
- `docs/status.md` — row at the close (PR 1).

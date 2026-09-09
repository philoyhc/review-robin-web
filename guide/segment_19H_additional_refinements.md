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
| **19H.3** | A night-mode Guide — the sixteen screencaps ship as light/dark pairs | Open — **planned** |
| 19H.4+ | Admitted only for operator-facing refinements found by using the app. | Open — **empty** |

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

- **The `instrument-card-preview` dark capture is of a different app
  state** (see Blast radius). Ship the pair as-is and that one figure
  shows different UI depending on the theme — the same drift Item 1's
  first light/dark pair had, caught here before it landed rather than
  after. **Decided by the author**: re-shoot it against the same state
  as the light capture, or replace both with a matched pair. Everything
  else in the set is ready.

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

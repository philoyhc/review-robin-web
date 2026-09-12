# Segment 19K — the 11sep assessment's three moves

**Opened 2026-09-11** for the three next moves recommended by
`guide/codebase_assessment_11sep.md` §8, and for whatever those three
produce. Plan: this file.

**A named scope that expects to grow.** 19J opened for an assessment's
three moves and closed at ten items, seven of them produced by the
findings of the item before. Its opening paragraph allowed for that —
"a fourth arriving from a finding is admitted" — and the allowance is
the reason ten items did not require a second segment. This segment
carries the same rule, stated up front rather than discovered: **an
item arriving from another item's findings is admitted; anything else
gets its own segment.** Three is what was known at opening, not a
prediction of the count.

**Items close independently.** Each carries its own `### Doc impact`
and `### Status`; there is no segment-level manifest. The segment
closes when every item has.

**The first finding arrived before the first build.** Measuring Item 2's
blast radius showed the move it was recommended on rested on a figure
that was wrong by about 4×. The correction landed in
`guide/inplace_pagination_assessment.md` and in the assessment's §1, §5
and §8 before this plan was written, and Item 2 below is framed from the
re-measurement rather than from the recommendation. That is the process
working, and it is also a caution about the other two: both of their
opportunity statements are re-derived here rather than quoted.

---

## Item 1 — `close_check` cannot see a `guide/` commitment

### Opportunity

`tools/close_check.py` is the tool that asks whether the spec edits a
plan promised actually happened — the "spec on the way out" half of the
phase rule in `rrw_sdd_in_practice.md` §6.1. It validates a manifest it
cannot fully read.

`COMMITTED_PATH` (`tools/close_check/_manifest.py:33`) is
`` `((?:spec|docs)/[A-Za-z0-9._/-]+\.md)[^`]*` ``. A `Doc impact` bullet
naming a path under `guide/` matches nothing and is silently dropped:
not reported as unchecked, not counted, not warned about. The tool
prints a committed-path count that is quietly smaller than the manifest
it just read.

Measured 2026-09-11 at `94aaa3b2` by parsing every `Doc impact` section
under `guide/` and extracting backticked `guide/*.md` paths from its
bullets:

| What | Count |
|---|---:|
| `guide/` commitments in `Doc impact` manifests | **67** |
| Plans carrying at least one | **33** |
| Of those, reported by `close_check` | **0** |

**Two went unhonoured in Segment 19J alone and nothing failed.** 19J.7
committed to a screencap-retake row in
`guide/post_azure_todo_checklist.md` and it was never written; 19J.8
committed in prose to a `guide/deferred_consolidated.md` entry for the
rejected in-place swap and it was never written. Both were caught by a
person reading the manifests at close, which is the control the tool
exists to replace. 19J.7's own `close_check` run reported **three**
committed paths against a five-bullet manifest and exited 0.

**A second, narrower gap in the same tool.** `window()`
(`_manifest.py:322`) opens an item's window at the later of the
`### Doc impact` heading and that item's own `## Item <n>` heading —
correct, and the fix for a live false pass at 19A.2. But
`_later_commit(start, None)` returns `start` (`_manifest.py:281`), so
when the item heading is **not yet committed** the window falls back to
the segment's first `Doc impact` commit and the item inherits every
sibling's edits. That is exactly the state a stub is in when its author
runs the check on it. Observed twice on 2026-09-11: 19J.9's stub and
19J.10's stub each reported **PASS** while uncommitted and **FAIL**
once their headings were committed, and the PASS was reported to the
author both times before being corrected.

### Decision

**Make the tool report what it cannot check, rather than teaching it to
check everything.** Two changes:

1. `guide/` paths are recognised and counted, and reported under a
   status that says the tool **cannot verify them the way it verifies a
   spec** — because a `guide/` commitment is often "add a row to a
   checklist", which no diff-shaped check can confirm was the *right*
   row. What the tool can honestly say is whether the file was touched
   in the window, which is the same question C3 already asks of
   `spec/` and `docs/`.
2. An **uncommitted item heading is named as such** rather than
   silently widening the window. If the pickaxe finds no commit for
   `## Item <n>`, C3 says the window is the segment's and that the
   result is provisional until the heading is committed.

**Rejected: leaving `guide/` out and documenting it.** That is the
status quo plus a sentence, and the sentence has to be read by someone
who already suspects the gap. Sixty-seven commitments across
thirty-three plans is past the size where a documented blind spot is
cheaper than a fix.

**Rejected: treating a `guide/` bullet exactly like a `spec/` one.** It
would make C3 pass on "the file was touched", which for a checklist is
nearly always true for unrelated reasons — `post_azure_todo_checklist.md`
was edited three times on 2026-09-11 for three different items. A check
that passes for the wrong reason is worse than one that abstains, and
this item is about a tool that already did the former.

### Semantics

- **A `guide/` bullet is a commitment, and the tool says so.** It is
  counted in the manifest total. Whether it is *verified* is a separate
  axis from whether it is *counted*, and conflating them is the current
  defect.
- **Waivers work identically** for `guide/` paths. The existing
  `<!-- doc-impact-waived: reason -->` marker needs no change; it is
  per-bullet and path-agnostic.
- **The root-file rule is untouched.** `constitution.md`, `CLAUDE.md`
  and `rrw_sdd_in_practice.md` count only in the leading position, for
  the reason 19G.4 recorded, and that asymmetry stays.
- **An archived plan's window still ends at its archive commit.** The
  `guide/archive/` handling in `window()` is orthogonal and must not
  move.
- **`--archived` output changes shape**, because its honoured/committed
  ratios are computed from the same parse. Its current figure —
  147/162 live committed paths honoured — will move when 67 previously
  invisible commitments enter the denominator. **The new number is not
  a regression**, and the item must say so where it is printed.
- **Every existing exit code is preserved for existing inputs.** A plan
  with no `guide/` bullets and a committed item heading gets byte-
  identical output.

### Judgment calls — decided

- **2026-09-11 — the CLI invocation string stays frozen.** Every
  archived plan's Definition of done names
  `python3 tools/close_check.py <id>`. 19J.3 froze it deliberately when
  it carved the package; this item does not touch it.

### Blast radius (measured)

Taken 2026-09-11 at `94aaa3b2`.

| What | Count | Command |
|---|---:|---|
| `guide/` commitments invisible today | 67 across 33 plans | parse `Doc impact` bullets for `` `guide/…md` `` |
| Lines in the manifest module | 683 | `wc -l tools/close_check/_manifest.py` |
| Package modules | 5 | `ls tools/close_check/` |
| Existing tests over the tool | to be counted at rung 1 | `grep -rln close_check tests/` |
| Plans whose `--archived` ratio moves | ≤ 33 | the same parse |

### Status — 2026-09-11

**Both rungs landed in one PR.** Rung 2 is nine lines and shares `window()`'s
return signature with rung 1; shipping rung 1 alone would have landed a
4-tuple whose fourth field nothing read, which is a worse intermediate state
than either end.

**Decisions confirmed at build:**

- **The status word is `noted`** (Author, 2026-09-11, from rendered samples of
  all three candidates on 19J.7's manifest). The deciding evidence was
  arithmetic rather than taste: the status column is five wide, so `noted` is
  the only candidate that keeps C5 aligned with `PASS` / `FAIL` / `WARN` /
  `SKIP`. `unverified` says the thing most precisely and costs ten characters;
  the label beside it — "guide/ commitments (counted, not verified)" — carries
  that meaning without spending the column on it.
- **C5 is the check id**, reusing a genuine hole in the numbering: the tool
  had C1–C4, C6, C7 and no C5.
- **C5 never fails.** `report()` fails only on `FAIL`, which is what made it
  safe to switch on for 31 plans at once without reddening a correct close.
- **C5 is emitted only where there is something to say.** A row on all 85
  plans would be noise on the 54 with no `guide/` bullet.

**Where this diverged from the plan, and why:**

- **The `--archived` honour ratio does not move.** `## Semantics` predicted
  147/162 would change "when 67 previously invisible commitments enter the
  denominator". They deliberately do not enter it: folding unverifiable paths
  into a percentage makes the percentage mean less, not more, and the same
  reasoning that keeps them out of C2 and C3 keeps them out of the ratio. The
  `--archived` footer says so **at the print site**, which is what that
  Semantics bullet actually required.
- **The `docs/practice-audit-2026-09-04.md` bullet assumed a close-check entry
  to extend.** There was none — the tool was absent from the inventory of
  automated checks entirely, which is its own small finding about a document
  whose subject is what gates a merge. The bullet is honoured by adding the
  row *and* the limits paragraph rather than by editing a paragraph that did
  not exist.

**Scope beyond the ladder, both forced by the Definition of done's own
measure** ("reports **five** committed paths, not three"):

- The committed total now **includes** the `guide/` paths, with the noted
  subtotal named beside it: `5 committed path(s), 2 noted, 1 waived`. Counted
  and verified are separate axes, and printing only the verified subtotal is
  the defect itself.
- The **waived** count now includes waived `guide/` bullets. Without it 19J.7
  printed `5 committed path(s), 0 waived` while its own C5 lines marked one of
  the five waived.
- `FAIL`, `NOTED`, `PASS`, `WARN`, `_section` and `find_manifests` are
  re-exported from the package, so the tests can name the statuses they assert
  on instead of hardcoding the strings a rename would slip past.

**Measured, not assumed:**

| Claim | Measurement |
|---|---|
| Existing inputs unchanged | 85 segment ids run against `HEAD` in a worktree: **54 byte-identical, 31 differ, and every one of the 31 differences is a C5 block**. Zero unexpected diffs. |
| No exit code moves | **0 flips** across the same 85. |
| `--archived` | gains exactly the two footer lines; the plan table and the ratio are byte-identical. |
| 19J.7's manifest | `5 committed path(s), 2 noted, 1 waived` — the Definition of done's own number, against the 3 it printed before. |
| Guards are not vacuous | **9 mutations, 9 caught.** Two were caught only after the test was rewritten: the first versions asserted on the result dict, and the committed total is computed inside `report()`, so the dict-level assertion passed on the very mutation it existed to catch. That is 19I's *a negative assertion is only as strong as the string it matches* at the seam level — an assertion is only as strong as the layer it reads. |

**Two findings this item leaves behind.**

*The `guide/` count depends on who is counting, and the hand count was wrong
in both directions.* The Opportunity's table says 67 across 33 plans,
hand-parsed at `94aaa3b2`. The tool's own parser, over the same corpus, finds
**80 across 35**; 19K's own plan contributes none of the difference. Worse,
the Opportunity's supporting figure — "12 point into `guide/archive/` and 13 at
paths that have since moved there, so C2 would turn **25** correct commitments
into failures" — does not survive measurement either: **11** of the 80 have no
file where the bullet names one, and **8** of those are the archived-plan case
the argument rests on. Three are genuinely broken. So C2 would fail eight
correct commitments to catch three, which is still the right call and a
materially smaller claim than the one the plan made.

The Opportunity is left as written, per *never rewrite intent* — the point it
was making survives either figure, and a hand count that disagrees with the
tool built to replace it is worth leaving visible. Everywhere the number is
*used* rather than recorded now carries the parser's: the `GUIDE_PATH` comment
in `_manifest.py` and the `docs/practice-audit-2026-09-04.md` passage.

*`--archived` reads one manifest per plan.* For an item-shaped plan it takes
the **first** item's `Doc impact` and stops (`_archive.py`, the `next(...)`
over `found["items"]`), which is why its footer says 58 `guide/` commitments
where the same regex over every level finds 76 in that directory. This is
pre-existing and affects the headline `147/162` ratio the same way — the
sweep has been reporting one item's commitments per multi-item plan since it
was written. Not fixed here: it moves the number the whole report is read for
and deserves its own slice, with the before-and-after stated. Recorded as a
candidate item for this segment.

**`spec-writer` pass (checker, 2026-09-11) — two flags, both upheld.**

1. *The practice-audit passage omitted C6.* It enumerated C1–C5 and C7 and
   never mentioned the `Status`-block check, so the document promising "what
   the tool does and does not verify" was missing one of seven. The passage is
   now an explicit C1–C7 list.
2. *The practice-audit repeated the hand count flatly while `docs/status.md`
   was recording it as unreconciled.* Upheld, and re-measuring made it worse
   than the flag: the 25-of-67 figure is 11-of-80, 8 of them the archiving
   case. Corrected in the practice-audit **and** in the `GUIDE_PATH` comment,
   which was the original source of the number — the tool's own comment
   asserting a figure the tool's own parser contradicts.

The second flag is the one worth keeping. This item's `Status` had already
recorded that the hand count did not reconcile, and the same session then went
on repeating it in the other committed document and left it standing in the
code. *Recording that a number is unreliable does not stop you using it* —
the correction has to reach every place the number is spent, not just the
place it is confessed. Maker ≠ checker earned its keep here: the author read
past this twice.

### PR ladder

1. **Count `guide/`, report it as unverifiable-but-committed.** The
   regex, the status vocabulary, and the `--archived` denominators.
   Tests: a manifest with a `guide/` bullet is counted; a waived one is
   waived; a plan with none produces byte-identical output to today.
   *Must not* change the root-file rule or the CLI string.
2. **Name an uncommitted item heading.** C3 says the window is
   provisional rather than reporting a clean pass. Test: the 19J.9
   stub's exact shape — an item heading present in the working tree and
   absent from history — reports provisional, not PASS.

### Definition of done

- A `Doc impact` bullet naming a `guide/` path is counted in the
  manifest total and reported under a status distinct from a verified
  `spec/` path.
- Running the tool on 19J.7's archived manifest reports **five**
  committed paths, not three.
- An item whose `## Item <n>` heading is uncommitted is reported as
  provisional rather than passing.
- A plan with no `guide/` bullets and a committed heading produces
  byte-identical output to `main` — asserted, not assumed.
- `.venv/bin/pytest` and `ruff check .` both pass in the agent container
  before pushing.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19K.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` records intended vs done
- `docs/status.md` row added

### Open questions

- **What the new status is called.** `unverified`, `noted`, `counted`
  — the word appears in every future close and should be chosen rather
  than defaulted. **Author decides at rung 1**, from a rendered sample.

### Out of scope

- **Verifying that a `guide/` edit was the *right* edit.** No
  diff-shaped check can, which is the reason for the abstaining status
  rather than a pass.
- **The whole-folder drift sweep.** A separate cadence with a separate
  reader (`tools/close_check.py --stale`), untouched here.

### Doc impact

- `docs/practice-audit-2026-09-04.md` — the close-check entry gains what
  the tool does and does not verify, since that document is where "what
  gates a merge here" is recorded (Item 1).
- `docs/status.md` — row when the item closes (Item 1).

---

## Item 2 — the column-chip script binds to elements that a re-render replaces

### Opportunity

`app/web/templates/base.html` carries **eight** inline `<script>`
blocks. One of them binds event listeners to elements inside the table
card, so anything that re-renders that card silently loses the
behaviour — no error, no console warning, a chip that stops responding.

Measured 2026-09-11 at `94aaa3b2` by reading each block, not by
grepping for `DOMContentLoaded`:

| Block | Lines | What | Binds to |
|---|---:|---|---|
| 2 | 321 | sortable table headers | **nothing** — inline `onclick` in markup |
| 3 | 127 | column-visibility chips | **`[data-col-toggle]` elements** |
| 4 | 29 | first-banner scroll | `document` |
| 5 | 21 | delete-confirmation gate | `[data-delete-confirm]` — outside the table card |
| 6 | 30 | theme toggle | `.theme-toggle-opt` — chrome |
| 7 | 77 | navigation busy indicator | `document`, `window` |
| 8 | 36 | range-menu outside click | `document` |

**This corrects the figure the move was recommended on.**
`guide/inplace_pagination_assessment.md` said four blocks totalling
~500 lines die with a re-rendered table, and
`guide/codebase_assessment_11sep.md` §5 and §8 repeated it. All three
are corrected as of 2026-09-11. The error had three parts, and the
first is the instructive one:

- **Binding *inside* `DOMContentLoaded` was mistaken for binding *to*
  elements.** Block 2's headers call `rrwSortHeaderClick(event, this)`
  through an inline `onclick` attribute, so the handler arrives with any
  re-rendered HTML and survives by construction. Its single listener is
  `document.addEventListener('DOMContentLoaded', _rrwHydrateFromCookies)`
  — a badge repaint a swap would re-call. One function call, not 321
  lines.
- **Blocks 5 and 6 are not table-relevant.** `[data-delete-confirm]`
  sits in the Operator actions and lock cards (`session_reviewers.html`
  lines 196 / 649 / 696) against a table card spanning 295–485;
  `.theme-toggle-opt` is chrome.
- **Block 4 is delegated**, not load-time binding.

No block uses property-style handlers (`el.onclick = …`) — checked
across all eight.

So the work is **one block of 127 lines**, and even it sits *above* the
table inside the card, so a table-body-only swap would not break it;
only a card-level re-render does.

### Decision

**Convert block 3 to a delegated listener on `document`, matching
blocks 7 and 8.** It is the shape the file already uses for its two
newest behaviours, it survives any re-render by construction rather
than by remembering to re-invoke, and nothing about it is specific to
the swap that is off the roadmap.

**Rejected: also re-homing the sort block's cookie hydration.** It is
one function call and it is not broken today; doing it here would mean
touching 321 lines to change nothing observable. It is named in
Semantics so that whoever eventually re-renders a table card knows to
call it, which is the cheaper half of the same protection.

**Rejected: doing nothing, on the grounds that nothing re-renders a
table card today.** True, and it is the argument the original ~500-line
figure was resisting. At 127 lines the cost is small enough that the
argument reverses: the block is the only thing standing between the app
and a re-renderable table card, and leaving one known fragile binding
in place because nothing steps on it yet is how the next person
discovers it.

### Semantics

- **Delegation is on `document`, event type `click` and `keydown`** —
  the two block 3 currently binds — and the handler resolves its target
  with `closest("[data-col-toggle]")`, so a chip rendered after load
  works with no registration.
- **`[data-col-toggles-for]` scoping survives.** The block finds a chip
  row's table by that attribute; delegation must resolve the same
  pairing from the event target rather than from a load-time list.
- **`localStorage` behaviour is unchanged.** Column visibility persists
  per table under the key the row declares; this item moves *where the
  listener lives*, not what it does.
- **A page with no chip row registers nothing today and must register
  nothing after.** An untagged roster renders no chip row at all, and a
  delegated listener that fires on every document click must return
  immediately when `closest` finds nothing.
- **Block 2's hydration is documented, not moved.** `_rrwHydrateFromCookies()`
  must be called after any future table re-render to repaint sort
  badges. That sentence is the deliverable for block 2.

### Judgment calls — decided

- **2026-09-11 — keyboard activation keeps its current contract.** The
  chips are `role="button" tabindex="0"` with a `keydown` handler; the
  delegated version handles the same keys and does not quietly become
  click-only.

### Blast radius (measured)

Taken 2026-09-11 at `94aaa3b2`.

| What | Count | Command |
|---|---:|---|
| Lines in block 3 | 127 | regex over `base.html`'s `<script>` bodies |
| `addEventListener` calls to re-home | 2 (`click`, `keydown`) | same |
| `[data-col-toggle]` sites in templates | 8 | `grep -rho 'data-col-toggle=' app/web/templates \| wc -l` |
| Templates carrying a chip row | 7 | `grep -rl 'data-col-toggles-for' app/web/templates` |
| Tests over column visibility | to be counted at rung 1 | `grep -rln col-toggle tests/` |

### Status

**Closed 2026-09-11**, both rungs, in one PR. The ladder held; the
measurement in the Opportunity above held too, which after the ~4×
correction that produced this item is worth saying explicitly.

**The premise was verified, not assumed.** The same chip injected after
load was driven in Chromium against both `main` and the branch: dead on
`main`, live after the change. An item whose whole argument is "this
breaks on a re-render" should not ship without someone having watched it
break.

Eight behaviours checked in Chromium at 1280×900 against a three-chip
roster: a click hides the column and a second click restores it, Enter
and Space each toggle, the state persists as
`{"tag-1":true,"tag-2":false,"tag-3":false}` under the existing key,
a reload restores it — and the two that matter here, **a chip injected
after load toggles its column**, and **`_rrwHydrateColToggles()` restores
the saved columns after the DOM is reset**.

- **2026-09-11 — hydration is exposed, which the plan did not ask for.**
  Delegation keeps a late chip *clickable*; it does not restore the
  operator's columns, because a re-render brings chips back as the
  server rendered them — all visible — and the `col-hidden-*` classes
  are not in the markup either. So `hydrate` became a named function
  called at load and assigned to `window._rrwHydrateColToggles`, which
  is the arrangement the sort primitive already has with
  `_rrwHydrateFromCookies`. Two lines, and without them the item
  delivers half of what it claims. Recorded here rather than quietly,
  because it is scope the plan did not name.
- **2026-09-11 — rows are filtered, not selected by attribute value.**
  Finding a table's chip rows could be
  `querySelectorAll('[data-col-toggles-for="' + id + '"]')`, but a table
  id is page-authored and that would make the primitive depend on CSS
  escaping for no gain. It iterates and compares instead.
- **2026-09-11 — the guard asserts the mechanism, and the item says so.**
  The suite has no JavaScript runtime, so it cannot click a chip. A
  per-chip listener and a delegated one are indistinguishable on a
  freshly loaded page and differ completely on a re-rendered one, so
  *where the listener is registered* is the honest thing to assert; the
  behaviour is the browser run above. The same division 19J.4 used for
  the busy indicator's arming.
- **The receiver probe started from the fixed form.** 19J.9 shipped
  `(\w+)\.addEventListener`, which does not match `menus[0].` — `]` is
  not a word character — so the offending receiver dropped out of the
  match set and the guard passed on the mutation it existed to catch.
  This file uses the corrected pattern and asserts the match count
  equals the number of registrations.
- **Five mutations, each caught**: rebinding per chip (the pre-19K.2
  shape), dropping the `keydown` half, resolving the target at load
  instead of at event time, removing the hydration hook, and renaming
  the storage key.

**One thing rung 2 did that the plan framed as documentation only.**
Block 2's comment now states that it binds nothing — its headers call
`rrwSortHeaderClick` through an inline `onclick`, so the handler arrives
with the markup — because that is the sentence whose absence caused the
~4× error this item was opened to correct. The spec carries both hooks
together, since a re-render owes the table both.

### PR ladder

1. **Convert block 3 to delegation**, behaviour unchanged. Tests: a chip
   toggles its column; a chip **injected after load** toggles its column
   (the assertion the whole item exists for, and one the current code
   fails); keyboard activation still works; a page with no chip row
   registers nothing that misfires. *Must not* change the
   `localStorage` key, the persisted shape, or any template.
2. **Document block 2's hydration hook** in the block's own comment and
   in `spec/ui_elements.md`, so a future re-render knows to call it.
   Not a code change.

### Definition of done

- Column-visibility chips work when injected after load — asserted by a
  test that fails on `main`.
- No `addEventListener` in block 3 has a receiver other than `document`,
  asserted the way `test_pager_cluster.py` asserts it for block 8,
  including that the match count equals the number of registrations.
- Keyboard activation and `localStorage` persistence unchanged.
- `.venv/bin/pytest` and `ruff check .` both pass in the agent container
  before pushing.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19K.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` records intended vs done
- `docs/status.md` row added

### Open questions

None. The measurement settled the shape and the scope.

### Out of scope

- **The in-place table swap.** Off the roadmap by decision
  (`guide/deferred_consolidated.md` Part C); this item is worth doing
  without it and says so.
- **Blocks 5 and 6.** Not table-relevant, measured above. Converting
  them would be tidying with no failure mode behind it.
- **Any change to block 2.** 321 lines that already survive a
  re-render.

### Doc impact

- `spec/ui_elements.md` — the column-visibility primitive gains the
  delegation contract and the note that a re-rendered table must call
  `_rrwHydrateFromCookies()` to repaint sort badges (Item 2).
- `docs/status.md` — row when the item closes (Item 2).

---

## Item 3 — decide whether the Invitations / Responses N+1 gets an item

### Opportunity

The Invitations and Responses pages issue a query per assignment.
Benchmarked during 19J.4 at a 200 × 200 roster: **40,433 and 80,432
queries** for one page render. 19J.5 paged both pages at 200 rows,
which cut the HTML they emit and **not** the work behind it — every row
is built before any slice happens.

Located 2026-09-11 at `94aaa3b2`. `app/services/monitoring.py:275` loops
reviewees, and inside that loops their assignments, calling
`_assignment_complete(db, a, fields)` per assignment
(`monitoring.py:203`), which executes
`select(Response).where(Response.assignment_id == assignment.id)` —
one query per assignment, nested two deep. `per_reviewee_coverage` and
`per_reviewer_progress` have **four** callers between them:
`app/web/views/_responses.py`, `app/web/views/_invitations.py`,
`app/services/invitations.py`, and
`app/services/scheduled_events/_reminders.py`.

**This is the most deferred decision in the codebase** and it currently
lives in exactly one place: 19J.4's `Out of scope`. The 11sep
assessment named deciding it as a next move — not fixing it.

### Decision

**Not yet made. Deciding is the item, and "not yet, and here is the
trigger" is a permitted and expected answer.** What this item produces
is a decision with a reason, recorded where a reader will find it —
not necessarily a fix.

The three candidate answers, so the item is not open-ended:

1. **Fix it now.** One grouped `select(Response)` over the page's
   assignment ids, folded into `per_reviewee_coverage`, replacing the
   inner call. Bounded, but it touches a service four surfaces call,
   two of which are not pages at all (`invitations.py` and the reminder
   scheduler), so the blast radius is wider than the two pages that
   hurt.
2. **Fix it when paging can carry it.** The slice already exists; the
   query does not respect it. Making coverage take the page's ids is a
   smaller change than making it fast in general, and it helps exactly
   the two surfaces that were measured.
3. **Defer with a trigger.** Record it in
   `guide/deferred_consolidated.md` Part B with a named lift condition
   — a pilot roster above some size, or a measured page time above
   some threshold — so it stops living in one item's Out of scope.

**Rejected as a framing: treating this as a performance bug to fix
because the number is large.** 40,433 queries is a real number and
nobody has yet reported a slow page from a real roster; the largest
roster the app has seen is the author's test data. Fixing it now on the
strength of a synthetic benchmark would be optimising against a load
model rather than against use — which is the same error the 19J.2
refinement-allowance work refuted in a different register.

### Semantics

These hold whichever answer wins.

- **The decision is recorded somewhere durable**, not in a plan's Out
  of scope. That is the one thing this item must produce.
- **The measurement is re-taken before it is acted on.** The 40,433 /
  80,432 figures are from 19J.4, before paging landed. Paging did not
  change the query count by design, but "by design" is a claim, and
  rung 1 checks it.
- **Any fix keeps `per_reviewee_coverage`'s return shape.** Four
  callers, two of them non-page; a signature change is a wider item
  than this one.

### Judgment calls — decided

- **2026-09-11 — re-measure before deciding, even though the answer
  might be "defer".** A deferral recorded against a stale number is
  worth less than one recorded against a current one, and the cost is a
  single benchmark run.

### Blast radius (measured)

Taken 2026-09-11 at `94aaa3b2`.

| What | Count | Command |
|---|---:|---|
| The per-assignment query | `monitoring.py:213` inside a 2-deep loop from `:275` | read |
| Lines in `app/services/monitoring.py` | 309 | `wc -l` |
| Callers of the two coverage functions | 4 | `grep -rn 'per_reviewee_coverage(\|per_reviewer_progress(' app/` |
| …that are pages | 2 | `_responses.py`, `_invitations.py` |
| …that are not | 2 | `invitations.py`, `scheduled_events/_reminders.py` |
| Places the measurement is currently recorded | 5 | `grep -rn '40,433\|80,432' guide/ docs/` |

### Status — 2026-09-12

Both rungs landed together. Rung 1's re-measurement settled the
question the Author was to decide from, and the answer — **fix it now**
— made rung 2 the same piece of work.

**Rung 1: the measurement, re-taken on `main` with paging in place.**
Method mirrors 19J.4's — full-matrix sessions through the real import +
generate routes, each page rendered while SQL statements are counted,
SQLite in-process.

| roster | assignments | Assignments | Invitations | Responses |
|---|---:|---|---|---|
| 25×25 | 625 | 43 q | 708 q | 1,332 q |
| 50×50 | 2,500 | 43 q | 2,633 q | 5,132 q |
| 100×100 | 10,000 | 43 q | 10,233 q | 20,232 q |
| 200×200 | 40,000 | 43 q | **40,433 q** | **80,432 q** |

**Every query count is identical to 19J.4's**, at every roster size. So
paging did not change the work behind the pages — the plan asserted that
"by design", and it is now measured rather than claimed. Wall times came
in lower (6.9 s / 12.6 s against 9.3 s / 16.1 s), which is container
speed; the query count is the portable number.

**Three things the re-measurement added that the plan did not have:**

1. **Responses' second pass is exactly half of it.** `summary_counts`
   accounts for **40,404 of the 80,432** queries, measured by replacing
   it with a stub, and its only consumer is one integer,
   `incomplete_count`.
2. **That integer is not cheap to get another way.** `pill_state`
   bottoms out in per-assignment completeness, so "replace the pass with
   a scalar `COUNT`" — the obvious cheap win — is not available. Checked
   before it was recommended.
3. **It is two lines, not a diffuse problem.** Attributing every query
   to its call site: `responses/_core.py:805` produced 2,500 of the
   Invitations page's 2,633 at 50×50, and Responses added
   `monitoring.py:213` for another 2,500. **Those two lines are ~99% of
   both pages.** The same query shape occurs at 9 sites in the
   codebase; the other 7 never fire on these pages.

Point 3 is what made the decision cheap. The plan's worry — that fixing
this touches a service with four callers, two of them not pages — does
not apply to a prefetch *inside* those two functions: no signature a
caller passes changes, because the new parameter defaults to `None` and
the non-looping callers never pass it.

**Rung 2: one query per session, in place of one per assignment.**

| roster | Invitations | Responses |
|---|---:|---:|
| 25×25 | 708 → **84** | 1,332 → **84** |
| 50×50 | 2,633 → **134** | 5,132 → **134** |
| 100×100 | 10,233 → **234** | 20,232 → **234** |
| 200×200 | **40,433 → 434** | **80,432 → 434** |

93× and 185× at 200×200; 6.9 s → 2.3 s and 12.6 s → 2.5 s. **Not flat**
like Assignments' 43 — 84 / 134 / 234 / 434 is roughly two queries per
reviewer plus a constant, the per-reviewer assignment and field lookups
that remain. Linear in the roster where it was quadratic in it, which is
the change worth having; the residual is recorded here rather than
chased.

**Decisions confirmed at build:**

- **The prefetch is internal and opt-in.** `responses_by_assignment` is
  a new parameter defaulting to `None` on `reviewer_session_state`,
  `_state_from_assignments` and `_assignment_complete`; only the two
  loop owners pass it. Every other caller behaves exactly as before,
  including the two non-page ones the plan flagged.
- **Joined on `Assignment.session_id`, not `id.in_(...)`.** The id list
  is the assignment count, which is the thing that grows, and SQLite's
  default variable limit is 999.

**Measured, not assumed:**

| Claim | Measurement |
|---|---|
| Paging changed nothing | Query counts identical to 19J.4 at all four roster sizes. |
| The second pass is half | 80,432 → 40,028 with `summary_counts` stubbed: **40,404 queries, 50%**. |
| Two lines are the cause | Per-call-site attribution at 50×50: 2,500 from `_core.py:805`, 2,500 from `monitoring.py:213`. |
| Nothing broke | Full suite **3,774 passed**, 16 skipped. |
| Guards are not vacuous | **6 mutations, 6 caught.** |

**Two vacuous tests written and caught before pushing — the same
mistake twice in one item.**

The first equivalence test seeded no responses, so it compared an empty
list against an empty list for every assignment and **passed against a
mutation returning `{}`** — the one mutation it existed to catch. Fixed
by activating the session and having half the reviewers submit.

Then the scoping test, added *because* a mutation escaped, made the
identical mistake one level along: it seeded a second session with no
responses, so dropping the `session_id` filter leaked nothing and the
test passed on the mutation it was written for. Fixed by giving the
other session rows.

*A fixture that produces no data makes every assertion about that data
true.* Writing the test after the mutation escaped did not stop it
happening again; only running the mutation a second time did.

**`spec-writer` pass (checker, 2026-09-12) — run *before* the push, for
the first time.** The three previous items ran it in parallel with the
push and each collected corrections after the merge; the Author changed
the order for this item. It found three things, all fixed here rather
than as a follow-up:

1. **The new function's docstring contradicted the rest of the change.**
   It said the per-assignment lookup "scaled linearly" — the whole point
   is that it scaled with the *square* of the roster and the prefetch is
   what makes it linear — and it attached the 50×50 figure to a sentence
   about 200×200. Rewritten with both roster sizes named.
2. **`guide/todo_master.md` still listed Item 3 as open roadmap work**,
   and `guide/codebase_assessment_11sep.md` still called the N+1
   "measured and unfixed" in §6 and recommended deciding it in §8 — a
   snapshot overtaken one day after it was written. Struck and annotated
   rather than rewritten, per the assessment convention, and both gained
   manifest bullets. They are visible to `close_check` at all because of
   19K.1, and nameable in a manifest because of 19K.5.
3. An alphabetical-ordering slip in `responses/__init__.py`.

It also **verified something this item had not**: the last-write-wins
concern in `_assignment_complete`'s `by_field` dict is moot, because
`Response` carries `UniqueConstraint("assignment_id",
"response_field_id")` — two rows cannot share a field id on one
assignment, so row order cannot matter in either path. That is a
correctness question the item had reasoned about and not checked.

**Running the checker before the push cost about eight minutes and
changed what landed.** Three items in a row had merged with corrections
outstanding; this one merged correct.

**One mutation was reclassified rather than fixed.** Dropping the
`session_id` filter is **not** a correctness bug: assignment ids are
globally unique, so a superset keyed by assignment id answers every
`.get` correctly. It is a performance bug — on a server hosting many
sessions the prefetch would read every response row in the database to
render one page — and it is guarded as that, with the reasoning in the
test.

### PR ladder

1. **Re-measure, then decide.** Benchmark both pages at the current
   `main` with paging in place, put the three candidates above to the
   author with the numbers, and record the answer. *Must not* change
   `monitoring.py`.
2. **Whatever follows** — a grouped query, a paged one, or a Part B
   entry with a lift trigger. Sized once rung 1 has the decision.

### Definition of done

- Current query counts for both pages at a 200 × 200 roster, measured
  on `main`, recorded in this plan.
- A decision, with its reason, recorded outside a plan's Out of scope.
- If the answer is "defer": `guide/deferred_consolidated.md` Part B
  carries it with a named lift trigger.
- `.venv/bin/pytest` and `ruff check .` both pass in the agent container
  before pushing.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19K.3` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` records intended vs done
- `docs/status.md` row added

### Open questions

- **Which of the three candidates?** **Author decides at rung 1**, from
  the re-measured numbers rather than from 19J.4's.

### Out of scope

- **Any other N+1 in the app.** None is measured; naming them here would
  make this item pretend to be an audit it is not.
- **Changing `per_reviewee_coverage`'s signature.** Four callers, two
  non-page; that is a wider item than this one and would need its own.

### Doc impact

- `spec/operations_pages.md` — records what the two pages cost to render
  and what was decided about it, so the next reader finds it on the
  page's own spec rather than in a closed plan (Item 3).
- `guide/todo_master.md` — the Item 3 roadmap entry struck and marked
  done, since it still described the decision as open (Item 3).
- `guide/codebase_assessment_11sep.md` — §6's "measured and unfixed"
  weakness and §8's third recommended move, both settled the day after
  they were written; struck and annotated rather than rewritten (Item 3).
- `docs/status.md` — row when the item closes (Item 3).

---

## Item 4 — `--archived` reads one manifest per plan

### Opportunity

`--archived` is the sweep that answers "is this practice actually
kept?" across every closed plan. Its headline figure —
`147/162 live committed paths honoured (91%)` — has been quoted into
`docs/status.md` four times as the measure of the phase rule's exit.

It is computed over a subset of the evidence. `archived_report`
(`tools/close_check/_archive.py:38-44`) picks **one** manifest per
plan: the segment-level `## Doc impact` if there is one, otherwise the
**first** item-level `### Doc impact` it finds, and stops.

```python
line = found["segment"] if depth == 2 else next(
    (i["doc"] for i in found["items"].values() if i["doc"] is not None),
    found["stray"][0] if found["stray"] else None,
)
```

A segment-level manifest spans the whole plan, so those 35 plans are
read whole. The five item-shaped plans are not:

| Plan | manifests | read today |
|---|---:|---:|
| `segment_19A_spec_documentation.md` | 2 | 1 |
| `segment_19G_post_assessment.md` | 10 | 1 |
| `segment_19H_additional_refinements.md` | 7 | 1 |
| `segment_19I_roster_search_and_row_delete.md` | 13 | 1 |
| `segment_19J_assessment_moves.md` | 10 | 1 |

**37 of the 42 item manifests in the archive have never been read by
the sweep.** 19I is judged on 1 of its 13.

Measured 2026-09-11 at `0e2850e1`, reading every level with each item's
own window:

| | today | every level |
|---|---:|---:|
| live committed paths honoured | 147/162 (**91%**) | **259/274 (95%)** |
| plans fully honoured | 30 of 40 | 30 of 40 |
| committed paths no longer existing | 9 | 9 |
| plans with no manifest | 58 | 58 |
| `guide/` commitments in the footer | 58 across 33 | 63 across 33 |

**Every one of the 112 hidden paths is honoured** — 259−147 = 112 and
274−162 = 112 — so all 15 unhonoured paths live in the older,
segment-shaped plans. The sweep has been **understating** the practice,
and understating it more as the plans got better: item-shaped manifests
are the newer convention, so the shape that closes item-by-item is
exactly the shape the sweep cannot read.

The defect has been present since the tool was written
(`851bb88f`, 2026-09-05), so it is in every `--archived` figure ever
quoted: 85/101, 132/148, 133/148, 147/162. **`_archive.py` has no
tests** — `grep -rln "archived_report\|--archived" tests/` returns
nothing — which is how a one-of-thirteen read survived six days of
the tool being used on itself.

### Decision

**Read every manifest level in the plan, each with its own window.**
The level set is the one `check_manifest` already uses: the
segment-level manifest if present, otherwise every item-level
`### Doc impact` plus any stray. Each item level passes its own item
number to `window()`, so an item's window opens at its own
`## Item <n>` heading — without that, fixing the read would import the
19A.2 false pass into the sweep, where a newer item's commitment could
be satisfied by an older item's edit.

**One line per plan stays.** The row is summed across levels, with the
manifest count shown when it is more than one, and the date column
showing the earliest level's window start.

**Rejected: a line per manifest level.** It is the same information,
and it takes the report from 98 rows to 135 — burying the ten plans
that have a finding under the ninety that do not. The report is read
as one row per plan and should stay that way.

**Rejected: leaving it and documenting the caveat.** That was the
answer 19K.1 gave, correctly, because 19K.1 was about something else
and the fix moves the number the whole report is read for. It is not
the answer twice.

### Semantics

- **The ratio moves, and the move is a correction rather than an
  improvement.** 91% → 95% is the same practice measured properly. The
  item must say so where the figure is recorded, or the next reader
  will read a 4-point jump as the practice getting better in a day.
- **A segment-level plan's output is unchanged.** Those 35 are already
  read whole; byte-identical is the assertion, not the hope.
- **Each item level keeps its own window.** An item's window opens at
  the later of the manifest heading and that item's own heading, as
  `check_manifest` does.
- **A stray `### Doc impact`** — outside any `## Item n` block, as 11E
  has under `## Follow-on` — has no item number and takes the
  manifest's own window.
- **`fully honoured` becomes every level's paths honoured**, not the
  first level's. It happens not to move, which is worth stating: the
  five plans were fully honoured on their first item and are fully
  honoured in full.
- **The per-plan `guide/` dedup stays per plan**, not per level, so the
  footer keeps counting what it counts today.

### Judgment calls — decided

- **2026-09-11 — the four already-quoted figures stay as written.**
  85/101, 132/148, 133/148 and 147/162 are in dated `docs/status.md`
  entries recording what the tool said on that day, which is what a
  changelog is for. Only the places that state the figure as *current*
  are corrected.

### Blast radius (measured)

Taken 2026-09-11 at `0e2850e1`.

| What | Count | Command |
|---|---:|---|
| Lines in `tools/close_check/_archive.py` | 107 | `wc -l` |
| Tests naming `archived_report` or `--archived` | **0** | `grep -rln 'archived_report\|--archived' tests/` |
| Archived plans | 98 | `ls guide/archive/segment_*.md` |
| …segment-shaped (read whole today) | 35 | the parse above |
| …item-shaped (read at one level today) | 5 | the parse above |
| …with no manifest | 58 | the parse above |
| Item manifests the sweep never reads | 37 | the parse above |
| `window()` call sites | 2 | `grep -rn 'window(' tools/close_check/*.py` |
| Live docs stating the ratio as current | 1 (`tools/README.md`) | `grep -rn '147/162' docs/ tools/ spec/` |

### Status — 2026-09-11

Landed as the one rung planned. Every predicted figure held against the
build, which is the first time in this segment that has been true of a
blast-radius table: 259/274 (95%), 30 of 40 fully honoured, 9 missing,
58 with no manifest, and the five item-shaped plans read at 2, 10, 7, 13
and 10 manifests.

**Decisions confirmed at build:**

- **`manifest_levels` is its own function**, not a loop inline in
  `archived_report`. It is the one thing in this module that has a rule
  worth stating, and the rule is testable without a git repo — six of
  the ten tests need no fixture at all.
- **The row gained `N manifests`** only where N > 1, so the 35
  segment-shaped rows stay byte-identical rather than gaining a
  `1 manifests` suffix.
- **The date column shows the earliest level's window start**, which for
  an item-shaped plan is its first item's. The alternative — the latest
  — would have made a thirteen-item plan look as though its window
  opened the day it closed.

**Measured, not assumed:**

| Claim | Measurement |
|---|---|
| Segment-shaped plans unchanged | 40 plan rows diffed against `origin/main`: **35 byte-identical, 5 changed**, and the 5 are exactly the item-shaped plans. |
| The ratio | 147/162 (91%) → **259/274 (95%)**. 274−162 = 112 and 259−147 = 112, so **every hidden path was honoured** and all 15 unhonoured ones are in the older segment-shaped plans. |
| Guards are not vacuous | **7 mutations, 7 caught** — one manifest per plan (the defect), `item=None` windows, the manifest count dropped from the row, stray levels dropped, manifest-less items counted as levels, both-shapes preferring items, and the dedup regression below. |

**One bug in this item's own code, caught by a one-off.** The footer
came out at **64** `guide/` commitments where the pre-build measurement
said 63. The accumulator was a comprehension —
`noted_here += [p for … if p not in noted_here]` — whose membership test
is evaluated against the list as it stood *before* `+=` extends it, so a
path named twice inside one level slips through. One duplicate in the
whole corpus: small enough to wave through as a rounding difference
between two parses, which is exactly why the pre-build number existed.
Now extended one path at a time, with a test that a doubled bullet
counts once.

**This item's own manifest is read at 2 of its 3 bullets**, and the
adjudication of that is the same shape as 19K.1's. `COMMITTED_PATH`
matches `spec/` and `docs/` only, so the `tools/README.md` bullet — a
real documentation commitment, kept — is invisible to C1–C7 exactly as
`guide/` paths were until Item 1. This is **known rather than new**:
19G.8's `docs/status.md` row already records that 19G.6's bullets "name
`tools/` and `.claude/` paths the regex never matched". Measured
2026-09-11 across every live and archived plan, **16 such commitments**:
`tools/` 6 in 4 plans, `app/` 5 in 3, `.claude/` 3 in 2, `tests/` 1,
`.github/` 1.

Not fixed here, and deliberately not: extending the manifest regex is a
decision about *which roots a plan may commit to*, which is a different
question from how the sweep reads levels, and the segment-plan skill's
rule against bundling independent changes applies. Recorded as a
candidate item. What this item will not do is let the printed count
stand unremarked — "the printed committed-path count quietly smaller
than the manifest it had just read" is the sentence Item 1 was opened
on, and it is true of this close too.

**`spec-writer` pass (checker, 2026-09-11) — two flags, both upheld, both
after the PR had merged.** It verified every figure above independently
(147/162, 259/274, the two 112s, 37 of 42, 19I's 1 of 13, 35 of 40
byte-identical) by re-running the tool at `0e2850e1` in a worktree, and
found:

1. *A performance regression the item did not measure.* Reading every
   level asks each plan's `Doc impact` pickaxe once per item — 13 times
   for 19I — taking `--archived` from **258 `git log` calls / 5.9s** to
   **491 / 17.8s**. Memoising `_first_commit_matching` on
   `(plan, pattern)` brings it to **417 / 11.3s**: 15% fewer calls for
   37% less time, because the calls it removes are the `-G` pickaxes,
   which scan a file's whole history rather than a range. The rest of the
   gap is not waste — 274 paths are checked where 162 were. The
   `~3s` in `tools/README.md` was the tool's own first-commit figure and
   was already wrong at 5.9s before this item touched it.
2. *A referent broken by insertion.* The sweep paragraph was inserted
   between the close check's two-exclusion list and the sentence "Both
   are printed at the point of use", so "Both" followed three limits —
   and wrongly, since the sweep's defect is fixed rather than printed.
   The paragraph now sits after that sentence, which says which two.

**That both landed after the merge is the cost of running the checker in
parallel with the push.** The alternative is a slower close, and the
corrections are a commit rather than a rewrite, so the trade held here —
but it is a trade, not a free win, and worth naming as one.

**The finding worth keeping.** `_archive.py` had **no tests** — the
blast-radius table's one zero — and that is not incidental to the
defect, it is the whole explanation for it. The sweep was run on this
repository roughly daily for six days, its output pasted into
`docs/status.md` four times, and it was reading 1 of 13 manifests for
the plan with the most commitments in the archive. Nothing in a report
that always exits 0 tells you it read less than it should; only a test
that constructs a plan with three manifests and counts them does. *A
report that cannot fail needs tests more than a check that can*, not
less.

### PR ladder

1. **Read every level, and test the sweep at all.** The level loop, the
   per-item windows, the summed row — plus the first tests
   `_archive.py` has ever had, since an untested sweep is how this
   survived. *Must not* change `check_manifest` or the single-id
   output.

### Definition of done

- `--archived` reads every manifest level in every archived plan, each
  with its own window.
- The 35 segment-shaped plans produce byte-identical rows — asserted,
  not assumed.
- The report states its own figures: 259/274, and the 5 plans read at
  more than one level show how many.
- `_archive.py` has tests, and each guard is mutation-checked.
- The ratio's move is recorded as a correction, not a gain.
- `.venv/bin/pytest` and `ruff check .` both pass in the agent container
  before pushing.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19K.4` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` records intended vs done
- `docs/status.md` row added

### Open questions

None. The three shape choices — every level, one row per plan, per-item
windows — are settled above with their rejected alternatives.

### Out of scope

- **The `guide/` dedup scope.** Per plan today, per plan after. Changing
  it would move the footer for a second reason in one change and make
  neither move readable.
- **Making `--archived` fail on anything.** It is report-only and always
  exits 0; that is a deliberate property of a sweep and this item does
  not touch it.

### Doc impact

- `tools/README.md` — the `close_check.py` row states what `--archived`
  reads, since it is the one live document that describes the sweep and
  currently implies it reads each plan whole (Item 4).
- `docs/practice-audit-2026-09-04.md` — the close-check passage gains
  the sweep's own limitation alongside the two 19K.1 recorded, so the
  document that says what gates a merge does not describe a checker
  reading more evidence than it does (Item 4).
- `docs/status.md` — row when the item closes (Item 4).

---

## Item 5 — a manifest can only commit to `spec/` and `docs/`

### Opportunity

`COMMITTED_PATH` (`tools/close_check/_manifest.py:33`) is
`` `((?:spec|docs)/[A-Za-z0-9._/-]+\.md)[^`]*` ``. Item 1 made `guide/`
paths visible; every other root is still silently dropped, including
`tools/README.md` — **the one live document that describes the close
check itself**.

19K.4's own close reported `2 committed path(s)` against a three-bullet
manifest, which is the sentence Item 1 was opened on, one item later.

This is **known rather than new**. 19G.8's `docs/status.md` row records
that 19G.6's bullets "name `tools/` and `.claude/` paths the regex never
matched", and three archived manifests carry an explicit aside —
*(for the human — outside the script's `spec/` + `docs/` regex)* — which
is the author writing a prose escape hatch around the tool, the shape
19G.8 removed for `cites:`.

Measured 2026-09-11 across every live and archived plan: **16** such
paths. But the count is the least interesting thing about them.

| Where in the bullet | Count |
|---|---:|
| Leading position — a commitment | **3** |
| After the dash — a citation | **13** |

The 13 are bullets committing to a `spec/` file and naming a code path
as the *content* of the edit: "name the `app/services/assignments/`
package, not the retired module path"; "one sentence, new routing
modules must be registered in `app/web/spec_registry.py`". **Matching
anywhere would invent 13 commitments nobody made**, and one of them —
`tests/integration/test_extracts_round_trip.py` — no longer exists, so
C2 would fail an archived plan that did nothing wrong.

### Decision

**A path under a known repo root counts in the leading position only,
and is verified like a `spec/` path.**

The leading-position rule is 19G.4's, already settled for bare
root-level names, and it is right here for the same measured reason: a
path before the dash is the bullet's subject, a path after it is nearly
always prose.

**Verified rather than `NOTED`.** `guide/` abstains because a plan file
legitimately archives and a checklist row cannot be confirmed by a diff.
Neither applies to `tools/README.md` or a workflow file: they stay where
they are, and "was this edited in the window" is exactly the right
question. Measured, it is also the answer that works — 19K.4's bullet
passes C2 and C3 on the real edit.

**Rejected: matching a root path anywhere in the bullet**, as
`spec/` and `docs/` paths are matched. Rejected on measurement, not
taste: 13 of the 16 would become commitments the author never made.

**Rejected: "any backticked path that resolves on disk", with no root
list.** That is how bare names resolve (19G.4, "no list to maintain"),
and it is wrong here in a way that is invisible: a *deleted* path would
stop resolving and silently stop being a commitment, which is precisely
what C2 exists to catch.

### Semantics

- **The root list is explicit**: `app`, `tests`, `tools`, `alembic`,
  `.github`, `.claude`. `spec/` and `docs/` keep their own rule,
  `guide/` keeps `NOTED`.
- **A directory is a commitment.** Manifests commit to packages and
  folders — `.github/workflows/`, `app/services/assignments/` — so C2's
  existence test is `exists`, not `is_file`. `is_file` called every one
  of them missing; the bug was unreachable until these became
  commitments.
- **`cites:` reaches the new paths**, and C7 asks whether the bullet
  *names* a path rather than whether it commits to it — so `_all_paths`
  searches the whole bullet for root paths even though only the head
  makes a commitment. Head-only there would fail C7 on every correct use
  of the escape for a root path: unusable exactly where the 13
  citations need it.
- **No existing verdict moves.** Asserted over every id, not hoped for.

### Judgment calls — decided

- **2026-09-11 — the three archived "for the human" asides stay as
  written.** They sit after the dash, so they remain invisible, and
  making them commitments would retro-apply C3 to closed plans. They are
  a record of the gap, and they read better as one.

### Blast radius (measured)

Taken 2026-09-11 at `c42b9b4f`.

| What | Count | Command |
|---|---:|---|
| Non-`spec`/`docs` paths in manifests | 16 | the parse above |
| …in the leading position (become commitments) | **3** | the parse above |
| …after the dash (stay prose) | 13 | the parse above |
| Plans affected | 2 (`18Q`, `19K.4`) | the id sweep |
| Ids checked for verdict movement | 143 | every segment + item manifest |
| Repo roots, excluding build artefacts | 6 | `ls -d */ .*/ ` |

### Status — 2026-09-11

Landed as the one rung planned. Every figure in the blast-radius table
held: 3 leading-position paths, 13 citations, 2 plans affected, 0
verdicts moved across 143 ids.

**Decisions confirmed at build:**

- **Verified, not `NOTED`.** The abstaining status Item 1 built exists
  because a `guide/` path legitimately archives and a checklist row
  cannot be confirmed by a diff. Neither is true of `tools/README.md`,
  and the measurement agreed: 19K.4's bullet passes C2 and C3 on the
  real edit.
- **An explicit root list**, against the bare-name precedent of
  resolving on disk. Resolution would make a deleted path *silently*
  stop being a commitment, which is the one failure mode C2 exists for.

**Two bugs the item surfaced that the plan did not predict**, both
unreachable before it and both found by a test rather than by reading:

1. **C2 used `is_file`**, so every committed directory read as missing —
   `.github/workflows/` in 18Q, `app/services/assignments/` in 19C. It
   could not bite while such paths were invisible; making them
   commitments made it reachable in the same change.
2. **C7 would have failed every correct `cites:` on a root path.**
   `_all_paths` answers "does the bullet name this path", which is C7's
   question, and searching only the head for root paths made the escape
   unusable exactly where the 13 after-dash citations need it. Found
   because a test asserted the escape worked, not because the code was
   re-read.

**Measured, not assumed:**

| Claim | Measurement |
|---|---|
| No verdict moves | **143 ids** — every segment and item manifest in the repo — run against `origin/main`. **141 byte-identical, 2 changed, 0 exit-code flips.** |
| The 2 that changed | `18Q` 12 → 14 committed paths, `19K.4` 2 → 3. Exactly the 3 leading-position paths, in the 2 plans that carry them. |
| Guards are not vacuous | **5 mutations, 5 caught** — matched anywhere, dropped entirely, `is_file` restored, a root missing from the list, and `_all_paths` back to head-only. |

**`spec-writer` pass (checker, 2026-09-12) — and it found a bug in the
shipped regex by disbelieving a number.**

The published count — 16 paths, 3 leading, 13 citations — **did not
reproduce against the code**: the checker got 20/3/17. Re-measuring at
the pinned SHA settled which was wrong, and it was the code. The shipped
`COMMITTED_ROOT` ended `[A-Za-z0-9._/-]*`, so a bare `` `tools/` `` matched
— a folder named in a sentence ("the `tools/` and `.claude/` paths the
regex never matched"), not a path. Four such mentions across the archive,
and they are exactly the gap between the two counts. Harmless while they
all sat after the dash, and a commitment to an **entire top-level
directory** the first time one led a bullet. Now `+`, with a test for
both directions; `.github/workflows/` still matches, its `workflows/`
coming after the root.

With that fixed, 3/13/16 reproduces at `c42b9b4f` exactly as published.
**The prose was right and the code was wrong** — the reverse of the usual
drift, and only findable by someone recomputing the number rather than
reading around it. This is the third consecutive item where the useful
finding came from a figure refusing to reconcile.

Three documentation gaps, all upheld:

- **`.claude/skills/segment-plan/SKILL.md` and
  `guide/segment_plan_template.md` state two of the four path rules** —
  missing `guide/`'s `NOTED` (19K.1) and this item's roots. These are
  what a plan author actually reads, so they were the live drift, and
  the manifest gained both bullets. The skill file is committable at all
  only because of this item, which is a neat closing of the loop.
- **`tools/README.md` never documented C5**, three touches after it was
  added.
- `docs/practice-audit-2026-09-04.md`'s C2 line did not say a directory
  counts, and its `guide/` figure (80 across 35) now measures 78 across
  35 — corpus drift on a dated measurement, now dated in the prose
  rather than corrected into a second undated one.

**The re-run after the fix:** 144 ids, **139 byte-identical, 2 changed
(`18Q`, `19K.4`), 2 date-only** (`docs/status.md`'s date rolled to
2026-09-12 inside an unrelated C3 message), **1 expected flip** —
`19K.5`, which does not exist on `main`.

**The trial was checked for vacuity before its result was believed.**
The first sweep reported *0 verdict flips*, which is the answer a rule
that does nothing also gives. Confirming the rule bit — 19K.4 reading
`3 committed path(s)` where it had read 2 — is what made the zero
meaningful, and it immediately exposed bug 1 above. A clean result and
a no-op are indistinguishable until you check which one you have.

**One caveat on the zero.** 18Q gains a C2 failure under the naive
`is_file` version and its exit code still does not move, because 18Q was
already failing C3 on `docs/azure_provision.md` for an unrelated,
pre-existing reason. The zero was true but partly lucky, and it is
recorded as such rather than banked.

### PR ladder

1. **Leading-position root paths, verified.** The regex, the `exists`
   fix, the `cites:`/C7 interaction, and tests. *Must not* change the
   `spec/`/`docs/` rule, the bare-name rule, or `guide/`'s `NOTED`.

### Definition of done

- A leading-position path under a known root is a committed path;
  the same path after the dash is not.
- A committed directory passes C2.
- `cites:` works on a root path, in both positions.
- No verdict moves across all 143 ids — asserted, not assumed.
- `.venv/bin/pytest` and `ruff check .` both pass in the agent container
  before pushing.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19K.5` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` records intended vs done
- `docs/status.md` row added

### Open questions

None. The two shape choices — leading position only, verified rather
than noted — are settled above with their rejected alternatives and the
measurements that rejected them.

### Out of scope

- **Retro-fitting the three archived "for the human" asides.** See
  Judgment calls.
- **The module-coverage `note` lines**, which warn about touched `app/`
  modules missing from a manifest. A different mechanism answering a
  different question, untouched.

### Doc impact

- `tools/README.md` — the `close_check.py` row states which roots a
  manifest may commit to and that the rule is leading-position (Item 5).
- `docs/practice-audit-2026-09-04.md` — the close-check passage's "what
  it verifies" list gains the widened path rule (Item 5).
- `.claude/skills/segment-plan/SKILL.md` — the `Doc impact contract`
  section states all four path rules, not the two it had; this is the
  file a plan-writing agent reads to know what counts as a commitment,
  so it is the one that matters most (Item 5). *Committable at all only
  because of this item.*
- `guide/segment_plan_template.md` — the same two-clause description,
  in the comment a new plan is copied from (Item 5).
- `docs/status.md` — row when the item closes (Item 5).

---

## Item 6 — a specificity collision in `base.html` is invisible until a value changes

### Opportunity

`app/web/templates/base.html` is 4,732 lines and owns the inline CSS for
the entire app — deliberately, per `CLAUDE.md` and `spec/architecture.md`:
no stylesheet, no build step. That choice has held, and this item does
not propose reversing it.

What it costs is recorded in the 11sep assessment's §5 as **the single
largest structural risk**, and the evidence is a defect rather than a
worry. During 19J.9 the rule `body.ui-v2 .table-pager-step` was **dead from
rung 1 until the fifth of the item's seven merges**: it and `body.ui-v2 .btn-icon` are both specificity
(0,2,1), so source order decided, and `.btn-icon` sits later. Nobody
could see it, because the loser's declarations happened to match what the
winner already set. It surfaced only when someone asked for a bigger
glyph and the glyph did not change.

Measured 2026-09-12 at `40a0b663`:

| What | Count | Command |
|---|---:|---|
| Lines in `base.html` | 4,732 | `wc -l` |
| Rule selectors | 618 | `grep -c '^\s*[.#a-z][^{]*{'` |
| …carrying `body.ui-v2` | 410 | `grep -c 'body\.ui-v2'` |
| Existing tests over its CSS tokens | **1** | `tests/unit/test_reserved_shade.py` |

**Two-thirds of the rules live in one `body.ui-v2` layer**, which is
exactly the condition that makes ties common: a `body.ui-v2 .a` and a
`body.ui-v2 .b` tie at (0,2,1), and any element carrying both classes
resolves by source order alone.

### Decision

**Make ties visible rather than remove them**, by resolving the cascade
**in Python** rather than in a browser: render pages through
`TestClient`, collect each element's class set from the markup, parse
the `<style>` block, compute specificity per selector, and fail where a
canonical role's declaration loses to an equal-specificity rule that
comes later.

Scope it to **canonical classes that co-occur on one element** — the
`.btn` roles of `spec/ui_elements.md` §6, which is the shape 19J.9's
collision had (`btn-icon` and `table-pager-step` on the same pager
step). Those are selectors the repo has committed to keeping stable, so
a tie involving one is a defect by definition; a tie between two ad-hoc
classes may be intentional.

**§10's layout primitives are explicitly out of this rung, and the
reason is structural rather than a matter of effort.** `.page-grid`'s
eight rules are *all* combinators — `.page-grid .card`,
`.page-grid > .card-tl` and so on — and `page-grid` and `card` **never
appear on the same element** (0 matches across `app/web/templates/`).
A same-element check cannot ask whether such a rule ties, because there
is no element whose class list contains both names. `base.html` has
**35** descendant-combinator selectors of that shape beyond the
`body.ui-v2 X` pattern. Covering them needs real ancestor matching over
a parsed DOM tree, which is a bigger resolver and a separate rung —
named here rather than left for a reader to discover when the check
silently says nothing about §10.

**Rejected: reading computed style from a browser** — which is what this
item's first draft specified, until the prerequisite was checked. The
suite contains **zero** browser tests, **neither CI workflow installs a
browser**, and `playwright` is declared in **neither** `pyproject.toml`
nor `requirements.txt`; it imports in the agent container only because
the *environment* pre-installs it. So that test would pass here and
fail or skip in CI — a guard that runs only in the author's sandbox,
which is the shape that let `_archive.py` read one manifest of thirteen
for six days (19K.4). Adopting it would mean declaring `playwright` and
adding a ~100 MB browser download to CI for a single test, which sits
badly beside `CLAUDE.md`'s no-build-step posture.

**The Python route is also narrower, not merely cheaper.** Computed
style reports the winner; it does not report that there *was* a tie. The
resolver targets exactly the condition that bit 19J.9 — equal
specificity, decided by source order — and can name both rules. Co-
occurrence, the one thing CSS alone cannot supply, comes free from the
rendered markup: a probe on the Assignments page finds class sets like
`pill + pill-empty`, `pill + pill-warning` and `btn + disabled` directly
in the HTML.

**Rejected: extracting a stylesheet — on relevance, not on cost.** The
first draft of this item rejected it as "a large diff", which is wrong
and worth correcting rather than quietly fixing: `base.html` has **one**
`<style>` element — lines 24–3894, **3,869 lines** of its 4,732 —
containing **zero** Jinja constructs, and `app/main.py` already mounts
`/static` with cache handling. Extraction is close to a cut-and-paste.

It is rejected because it **does not touch the cascade**. A tie at
(0,2,1) resolves by source order in a `.css` file exactly as in a
`<style>` block, so 19J.9's rule would have been just as dead. Nor does
tooling rescue it: stylelint's `no-descending-specificity`, the
canonical rule for this family, flags a *lower*-specificity selector
following a higher one — 19J.9 was an **equal**-specificity tie, which
it does not cover. **That last is asserted, not run**: there is no
stylelint in this repo to test it against, so treat it as a reading of
the rule rather than a measurement, and check it before relying on it.
There is also no JS toolchain at all here, so the rule would
arrive with npm and a node CI step attached.

There **is** a real argument for extraction, and it is about page weight
rather than correctness. It is 19K.9's, judged on its own terms; smuggling
it in here as a fix for a defect it does not fix would buy the
architecture change on a false premise.

**Rejected: a source-order lint.** "`body.ui-v2 .btn-icon` must precede
`body.ui-v2 .table-pager-step`" encodes today's answer, not the rule,
and a reader who changes the order correctly would have to change the
test to match — a check that has to be edited whenever the thing it
checks changes is not a check.

**Rejected: raising specificity on the canonical roles.** It works
(19J.9 fixed its own case with `body.ui-v2 .btn-icon.table-pager-step`)
and it scales badly: each rescue raises the bar the next rule has to
clear, and nothing records why the number is what it is.

### Semantics

- **The test resolves the cascade, it does not match source text.**
  `test_reserved_shade.py` matches source and could not have caught
  19J.9's collision; the difference is that this one computes
  specificity and compares rules against elements that actually carry
  both classes.
- **Co-occurrence comes from rendered markup, not from the CSS.** Two
  selectors tying matters only if some element carries both classes,
  and only a rendered page knows that. This is why the resolver needs
  `TestClient` and not just a CSS parse.
- **A tie is a failure only where a canonical role loses.** Two
  non-canonical classes tying is out of scope and must stay passing, or
  the check becomes noise the first week.
- **One theme is enough for the winner, and that is a measurement not
  an assumption.** `:root[data-theme="dark"]` (lines 278–401) holds
  **106 custom-property declarations and zero component rules**, so
  dark mode changes what a `var()` resolves to *after* the cascade has
  already picked a winner. The only two theme-scoped component
  selectors in the file (`:root[data-theme="dark"] body.ui-v2
  .guide-figure img[…]`) target guide figures, not canonical roles. So
  which rule wins is theme-invariant today. **The first draft of this
  item said the opposite**, conflating winner-detection with token-value
  inspection — which is `test_reserved_shade.py`'s job, not this one's.
  Re-check the claim if a component rule ever lands inside the dark
  block.
- **It runs wherever the suite runs**, including both CI tracks, because
  it needs no browser. That is the property the browser version lacked
  and the reason the method changed.
- **What this method cannot see, stated up front.** A CSS parse plus a
  flat class list is *incomplete* in four ways and *unsound* in none of
  them, provided the check only ever reports a tie it can prove:
  **inline `style=`** always beats any class selector and is never in
  the `<style>` block — and there are inline styles on `.page-grid`
  elements setting the very property its canonical rule sets
  (`session_new.html:16`); **14 `@media` blocks**, whose rules apply
  only at some viewports, so comparing them against unconditional rules
  needs care in both directions; **`:hover` / `:focus`** state selectors,
  which add specificity but apply conditionally; and **shorthand versus
  longhand** (`background` against `background-color`), where an exact
  property-name match would miss a real override. `!important` and
  `@supports` do not occur in `base.html` at all today (0 each), which
  is worth re-checking rather than assuming at build time. Each of these
  is a reason the check may stay silent where a browser would speak;
  none is a reason it would report a tie that is not there.
- **A hand-rolled resolver can be wrong**, which is the cost of this
  route. The mitigation is in the Definition of done and is not
  optional: reintroduce 19J.9's actual collision and require the test to
  fail on it. A resolver that cannot catch the defect it was built for
  is worse than none, because it reports safety.

### Judgment calls — decided

- **2026-09-12 — the scope claim was narrowed after a checker found it
  overreached.** The revision said the check would cover "the `.btn`
  roles (§6) **and the layout primitives (§10)**". It cannot: `.page-grid`
  is a named canonical primitive whose every rule is a combinator, and
  whose two class names never share an element, so a same-element check
  is structurally blind to it — along with 34 other selectors of that
  shape. Narrowed to same-element canonical classes, with combinators
  named as a separate rung. *Changing the method changed what the method
  can reach, and the scope sentence was carried over unexamined* — the
  same shape as reusing a figure after re-measuring, one level up.

- **2026-09-12 — the method changed from a browser to Python, on a
  prerequisite check rather than a preference.** The first draft
  specified reading computed style. Asking "do we have everything needed
  for this?" before starting found that the suite has no browser tests,
  neither CI workflow installs a browser, and `playwright` is declared
  nowhere — it imports here only because the environment provides it.
  The test would have been green in the container and absent from CI.
  *The prerequisite that matters is not "can I run this?" but "can CI?"*,
  and the two answers differ whenever the sandbox is richer than the
  pipeline — which is exactly the case here.

- **2026-09-12 — `base.html` does not go on §9's watchlist.** It is a
  template, not a production module, and the split its size would
  otherwise imply is precisely the one the architecture forbids. The
  risk is real and the remedy is not a split, which is why this item
  exists instead.

### Blast radius (measured)

Taken 2026-09-12 at `40a0b663`. See the table above; additionally:

| What | Count | Command |
|---|---:|---|
| Canonical `.btn` roles in `spec/ui_elements.md` §6 | to be enumerated at rung 1 | read the spec |
| Templates extending `base.html` | **34** | `grep -rl 'extends "base.html"' app/web/templates \| wc -l` |
| Pages a render-based test must visit | ≤ the number of canonical roles | one page per role, not one per page |

Taken 2026-09-12 at `72e88096`, and the reason the method changed:

| What | Count | Command |
|---|---:|---|
| Browser-based tests in the suite | **0** | `grep -rl playwright tests/ \| wc -l` |
| CI workflows installing a browser | **0** | `grep -n 'playwright\|chromium' .github/workflows/*.yml` |
| `playwright` declared as a dependency | **no** | absent from `pyproject.toml` and `requirements.txt` |
| Multi-class elements on one rendered page | present, e.g. `pill + pill-empty`, `btn + disabled` | `TestClient` + `re` over `class="…"` |

### Status — 2026-09-12

Built as the one rung planned: `tests/integration/test_cascade_ties.py`,
**16 tests**, no browser, no new dependency, running in both CI tracks.

**The mandatory mutation passes.** 19J.9's collision reintroduced into
the real `base.html` — `body.ui-v2 .btn-icon.table-pager-step` reduced to
`body.ui-v2 .table-pager-step`, which is what the selector looked like
while the rule was dead — and the end-to-end check fails, naming both
rules and **both** dead properties (`color`, `font-size`). `base.html`
restored; `git diff` clean.

**The check found a live tie on its first run, and it improved the
design rather than the stylesheet.** `body.ui-v2 .table-pager-cluster`
(`display: inline-flex`) and `body.ui-v2 .table-pager-cluster-bottom`
(`display: flex`) both tie at (0,2,1) on an element carrying both
classes, and the `-bottom` rule wins on order. It is **deliberate**, and
`base.html` says so in a comment beside it: below the table the cluster
is the only thing on its line, so it takes full width.

That is the discriminator the plan did not have. A **variant that comes
later and wins** is the CSS idiom working. A **specialisation that comes
earlier and loses** is 19J.9. `_is_variant_of` encodes it on the repo's
own naming convention (`X-bottom` extends `X`, matched on the `-`
boundary), and two tests pin both directions — because suppressing
variants outright would hide exactly the defect the item exists for.
**Nothing in `base.html` changed**, per the ladder.

**Two vacuity findings, both caught before pushing.**

1. **The end-to-end check could not see the defect it was built for.**
   With an empty session the fixture collected 46 class sets and **not
   one** carried `btn-icon` or `table-pager-step` — the pager renders
   only above the page size. The check would have passed against 19J.9's
   own collision. Fixed with a 220-row roster, and the guard is now a
   **separate named test** asserting the classes are covered: a
   mutation proved that an assertion living inside the check it guards
   can be deleted invisibly.
2. **The `@media` test pinned nothing.** With a single rule inside the
   block, the brace walk drops the nested rule whether or not the
   at-rule is skipped, so the test passed with the skip mutated away.
   A *second* rule inside the block is what leaks; the fixture now
   carries one.

**Measured, not assumed:**

| Claim | Measurement |
|---|---|
| The arithmetic is right | `_specificity` reproduces the two values `spec/ui_elements.md` §6 states in prose — `body.ui-v2 .btn-icon` (0,2,1), `body.ui-v2 .btn-icon.table-pager-step` (0,3,1). |
| It runs where it matters | No browser, no new dependency. The check resolves **236** selectors — those that are both simple and outside `@media`. The first draft of this row said *253 of 618 … simple enough to resolve*, which counted simple selectors **including** the 17 inside `@media` blocks that `_top_level_rules` deliberately discards. "Simple enough to resolve" implied the check reaches them; it does not. |
| Guards are not vacuous | **9 mutations on the resolver, 9 caught** — specificity ignoring classes, `@media` rules treated as unconditional, combinators accepted as simple, the variant rule applied in both directions, the canonical filter removed, the `<style>` element located by the naive regex, and the roster shrunk below the page size. Plus the collision mutation above, on the real file. |
| Nothing broke | Full suite **3,790 passed**, 16 skipped. |

**`spec-writer` pass (checker, 2026-09-12) — it found a false positive,
which is the one kind this check cannot afford.** Two upheld findings:

1. **`!important` beat the resolver, not the other way round.** Given two
   tied rules where the *earlier* one carries `!important`, real CSS
   gives it the win — and `find_ties` reported it dead. That contradicts
   the module docstring's central promise, *"none can make it report a
   tie that is not there"*, and a false positive is the failure mode the
   exclusions are chosen to avoid. **Fixed rather than documented**:
   importance is compared before order, with tests for both directions,
   because skipping every property that mentions `!important` would
   silence a real defect. `base.html` has **zero** `!important` today,
   so the case was latent — a checker constructed it.
2. **A count that implied more coverage than it had.** "253 of 618
   selectors are simple enough to resolve" counted simple selectors
   anywhere in the sheet, including the 17 inside `@media` that the
   parser discards on purpose. The check resolves **236**. Corrected
   with what it used to say.

It also **disconfirmed the suspicion this item was most worried about**:
`_ELEMENT` does not over-count inside hyphenated class names, because it
requires a boundary character that `.` is not. Verified against `.a.b.c`,
`.a[data-x]`, `div.a` and every canonical selector.

**One dormant looseness, recorded rather than fixed.** `_is_variant_of`
matches on the `-` boundary, so `.btn-row`, `.btn-pair`, `.btn-reset`
and `.danger-solid` all read as "variants" of `.btn` / `.danger` by
name, which they are not. It costs nothing today — none of those pairs
co-occurs on a rendered element at equal specificity — but the next
`.btn-*` class that *does* co-occur with a bare `.btn` would be
suppressed silently. Whoever adds one should check this first.

**A note for whoever extends this.** The `<style>` element is located by
walking lines, not by regex, because `base.html:9` carries a Jinja
comment whose *text* contains the literal string `<style>` — a
non-greedy regex matches that and swallows the no-FOUC script as CSS.
That cost a wrong figure in 19K.9's own plan, and the mutation which
restores the naive regex is one of the seven.

### PR ladder

1. **Resolve the canonical roles against the cascade, in Python**, in
   both themes, and fail on a tie a canonical role loses. Mutation:
   restore 19J.9's collision and watch it fail — the resolver is not
   trustworthy until it has caught the defect it exists for. *Must not*
   change any rule in `base.html`: if the check finds a live collision,
   that is a finding for `## Status` and a second rung, not a silent fix
   inside the rung that added the check. *Must not* add a browser or a
   JS dependency, which is the whole point of the method.

### Definition of done

- A canonical `.btn` role whose declared value loses to a
  same-specificity rule **on an element carrying both classes** fails a
  test, **with both rules named** — a failure that says only "something
  overrode this" is a worse report than the browser version it replaced.
- The check says nothing about combinator-based rules, and the item says
  so rather than letting silence read as coverage.
- The test runs in **both CI tracks** with no browser and no new
  dependency — asserted by CI going green, not by it passing here.
- 19J.9's collision, reintroduced, fails it — asserted, not assumed.
- Two non-canonical classes tying does **not** fail it.
- Any live collision the check finds is recorded in `## Status`, fixed
  or waived with a reason, and not folded into rung 1.
- `.venv/bin/pytest` and `ruff check .` both pass in the agent container
  before pushing.
- `spec-writer` run **before** pushing (the order adopted at 19K.3).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19K.6` exits 0; any warning adjudicated
- `## Status` records intended vs done
- `docs/status.md` row added

### Open questions

- **Whether a live collision exists today.** Unknown until the check
  runs, and the answer changes the item's size. Rung 1 finds out; the
  ladder above says what happens either way.

### Out of scope

- **Splitting `base.html`.** See Decision.
- **The `.btn` vocabulary itself**, settled at 19B and 19J.7.

### Doc impact

- `spec/ui_elements.md` — §6 records that the canonical roles are
  resolved against the cascade by a test, and what a tie means (Item 6).
- `docs/practice-audit-2026-09-04.md` — the inventory of automated
  checks gains the row (Item 6).
- `docs/status.md` — row when the item closes (Item 6).

---

## Item 7 — the muted-text contrast failure, and the entry that records it

### Opportunity

`docs/known_limitations.md` §Accessibility says:

> The `--text-muted` colour token fails WCAG AA contrast and is still
> used on operator chrome / breadcrumbs; flagged for a later pass.

**There is no `--text-muted` token.** `grep -c 'var(--text-muted)'`
across `app/web/templates/` returns **0**. The entry names something
that does not exist, which is the more interesting half of this item:
the one live user-facing fault in `known_limitations.md` has been
recorded for months against a token nobody can find.

Computed 2026-09-12 at `40a0b663` — WCAG 2.1 relative luminance over the
real token values in `base.html`:

| Token | Value | On | Ratio | AA normal | AA large |
|---|---|---|---:|---|---|
| `--text-subtle` | `#6b7280` | `--white` | **4.83** | pass | pass |
| `--text-subtle` | `#6b7280` | `--surface-muted` `#f5f5f7` | **4.44** | **fail** | pass |
| `--text-dim` | `#9ca3af` | `--white` | **2.54** | **fail** | **fail** |
| `--text-dim` | `#9ca3af` | `--surface-muted` | **2.33** | **fail** | **fail** |

Dark mode is better and not clean: `--text-subtle` (`#a9b4c6`) is
6.71–8.83 everywhere, and `--text-dim` (`#6f7b8e`) is **3.28–4.31** —
fails AA normal, passes AA large.

So the real finding is **two** failures of different severity, neither
described by the entry:

- **`--text-dim` in light mode is the serious one** — 2.33–2.54 is not
  marginal, it is roughly half the required ratio.
- **`--text-subtle` fails by 0.06** on the muted surface only, and
  passes on white. A different kind of problem, and possibly a
  different answer.

Usage, measured: **21 `color:` uses** of `--text-dim` across
`app/web/templates/`, plus **6 decorative uses** (a 3px divider, a
striped pattern, a border) where WCAG imposes no text requirement at
all. `--text-subtle` is used 34 times in `base.html`.

### Decision

**Fix the token values, not the call sites, and separate the two
failures.** A value change reaches every one of the 21 call sites at
once; editing call sites would leave the token failing and make the next
use of it fail again.

**The decorative uses are excluded, by rule and not by judgment.** WCAG
1.4.3 applies to text; a 3px divider and a striped background are not
text. Those 6 stay as they are, and the item says so where it changes
the rest, or the next reader will "fix" them and lighten a divider for
no reason.

**Rejected: waiting for the deployment.** Nothing here needs Azure. It
is in `known_limitations.md` under a heading that is otherwise entirely
infrastructure constraints, which is probably why it has sat: it
inherited the blocked-ness of its neighbours without sharing it.

**Rejected: a blanket darkening of both tokens.** `--text-subtle` passes
on white and misses by 0.06 on one surface; treating it identically to a
token at 2.33 would change the app's whole muted register to fix a
rounding error. The two get separate answers.

### Semantics

- **The threshold is AA normal (4.5:1)** for text under 18.66px or not
  bold, AA large (3:1) above it. Several `--text-dim` uses are on
  `--fs-tiny` (0.75rem), so the stricter bar applies.
- **Both themes are in scope**; the dark values are separate tokens and
  `--text-dim` fails AA normal there too.
- **A token change is a visual change everywhere it is used**, so this
  is one of the changes `CLAUDE.md` says must be verified on the Azure
  dev slot rather than claimed from the suite.
- **`known_limitations.md`'s entry is rewritten to name what is true**
  — which tokens, which ratios, which surfaces, and that the decorative
  uses are deliberately untouched.

### Judgment calls — decided

- **2026-09-12 — the entry is corrected rather than struck.** It
  records a real fault under a wrong name; deleting it would lose the
  fault, and striking it would imply the fault went away.
- **2026-09-12 — the name is `--decor-muted`, for what it does rather
  than where it sits.** It lands in the Borders & focus cluster beside
  `--marker-neutral`, which is the same kind of thing; naming it for
  the cluster (`--border-*`) would have claimed it paints boundaries,
  which it does not.
- **2026-09-12 — `--slate` was edited rather than a near-duplicate
  primitive added.** Repointing was forced for `--text-dim`, whose move
  is large enough to wreck `--card-help-border`; it was not forced for
  `--text-subtle`, whose only other consumer is
  `--btn-secondary-border`, a boundary held to 3:1 that the same edit
  improves from 4.83 to 5.61. A second gray 0.03 of luminance from the
  first would cost a reader more than it buys.
- **2026-09-12 — `--text-link` was folded in; the other eleven were
  not.** Author, mid-build. The link fix needed no new primitive
  (`--blue-glow-soft` already existed) and no design decision. The
  remaining eleven each move a *family* — the reserved accent, or every
  status tint at once — and belong to whoever takes that decision.

### Blast radius (measured)

Taken 2026-09-12 at `40a0b663`.

| What | Count | Command |
|---|---:|---|
| `color:` uses of `--text-dim` | **21** | `grep -rn 'color: var(--text-dim)' app/web/templates/` |
| Decorative uses of `--text-dim` (out of scope) | **6** | `grep -rn 'background: var(--text-dim)\|var(--text-dim) [0-9]'` |
| Uses of `--text-subtle` in `base.html` | **34** | `grep -c` |
| Templates outside `base.html` using `--text-dim` | 2 | `instruments_index.html`, `session_observers.html` |
| Existing tests over the colour tokens | **1** | `tests/unit/test_reserved_shade.py` |

### Status — 2026-09-12

**The shape changed: two answers became one token.** The Decision said
"the two get separate answers" and rejected "a blanket darkening of
both tokens". Neither is what shipped. Asked for the options if the
hierarchy were abbreviated instead, the measurement said the collapse
is both cheaper and cleaner: `--text-dim` retired, its 20 text uses
taking `--text-subtle`, its decorative uses taking a new
`--decor-muted` that holds the *same* primitives so nothing decorative
moves. That is a shape change rather than a value choice, which is why
it is recorded here and the Decision stands as written.

**Two errors in this item's own blast radius, both found by running
the commands rather than reading them.**

- The table's `grep 'color: var(--text-dim)'` counts **21** because it
  also matches `border-color:` at `base.html:784`. The real split is
  **20 text, 7 non-text** — not 21 and 6.
- Of the 7 non-text uses, **2 were dead code**. `.btn-cta.disabled`
  painted `--text-dim` as a *fill*, and is overridden on every page by
  `body.ui-v2 .btn-cta.disabled`; all **34** templates extending
  `base.html` carry `ui-v2`, none doesn't. The rule was deleted rather
  than repointed. Residue: **5** live decorative uses.

**The Opportunity's central claim is half right, and the other half is
the better finding.** "There is no `--text-muted` token" is true today
and was false when the entry was written: `guide/archive/semantic_tokens.md`
records `--slate-soft #9ca3af → --text-muted` in the flat scheme, and
`docs/status.md`'s 14A PR 5 row names the token and the ratio
(`~2.5:1`) that still measures 2.54 on white. 19C Item 6 renamed it to
`--text-dim` and nothing updated the entry. So it was **stale, not
fictitious** — the entry was not recorded against a token nobody can
find, it was recorded against a token that was later renamed out from
under it. Per *never rewrite intent* the Opportunity keeps its words.

**The blast radius omitted `tools/` entirely.**
`tools/theme_preview.html` and `tools/theme_customizer.html` are
generated from `base.html` and carry the whole palette; both regenerate.
Their generators carry hand-written references the lift does not
reach — the customizer's "Dim / card" contrast row, 4 element-facet
map entries, and 12 uses in the two tools' own chrome CSS — and
`tools/theme_variants.gen.py` carried a docstring asserting
`--slate-dim` is also `--text-dim` in dark. **Nothing tests
generator-versus-output drift**, so every one of these was silent.

**The scope widened twice, each time because the narrower version was
shown to be lying by omission.** This is the finding of the item.

1. Checking the fix on the token under repair found **`--text-link`
   at 4.22** on `--surface-muted` in dark — a second live AA failure,
   in the same cluster, that four months of an entry naming one token
   had never mentioned. Fixed here at the author's instruction:
   `--blue-glow` → `--blue-glow-soft`, an existing primitive, **5.53**.
2. Widening to *the Text cluster against every surface* found nothing
   further — and was **still wrong**. `--nav-home-bg` (`#e5e7eb`) is
   darker than any `--surface-*` token and carries muted text on the
   Session Home anchor: **3.90** before this item, **4.04** after the
   first fix. A cluster-versus-cluster sweep never reads that pair at
   all: its worst case was 4.56, on a *surface*, which passes while the
   anchor sits at 4.04. (Both belong to the interim `#667080`; the
   shipped `#616874` is 5.11 and 4.53.) *A check whose scope is a token
   list will pass while the thing it is named for fails.*

So the check became a sweep over **every pair the palette forms**,
gathered four ways rather than listed — 73 pairs, 146 theme-resolved
pairings — and `--slate` went to `#616874` rather than `#667080`, so
the floor holds against all of them with margin instead of against the
enumerated ones by 0.06.

**The full audit: 12 failures, of which 1 is now fixed and 11 are
recorded.** None of the 11 is body text; they are accent fills
(2.54–3.68, six pairs, all resolving through the reserved
`--blue-glow`) and saturated text on its own pale tint (3.32–3.95,
five pairs, two shared values). Each is pinned in `KNOWN_SHORTFALLS`
at its measured ratio, in **both** directions: a regression fails, and
so does a fix, because a fix must delete the entry rather than leave a
stale number behind it — which is precisely how the entry this item
repaired went wrong.

**A vacuity caught in my own negative probe.** The first mutation run
reported 9 of 9 caught, and the one *negative* probe — `border-color`
must not trip the text check — reported a failure. It was not a false
positive: an earlier mutation had been reverted with `git checkout`,
which restored the file to `HEAD` and silently undid this item's edits,
so mutations 3–9 all ran against a dirty tree and every "2 failed" was
one intended failure plus one contaminant. Re-run clean from a
snapshot: **11 mutations, 11 caught by the intended test, the negative
probe silent.** *Reverting a mutation with the version-control tool
reverts the work as well when the work is not yet committed.*

**The `spec-writer` pass, run before the push, upheld four flags and
found a fifth this item did not cause.**

- **Two figures in the new spec section reproduced against nothing that
  ships.** "4.56" and "4.04" are both `#667080`, the *interim* `--slate`
  — the value the pair sweep rejected. Against the shipped `#616874`
  the same two measurements are 5.11 and 4.53. The prose read as if it
  described the shipped palette, so a reader recomputing it would have
  found neither number. Now named as superseded, and kept rather than
  dropped because they are the only way to check the claim that a
  surfaces-only sweep passes while the anchor fails.
- **The same clause conflated two surfaces.** "scores 4.56 there" put a
  `--surface-tint-5` figure on `--nav-home-bg`. Corrected in the spec,
  in `docs/status.md` and above.
- **The test's own docstring said 72 pairs / 144 pairings** where the
  code gives **73 / 146** — written before `ON_FILL` was added and not
  re-measured. Every *other* document this item touched has 73/146, so
  the one file that computes the number was the one stating it wrongly.
- **"Three passes" undercounted its own sources.** `ON_FILL` is a
  fourth, and the one that is hand-kept; describing it as outside the
  count while it contributes a real pair is the kind of quiet exception
  this item exists to remove. Now "three gathering passes plus one
  hand-kept map", with the coverage test named as its guard.
- **A pre-existing self-contradiction in `spec/color_tokens.md`.** The
  `--border-default` paragraph gave its previous dark ratio as
  **1.70:1**; `--slate-deep` `#3a465c` on `--ink-abyss` `#0f141b` is
  **1.95:1**, and the same document's Card-accents section already
  computed 1.95 for that identical pair. Inherited from
  `guide/archive/segment_19C_refinements.md`, live since 19C Item 8.
  Corrected here with the discrepancy named rather than silently
  overwritten: it sits in the paragraph this item's new section was
  inserted beneath, and leaving a known contradiction in a file just
  certified is worse than the small scope creep of fixing it. The light
  figure, 1.47, reproduces exactly.

The pass also **independently confirmed** three things this item
asserted: all 34 templates carry `ui-v2` *and* the surviving rule wins
on specificity ((0,3,1) against (0,2,0)) rather than on source order,
so the deleted rule was structurally dead; the 11-row shortfall table
matches `KNOWN_SHORTFALLS` exactly; and regenerating both theme pages
from their sources gives files byte-identical to the committed ones.
That last is worth its own line — this item's finding was that
*nothing tests* generator-versus-output drift, and the checker did by
hand what no check does.


**The panel became the place the audit is read** (author, after the
push of the first three commits). The 11 shortfalls were recorded in
four documents and enforced in one test; the 135 *passing* pairings
were recorded nowhere — the audit could be enforced but not looked at.
The customizer's Contrast panel already existed for exactly this and
was carrying **12** hand-listed pairs, which is the same defect one
level up: it was missing 62 of the palette's pairs, including the
`--nav-home-bg` one that was failing AA. So
the panel now renders a row per pair from `hc.collect_contrast_pairs`
— the single definition, which the test imports rather than
re-implements — with sub-AA outlined in red, a live count per group
and overall, the shipped ratio beside the live one, and the four
sources named in each row's tooltip.

Two things make that more than a bigger list. **The flagging is
computed in the browser from the live model**, so grouping is
structural (by the foreground's cluster) rather than by pass/fail: a
static "failures first" layout would be wrong the moment you remap.
And **a test asserts the generated page carries a row for every
audited pair** — not the generator's source, which would pass while
the committed page was stale. That is the generator-versus-output
drift this item found nothing tests; it is now tested for this one
surface.

**Verified in a browser, not asserted.** The suite has no JS runtime,
so the panel was driven in Chromium against the committed page: 73
rows, **0 unresolved**, **7 outlined in light and 4 in dark — 11,
exactly `KNOWN_SHORTFALLS`** — with the per-group counts summing to
the same. Then the live promise: repointing `--text-subtle` to
`--gray`, the value `--text-dim` used to carry, takes the count from
**7 to 17**, and restoring returns it to 7. Playwright is installed in
this container but **declared in neither `pyproject.toml` nor
`requirements.txt`**, so this cannot become a test without a
dependency decision — the same finding 19K.6 recorded, and the reason
the two new tests assert the *mechanism* (the class is defined,
something toggles it, every recorded shortfall has a row) and say so.

The first render was wrong in a way only looking could catch: at three
columns the labels ellipsised to `subtle → ti…`, so a reader could see
a red 3.32 and not what it belonged to. Cells widened, and the tooltip
now carries the token names rather than only the provenance.


**The second `spec-writer` pass, on the panel, found the bug the first
one could not have.** Five flags; the one that matters is a defect in
the panel's own JavaScript.

- **A stale row reading as current.** When a remap leaves a token
  unmapped or in a coupling cycle, `resolve` returns null and
  `updateContrast` **returned** — leaving that row painted with its
  last-good ratio *and* its last-good red outline, while the counts
  summed the stale class and agreed with it. So the panel stayed
  internally consistent and collectively wrong, in exactly the case
  where recomputing is the point, against prose promising it
  "recomputes live as tokens are remapped". Reproduced against the
  pre-fix page before fixing: unmapping `--lifecycle-ready-fg`, which
  carries one of the 7 outlined rows, left the count at **7**. After:
  **6**, the row cleared to `—` with a dashed `?` badge. *The promise
  a tool makes in prose is the first place to look for the case it
  does not handle.*
- **A claim of mine that does not survive `git log`**, and the most
  useful flag of the five. "The twelve had drifted to include
  `--text-dim`" is false of the twelve actually replaced: **this
  item's own earlier commit `6f39accd` had already removed that row**,
  taking the list 13 → 12. Both things are true — the list named a
  retired token, and the list was missing 62 pairs — but they were
  true a few commits apart, and compressing them into one sentence
  invented a state that never existed. Corrected in five places, the
  canonical one being `collect_contrast_pairs`' docstring that the
  rest echo. The commit message keeps the original wording; the
  correction rides the next commit rather than an amend, because the
  correction is itself part of the record.
- **One of the twelve is genuinely absent from the 73**, and the
  checker was right to refuse my "no coverage lost" framing until it
  was checked: the old list paired `--btn-destructive-fg` with
  `--surface-page`, where the rule actually sets
  `--btn-destructive-bg`. Measured both themes — the two resolve
  identically (`#ffffff` light, `#0f141b` dark) — so the old row was
  an approximation the derived pair supersedes, and nothing moves.
- **A latent wrong pair.** `_BG_RE` would match a gradient's first
  colour *stop* as if it were the fill behind text. Not triggered —
  `base.html`'s two gradient rules set no `color:` — and wrong the
  first time one does. Guarded; the count stays 73, which is what
  "latent" should look like.
- **`docs/known_limitations.md` still enumerated three sources** where
  there are four. The identical omission the first pass caught in the
  test's docstring, never propagated to the document a reader meets
  first — and sitting four lines under text this item had just
  edited. *A correction reaches the place it was found and no further
  unless someone walks it.*

Also upheld and not changed: `setdefault` means a pair reachable by
more than one source — **31 of the 73** — shows only the first, so
`tools/README.md` now says that is provenance rather than exclusivity.


**Decisions confirmed at build:**

- The decorative uses are outside the floor by rule, not judgment
  (WCAG 1.4.3 governs text) — and now by construction, since
  `--decor-muted` is a separate token and a `color:` declaration
  naming it fails a test.
- Repointing rather than editing a primitive was forced for
  `--text-dim` (`--gray` also feeds `--card-help-border`) and for
  `--text-link` (`--blue-glow` has ten dark consumers, among them the
  reserved `--selected-bg`), and *not* forced for `--text-subtle`; see
  Judgment calls.
- `spec/color_tokens.md`'s "Deliberate couplings" recorded
  `--text-link` as resolving to the reserved pair in both themes.
  That contract is now one step off in dark, and the spec says so
  rather than being quietly left wrong.
- The parser was extracted to `tests/unit/_base_css.py` rather than
  copied: `test_reserved_shade.py` had already paid for three traps in
  it, and 19K.6 added a third reader of the same stylesheet.

### PR ladder

1. **New values for the two tokens, in both themes, with the contrast
   arithmetic in the test.** A test that computes the ratio from the
   token values rather than asserting a hex, so the next value change
   is checked rather than trusted. `known_limitations.md` rewritten in
   the same PR — the entry is the reason the item exists.

### Definition of done

- Every `color:` use of `--text-dim` and `--text-subtle` meets AA for
  the size it is rendered at, in both themes, computed by a test from
  the token values.
- The 6 decorative uses are unchanged, and the reason is written down.
- `docs/known_limitations.md` names the real tokens, the real ratios,
  and what was done.
- Flagged in the PR as **UI-visible and verified on the dev slot after
  deploy, not in the container** (`CLAUDE.md`, "Where work runs").
- `.venv/bin/pytest` and `ruff check .` both pass in the agent container
  before pushing.
- `spec-writer` run **before** pushing.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19K.7` exits 0; any warning adjudicated
- `## Status` records intended vs done
- `docs/status.md` row added

### Open questions

- **The replacement values.** Author decides at rung 1, from rendered
  samples in both themes — a contrast ratio is a floor, not a design.

### Out of scope

- **A full WCAG audit.** `known_limitations.md` records that only a
  basic pre-pilot pass was done (Segment 14A PR 5); this item fixes the
  one thing that pass found and does not become the audit.
- **The decorative uses.** See Decision.

### Doc impact

- `docs/known_limitations.md` — the Accessibility entry rewritten
  against the real tokens and ratios (Item 7).
- `spec/color_tokens.md` — the two-tier token catalogue records the AA
  floor the muted text tokens are held to, and that the decorative uses
  are outside it (Item 7).
- `docs/status.md` — row when the item closes (Item 7).
- `tools/theme_variants.gen.py` — the `palette_only_variant` docstring
  named `--text-dim` as sharing `--slate-dim` in dark; it is
  `--decor-muted` that does now (Item 7).
- `tools/theme_customizer.gen.py` / `tools/theme_preview.gen.py` — the
  hand-written references the `base.html` lift does not reach: the
  customizer's element-facet map and both tools' own chrome CSS. The
  customizer's Contrast panel becomes the audit's inspection surface:
  every pair, sub-AA outlined in red (Item 7).
- `tools/_harness_common.py` — `collect_contrast_pairs`, the one
  definition of the pair set, shared by the panel and the test (Item 7).
- `tools/README.md` — the Contrast-panel paragraph rewritten: what the
  panel now lists, that the pairs are derived rather than listed, and
  that a test asserts the generated page matches the audited set (Item 7).

---

## Item 8 — the Guide documents how to build a session, not how to run one

### Opportunity

`app/web/templates/guide.html` is the operator's in-app documentation,
canonical since 19E rung 2. It is **front-loaded to the point of
imbalance**, measured 2026-09-12 at `40a0b663`:

| Section | Lines | Screencapped surfaces |
|---|---:|---:|
| Create and set up | 295 | 11 |
| Prepare and activate | 86 | 5 |
| **Watch progress** (Invitations + Responses) | **16** | **0** |
| **Download responses** (Extract data) | **18** | **0** |
| Give access | 21 | 0 |
| Tips / Sample session | 34 / 36 | 0 |
| For reviewers / observers / reviewees | 12 / 12 / 11 | 0 |

11 + 5 = the 16 surfaces behind the 32 committed files, so the two
documented sections hold every image in the Guide.

All **16** screencapped surfaces are setup surfaces. The word
"Invitations" appears **once** in the whole Guide; "Extract data" once.
**Validate has no section of its own** — it surfaces only as passing
mentions inside "Prepare and activate" and "Tips" (`guide.html:363`,
`:500`, `:509`, `:538`), so an operator learns it exists but never what
the page shows them.

So the Guide teaches how to *build* a session in detail and how to *run*
one in four paragraphs — and running it is the half an operator does
under time pressure with real people waiting. The participant sections
have the same shape: a reviewee arriving at `/me/.../results` gets nine
lines.

**Why now rather than later.** 19J and 19K rebuilt these exact pages —
the range strip became a pager cluster, the column chips were
delegated, and 19K.3 took Invitations and Responses from 40,433 and
80,432 queries to 434 each. Screencaps taken now are of the current UI.

**These are new captures, not retakes.** 19J.7's screencap-retake
commitment was **waived with a measurement**, not left unpaid: all 16
were opened on 2026-09-11 and none is stale, because none shows a
roster pager (they are card crops), every chip in them is *selected*
where the new edge is invisible, and none shows a validated lifecycle
pill. So the existing 16 are current and this item adds to them rather
than replacing any.

### Decision

**Bring the operational half up to the standard the setup half already
sets** — prose plus a screencap per surface — rather than writing a new
document. The Guide is the canonical operator documentation; a second
one would compete with it.

Covered: **Validate**, **Invitations**, **Responses**, **Extract data**.
Each gets what the setup surfaces get: what the page is for, what the
operator does on it, and one screencap in both themes.

**Rejected: a separate "operations" guide page.** 19E made
`guide.html` canonical precisely to stop operator documentation
scattering, and `known_limitations.md` plus `docs/` already hold the
non-operator half. A second page would have to be found.

**Rejected: doing the participant sections in the same item.** They have
the same shape of gap and a different audience, a different set of
routes, and a different reviewer. Named in Out of scope with where they
are recorded, not silently dropped.

**Rejected: waiting for the deployment.** Nothing here needs the host.
Segment 20 owns the *currency pass* over the Guide against deployed
reality, and its own Out of scope says work that does not need the host
"belongs in 19E / 19C, not here" — so this is new work, and 20's pass
will re-read whatever this item writes.

### Semantics

- **Screencaps are committed assets** under `app/web/static/guide/`,
  light and dark, and `tests/integration/test_guide_screencaps.py` (285
  lines) fails on a referenced-but-missing file **and** on a
  committed-but-unreferenced one. The Guide cannot drift from its
  images in either direction, which is why this is safe to grow.
- **A screencap needs a session with data in it.** 19K.3's benchmark
  harness seeds a full-matrix session through the real import and
  generate routes and drives responses through `/me/.../save` and
  `/submit` — an Invitations page with nothing on it would document
  nothing.
- **The Guide is honest about what is not wired.** The existing
  "Watch progress" text says the reminder function is not implemented;
  anything this item writes about email-dependent behaviour carries the
  same caveat rather than describing a feature the operator cannot use.
- **Section visibility is already conditional** (`visible_sections`), so
  new content inherits that mechanism rather than adding one.

### Judgment calls — decided

- **2026-09-12 — this item's own first draft was wrong in seven places,
  and the pattern is worth carrying into the build.** A pre-push checker
  recomputed every figure above and found: a section-line table with
  three wrong counts whose per-section screencap totals did not sum to
  the item's own correctly-stated 16; `tests/unit/test_participant_tokens.py`
  listed in two items as a colour-token test when it tests
  anonymous-participant *access tokens* — a pure word match; "Validate is
  never described as a page" when the Guide says "the Validate page"
  twice; a `Doc impact` naming `spec/ui_elements.md` for a token table
  that lives in `spec/color_tokens.md`; `spec/operations_pages.md`
  credited with four surfaces when it covers two, with
  `spec/validate_page.md` and `spec/extract_data.md` uncited; and a
  blast-radius row whose own command could not reproduce its number.

  **The worst of them is instructive.** The draft said 19J.7 "committed
  to a screencap-retake row and never wrote it — that debt is still
  open." It was **waived, with a measurement**: all 16 opened, none
  stale. Worse, the archive entry recording that waiver ends *"a
  blast-radius claim written from filenames rather than from the
  images"* — and this draft repeated the identical error while citing
  that document, then also claimed a file's status without opening it.
  The Opportunity sections were written from impressions and formatted
  as measurements, which is precisely what the blast-radius convention
  exists to prevent. Every figure above is now recomputed; the build
  should trust none of the prose it did not re-run.

- **2026-09-12 — Validate gets a section of its own** rather than a
  paragraph inside "Prepare and activate". It is a page an operator
  returns to, and the Guide currently never tells them it exists.

### Blast radius (measured)

Taken 2026-09-12 at `40a0b663`.

| What | Count | Command |
|---|---:|---|
| Lines in `guide.html` | 590 | `wc -l` |
| Screencap files committed | 32 (16 surfaces × 2 themes) | `ls app/web/static/guide/` |
| …of an Operations surface | **0** | the same listing |
| Lines in the screencap test | 285 | `wc -l tests/integration/test_guide_screencaps.py` |
| Spec files mentioning each surface | 23 / 18 / 24 / 11 | `grep -rlF '<surface>' spec/ \| wc -l` |
| New screencaps this item adds | 8 (4 surfaces × 2 themes) | the Decision |

### PR ladder

1. **Prose for the four surfaces, no screencaps.** The sections, the
   copy, the Validate section's placement in the nav order. Landing
   the words first means the shape is agreed before eight binary assets
   are committed to it — the scaffold-first rule in `CLAUDE.md`, applied
   to documentation.
2. **The eight screencaps**, seeded through 19K.3's harness so each page
   shows real rows, and the `{% if %}` wiring that references them.

### Definition of done

- Validate, Invitations, Responses and Extract data each have a Guide
  section saying what the page is for and what the operator does there.
- Each has a screencap in both themes, referenced from the Guide, and
  `test_guide_screencaps.py` passes in both directions.
- Nothing in the new copy describes behaviour that is not wired, or it
  carries the same caveat the reminder sentence already does.
- The existing 16 screencaps are left alone; this item only adds.
- `.venv/bin/pytest` and `ruff check .` both pass in the agent container
  before pushing.
- `spec-writer` run **before** pushing.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19K.8` exits 0; any warning adjudicated
- `## Status` records intended vs done
- `docs/status.md` row added

### Open questions

- **Whether the participant sections follow in this segment or the
  next.** They have the same gap and a different audience; the Author
  decides once rung 1 shows how much the operational copy cost.

### Out of scope

- **The participant sections** (`for_reviewers`, `for_observers`,
  `for_reviewees`), recorded in the Open question above rather than
  dropped.
- **Segment 20's currency pass**, which re-reads the Guide against the
  deployed reality and is correctly blocked on the host.
- **Screencap retakes of the 16 setup surfaces.** Measured current at
  19J.7's close and untouched here.

### Doc impact

- `app/web/templates/guide.html` — the four new sections (Item 8).
- `spec/operations_pages.md` — records that the Guide documents
  Invitations and Responses, the two surfaces this spec covers (Item 8).
- `spec/validate_page.md` — the same, for Validate (Item 8).
- `spec/extract_data.md` — the same, for Extract data (Item 8).
- `docs/status.md` — row when the item closes (Item 8).

---

## Item 9 — two-thirds of every page is the same CSS, sent again each time

### Opportunity

`base.html` carries the app's entire stylesheet as one inline `<style>`
block, and every one of the **34** templates that extend it re-sends that
block on every render. Measured 2026-09-12 at `11cad9c1` by rendering
real pages through `TestClient` and measuring the response body:

| Page | Total | Inline CSS | CSS share | gzip(whole body) |
|---|---:|---:|---:|---:|
| Assignments | 195.9 KB | 157.7 KB | **80.5%** | 49.5 KB |
| Guide | 213.9 KB | 157.7 KB | 73.7% | 54.2 KB |
| Lobby | 216.1 KB | 157.7 KB | 73.0% | 53.1 KB |
| Session home | 244.1 KB | 157.7 KB | 64.6% | 57.4 KB |

The **157.7 KB is byte-identical on all four** — it is the same block,
paid again on every navigation, and it cannot be cached separately
because it is not a separate thing. (Three of the four are operator
pages; `/guide` is "operator **and participant** documentation"
(`app/web/routes_guide.py`), so the cost is not the operator's alone.)

**`app/main.py` registers no compression middleware.** Whether the Azure
front end gzips responses on the way out is **not knowable from here**,
and that unknown is the whole reason this item is measurement-first: if
the platform already compresses, the wire cost is ~50 KB rather than
~200 KB and the case is much weaker.

**Not knowable from here, literally.** The agent container's network
policy blocks the dev slot — a request to
`app-review-robin-web-dev-…azurewebsites.net` returns
`403 CONNECT tunnel failed` (tried 2026-09-12). So rung 1 is not agent
work at all, and this item is **the only one of 19K.6–9 whose first
rung cannot start in the container**. Items 6, 7 and 8 are all "build
here, verify on the slot after deploy"; this one needs the number
*before* there is anything to build.

Context that makes it worth asking: the deployment is an **F1 free App
Service plan with no Always On** (`docs/known_limitations.md`), so this
is not a surface where bandwidth and cold-start latency are free.

### Decision

**Not yet made. Rung 1 is a measurement against the deployed slot, and
the answer decides between three responses** — the same shape 19K.3
used, which is what turned a deferral into a cheap fix there.

1. **Nothing.** If the Azure front end already gzips, ~50 KB per page
   over the wire is unremarkable, and the inline block keeps the
   single-artefact property the architecture chose it for.
2. **Compression middleware.** One line in `app/main.py`, no
   architectural change, and it compresses the **whole** response rather
   than the CSS alone — the HTML around it is 38–86 KB per page.
3. **Extract the stylesheet.** The only option that makes the CSS
   *cacheable*, so a repeat view pays a 304 rather than the bytes. It is
   mechanically cheap — one `<style>` element, 3,869 lines, zero Jinja —
   and it is the one that changes the architecture, so it needs the
   strongest evidence.

**Rejected as a framing: treating this as 19K.6's problem.** A
stylesheet does not fix a specificity tie (19K.6, Decision). These are
two questions about one file and they get separate answers, or the
architecture changes on the wrong argument.

**Rejected: doing 2 and 3 together.** Compression would mask most of
what extraction buys, so landing both at once makes it impossible to say
afterwards which one was worth it.

### Semantics

- **The measurement is taken against the deployed slot**, not the
  container, and the distinction that matters is *which* Azure. The dev
  slot is **live** (`docs/known_limitations.md`: one dev slot, a push to
  `main` deploys straight to it); what is outstanding is the
  institutional host, which blocks Segment 20 and not this. So this item
  is gated on **a request**, not on provisioning.
- **`_RevalidatingStaticFiles` sets `Cache-Control: no-cache`** (19H
  Item 4), so an extracted stylesheet would *revalidate* rather than be
  cached hard — a 304 on repeat views, not a skipped request. That is
  still far cheaper than 157.7 KB, and the item must not claim a
  stronger caching win than the existing posture actually gives.
- **A stale stylesheet after deploy is a real failure class.** Option 3
  inherits a cache-busting question the inline block does not have, and
  the existing `no-cache` posture is what answers it.
- **The architecture's own reason stands either way.** The single-artefact
  property (`CLAUDE.md`: no stylesheet, no build step) is why this is
  option 3 and not option 1.

### Judgment calls — decided

- **2026-09-12 — the item's own CSS figures were wrong, and the document
  already contained the right ones.** The first draft said 3,885 lines /
  158.4 KB / 39.5 KB. `base.html:9` carries a Jinja comment whose text
  includes the literal string `` <style> ``, so a non-greedy
  `<style[^>]*>(.*?)</style>` over the raw template matched **that** as
  the opening tag and swallowed 15 lines of comment and the no-FOUC
  `<script>` as if they were CSS. The real element is lines 24–3894:
  **3,869 lines, 157.7 KB raw, 39.2 KB gzipped**.

  The instructive part is not the regex. **The page-weight table in this
  same item already said 157.7 KB** — it is measured from a rendered
  response, where Jinja has stripped the comment before any regex runs,
  so it was never exposed to the bug. Two measurements of one quantity,
  taken by two methods, disagreeing by 0.7 KB in one document, and
  nobody compared them. Measuring twice is worth nothing if the two
  results are never put beside each other.

- **2026-09-12 — measure before choosing, even though option 2 is one
  line.** Landing compression without knowing whether the platform
  already compresses would be a change whose effect nobody could state,
  and this segment has already produced two findings about numbers that
  were asserted rather than run.

### Blast radius (measured)

Taken 2026-09-12 at `11cad9c1`.

| What | Count | Command |
|---|---:|---|
| Templates extending `base.html` | **34** | `grep -rl 'extends "base.html"' app/web/templates \| wc -l` |
| `<style>` blocks in `base.html` | **1** | parse |
| CSS lines / file lines | **3,869 / 4,732** | `<style>` spans lines 24–3894 |
| Jinja constructs inside the CSS | **0** | parse |
| Inline CSS, raw / gzipped | **157.7 KB / 39.2 KB** | `len()` + `gzip.compress` on the element's content |
| CSS share of a rendered page | **64.6–80.5%** | the table above |
| Compression middleware in `app/main.py` | **0** | `grep -n Middleware app/main.py` |
| Existing static mount | 1 (`/static`, revalidating) | `app/main.py:42` (class), `:97` (mount) |

### PR ladder

1. **Measure the deployed response — Author, not agent**, and record the
   answer here. The dev slot exists and every push to `main` deploys to
   it, so this needs no provisioning; it needs a request the container
   cannot make. **Filed as item 4 of
   `guide/post_azure_todo_checklist.md`**, whose admission rule the
   author widened on 2026-09-11 for exactly this case — a check blocked
   on *a* deploy rather than *the* institutional one, which "needs a
   file like this one or it is forgotten". One line, from any machine
   that can reach the slot:

   ```
   curl -sS -o /dev/null -D - -H 'Accept-Encoding: gzip' \
     https://app-review-robin-web-dev-a5c9f3gpfudaambf.southeastasia-01.azurewebsites.net/operator/sessions
   ```

   What to record: the `Content-Encoding` header (present or absent) and
   `Content-Length`. Browser devtools' Network tab gives the same two,
   with "transferred" against "resource" size. *Must not* change
   `app/main.py` or `base.html`.
2. **Whatever rung 1 selects**, sized once the number exists.

### Definition of done

- The wire size of a real operator page from the dev slot, with its
  `Content-Encoding`, recorded in this plan.
- A decision among the three, with its reason, recorded where a reader
  finds it — `spec/architecture.md` if the architecture holds, or the
  item that changes it if not.
- If the answer is "nothing", that is recorded as a measured decision
  rather than left implicit.
- `.venv/bin/pytest` and `ruff check .` both pass in the agent container
  before pushing.
- `spec-writer` run **before** pushing.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19K.9` exits 0; any warning adjudicated
- `## Status` records intended vs done
- `docs/status.md` row added

### Open questions

- **Which of the three.** Author decides at rung 1, from the deployed
  measurement rather than from the container's.
- **Whether this item belongs in 19K at all.** It was opened alongside
  6–8 as "unblocked work while Azure is outstanding", and that framing
  was only two-thirds right: it is unblocked by *provisioning* and gated
  on a request the agent cannot make. **Settled 2026-09-12** by
  splitting it — the measurement is checklist item 4, which is that
  file's whole job, and the decision stays here, which is this file's.
  The same split 19J.4 used: its browser verification lives in the
  checklist and its reasoning never left its plan. So 19K.9 can close
  without the segment waiting on a header.

### Out of scope

- **Splitting `base.html` into several stylesheets.** Whatever rung 1
  decides, one file in and one file out; a module boundary inside the
  CSS is a separate argument with no evidence behind it yet.
- **A build step.** `CLAUDE.md` rules out a JS/CSS toolchain, and
  nothing here needs one — extraction is a file move, not a bundle.

### Doc impact

- `spec/architecture.md` — records what a page costs to send and what was
  decided about the inline-CSS choice, so the next reader finds the
  reasoning beside the rule rather than in a closed plan (Item 9).
- `docs/known_limitations.md` — the F1-plan entry gains the page-weight
  measurement if rung 1 finds the platform does not compress (Item 9).
- `guide/post_azure_todo_checklist.md` — item 4, carrying rung 1's
  measurement so it survives outside this plan (Item 9).
- `docs/status.md` — row when the item closes (Item 9).

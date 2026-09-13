# Sweep — `spec/ui_elements.md` (2026-09-13)

**Swept:** 2026-09-13 · **Scope:** one file, `spec/ui_elements.md` (949
lines) · **Previous sweep:** `guide/sweep_2026-09-10_rrw_functional_spec.md`
(partial); last corpus sweep `guide/sweep_2026-09-05_spec-docs.md` ·
**Trigger:** not cadence — requested by the author after 19L.4's
`spec-writer` pass surfaced three stale RTD references. *"Sweep
ui_elements. RTD was a long time ago!"*

<!-- sweep-scope: partial -->

**This does not reset the corpus cadence.** One file is not the corpus;
the 8-weeks / 500-merges clock still runs from 2026-09-05.

## 0. Carried forward

Nothing to carry. `guide/archive/spec_sweep_18Aug.md` names
`ui_elements.md` only in a list of files it did not read; the 2026-09-05
corpus sweep cites it twice as a cross-reference target, never as a
subject. **This file has not been swept as a subject before.** That is
itself the finding below: four months of drift accumulated because the
file was always the thing other documents pointed *at*.

## 1. The headline — the body is in a mode the header says it left

The status block at the top declares, dated **2026-05-11**:

> Pilot-validated then migration-complete. […] This doc is now the
> implementation catalogue: it tracks per-element current state and
> canonical naming.

The body does not do that. Counted at `3e64958c`:

| block | count |
|---|---|
| `*Current:*` | 23 |
| `*Canonical:*` | 22 |
| `*Migration delta:*` | 27 |
| `*PR:*` | 25 |

That is the shape of the **plan the file was before 2026-05-11**, not of
a catalogue. And it is the mechanism behind every individual staleness
below: **a `*Current:*` block is a snapshot, and nothing renews it.**
Written on 2026-05-03, it describes 2026-05-03 for ever, while calling
itself *current*.

So the three RTD references that prompted this sweep were not three
mistakes. They were three symptoms of one: the RTD card retired on
2026-05-26, and the `*Current:*` block that named its banners had been
frozen for twenty-three days by then and has been frozen for the
hundred-and-ten since.

**The fix for the class, not the instances, is to convert the remaining
blocks from plan to description.** That is scoped in §4 and deliberately
not done here.

## 2. Update in place — done in this sweep

Ten edits, each verified against the code at `3e64958c` before the words
changed.

**2.1 §5 Banners — the `*Current:*` block describes nothing that
exists.** `.warning-banner` and `.danger-banner`: **0 occurrences** in
`app/`. The three `rtd-*` banners: **0**, gone with the RTD card
(2026-05-26). `upload-blocked`: **0**. The two ids that survive render
the canonical shape — `rf-save-error-banner` and `missing-confirm-banner`
are both `.banner.banner-error.banner-scroll-target`. Rewritten as *"Was,
at 2026-05-03"* with what shipped stated: **18 banner elements** across
the templates now use the four-variant family.

**2.2 §5 — two shipped sub-elements were never catalogued.**
`.banner-headline` and `.banner-actions` are defined in `base.html` and
used; the spec mentioned neither. `.banner-actions` is what carries the
Cancel button §5a *requires*, so the spec demanded a control and did not
name the thing that holds it. Added.

**2.3 §5 — `*Migration delta:*` marked complete.** It read *"introduce
four-variant `.banner` family; retire the standalones; sweep every
inline-styled banner-card"* — all three done.

**2.4 §9 Lifecycle badge — a dead template.** The `*Current:*` block
named `session_monitoring.html`, which does not exist. Reworded as
history and the non-existence stated.

**2.5 §9 Lifecycle badge — delta complete, and wider than projected.**
The entry anticipated three classes (`draft` / `validated` / `ready`)
with `expired` and `archived` "when those states ship". They shipped; the
set covers five. Marked complete, with the note that the entry's own
forecast held.

**2.6 §9 Status-symbol indicators — delta complete.** `.status-icon` is
defined in `base.html`. The *"small extraction"* was made.

**2.7–2.8 §9 pills table — two v2 names that were never adopted.** The
table proposed `.pill-state-ready` and `.pill-error-count`; both have
**0 occurrences**. `.pill-success` and `.pill-error` kept their v1 names.
Corrected, with the non-adoption stated rather than the rows quietly
rewritten — *a proposal that lost is part of the record.*

**2.9 §11 `<pre>` blocks** — named `session_outbox.html`, which does not
exist; the operator outbox was never brought into the v2 taxonomy, which
the 2026-09-05 sweep records as deliberate. Marked moot. `.code-block`
itself shipped, so the target exists and the subject does not.

**2.10 §11 `form style="display: contents;"`** — **0 occurrences**. It
was a hack on the RTD edit form and retired with the card. *The cleanup
this flagged was done by deletion rather than by cleanup*, which is worth
distinguishing: the item was not addressed, it was outlived.

**2.11 §11 inline JS handlers — half true, and the true half is the
bigger one.** `onsubmit="return confirm(…)"`: **0**. `onclick="…"`:
**36**, still live in `instruments_index.html`. Corrected to say so, with
the caveat that they are load-bearing — the Lock / Unlock anchors carry
`onclick="return newModelLockClick(event, <id>)"` with the `?editing`
href as the no-JS fallback, so a naive delegation sweep would have to
preserve it.

*(Eleven numbered findings, ten edits: 2.7 and 2.8 are one table.)*

## 2b. Corrected the same day — three of §2's own edits were wrong

`spec-writer` was run against the ten edits before the branch merged, and
**three of them asserted things that are not true.** They are corrected
in the spec and recorded here rather than quietly fixed, because a sweep
whose own findings go unchecked is the thing it exists to prevent.

**2b.1 — `.status-icon` is not defined in `base.html`.** §2.6 said the
delta was complete because that class exists. It does not.
`base.html` defines `.status-icon-complete` and `.status-icon-incomplete`
as **siblings**, and `review_surface.html` carries the modifier alone.
There is no base rule, so the *Canonical* line's compound selector
`.status-icon.status-icon-complete` never shipped and was aspirational
when written. *The delta is shipped; the shape it shipped in is not the
shape the entry specifies.* Corrected to say both.

**2b.2 — the `<pre>` / outbox item is shipped, not moot, and the
citation propping it up was borrowed from an unrelated finding.** §2.9
said the outbox "was never brought into the v2 taxonomy", citing the
2026-09-05 sweep. Both halves are wrong:

- The promotion to `.code-block` **happened**, in `024c48ed` on
  2026-05-03 — *before* the migration-complete date this file's header
  cites. `session_outbox.html` is gone only as a filename; 16A split it
  into `sys_admin_session_outbox.html` + `partials/_sys_admin_outbox.html`,
  both `body_class = ui-v2`, the latter still rendering
  `<pre class="code-block">`.
- The 2026-09-05 sweep entry says `session_outbox.html` "remains
  explicitly out of the operator taxonomy" — and that entry is about
  **whether the page warrants its own spec document**, in a
  *Write or deepen* carry-forward row. It says nothing about CSS. *The
  citation borrowed authority from a finding on a different subject*,
  which is how a wrong claim acquires a footnote and stops looking
  wrong.

**2b.3 — the Lock / Unlock anchor description matched neither anchor.**
§2.11 described them as one pattern: `newModelLockClick` with a
`?editing` href. In fact **Lock** has `newModelLockClick` over a *plain*
href and **Unlock** has `newModelUnlockClick` over the `?editing` one.
The sentence took the handler from one and the href from the other. The
substantive point survives — both are load-bearing and a delegation
sweep must preserve the fallback — but only Unlock has a fallback to
preserve, because only entering edit mode needs the round trip.

**And one overstatement, softened.** §2.1's "None of that survives" is
true of the named classes and ids and **not** of the pattern they were
examples of: an inline-styled `.card` doing banner duty via
`banner-scroll-target` still ships in `sys_admin_users.html` (×2),
`session_detail.html`'s owners-error card, and `next_action_card.html`.
Those are outside the four-variant family and outside this catalogue —
which makes them a finding this sweep did not have room to pursue, not
an absence.

*Three wrong out of ten, caught by a check that ran after the words were
written and before they were merged. The sweep's own §1 argues that a
`*Current:*` block rots because nothing renews it; §2b is the same
lesson one level up — **a finding rots unless something checks it**, and
the checking is not optional because the finder is confident.*

## 3. Checked and found correct — left alone

A sweep that lists only errors implies everything else was read. These
were read, suspected, and are right:

- **§6's `session_edit.html` reference** (×2). Looks like a dead
  template, and is not: it is a *dated correction note* from 2026-09-08
  explaining that the Delete buttons moved there in 2026-05-22 and came
  back when 18R Item 4 retired the page, and it says in as many words
  that the template "no longer exists". **Repointing it would have
  falsified a log.**
- **§10's `.table-pager` / `.table-pager-bottom`** — 0 occurrences, and
  correctly marked *"Retired 2026-09-11 (19J.9)"*.
- **§4's `.rs-help-card-solo`** — 0 occurrences, correctly marked
  *"retired 2026-05-05 (`62a85fee`)"*.
- **§7's `.table-dense`** — 0 occurrences, and the entry is explicitly
  speculative (*"may need … if 12/16 padding makes"*), not a claim of
  existence.

*Four of the twelve candidates a mechanical dead-identifier pass
produced were correctly-recorded history.* A sweep that fixed all twelve
would have made the file worse in four places.

## 4. Not done — scoped, not silently skipped

**The remaining `*Current:*` / `*Migration delta:*` / `*PR:*` blocks are
not converted.** This sweep verified and rewrote the entries it had
evidence for; the rest were not individually checked against the code,
and rewriting them from a plan shape into a catalogue shape is a larger
piece of work than a sweep should smuggle in.

What it would take, honestly: each block needs its `*Current:*` checked
against the templates, its `*Canonical:*` checked against `base.html`,
and its delta resolved to shipped / partial / abandoned. Roughly twenty
entries at a few minutes each — **an item, not an afternoon**, and one
that wants `spec-writer` on every entry rather than the author's memory.

Until then the header carries the warning, so a reader meets it before
the blocks.

## 5. What this sweep did not read

`spec/ui_elements.md` §1–§3 (page chrome, session chrome, headings), §7
(tables) beyond the `.table-dense` and pager entries, §8 (forms), and
§10's layout primitives beyond the entries named above. The mechanical
identifier pass covered the whole file — every backticked class, id and
template name in all 949 lines — so dead *references* anywhere are
caught. What is unread is the *prose* of those sections, where a claim
can be false without naming anything that has vanished.

*That distinction is the limit of this sweep and is stated rather than
left to be assumed.*

## 6. Reversed the same day — the sweep put history *into* a spec

The author, reading §2's edits: *"Let's keep history out of spec docs as
much as possible."*

That is a reversal of this sweep's direction, not a trim of its prose.
§1 diagnosed the problem correctly — a `*Current:*` block is a frozen
snapshot and nothing renews it — and then **§2 made six entries more
historical, not less**. It rewrote snapshots as *dated* snapshots:
*"Was, at 2026-05-03"*, *"Shipped — swept 2026-09-13"*, *"corrected the
same day"*, commit SHAs, *"the entry was complete for four months and
never marked"*. A reader wanting to know what a banner is had to read
four months of provenance first.

**The rule.** A spec says what *is*. When something landed, what it
replaced, which proposal lost, and what a previous draft got wrong are
all `guide/` and `docs/status.md` material. The spec carries at most a
pointer to them.

### 6.1 What the entries became

Six entries converted from plan-with-history to plain present-tense
description, with the `*Current:*` / `*Migration delta:*` / `*PR:*`
apparatus dropped from them entirely:

| entry | now reads as |
|---|---|
| §5 banners | the four variants, their two sub-elements, and the note that the family is not universal |
| §9 pills table (×2) | `.pill-success` / `.pill-error` keep their v1 names — stated, not narrated |
| §9 lifecycle badge | one `.pill-lifecycle-*` set over five states |
| §9 status-symbol | two sibling classes, and that there is **no** bare `.status-icon` base rule |
| §11 `<pre>` blocks | renders `.code-block`; names the two templates that carry it |
| §11 inline handlers | 36 live `onclick`s, and the Lock / Unlock asymmetry a delegation sweep must preserve |

Two deletions rather than rewrites:

- **§11 `form style="display: contents;"` is gone from the spec.** It has
  0 occurrences. An entry describing a hack that no longer exists is not
  a stale description, it is an absent subject — and the retired-thing
  record belongs here, not in the catalogue.
- **§9's status-symbol `*Current:*` line went too.** It described
  inline-styled glyphs (`#16a34a`, `font-size: 1.2em`) in
  `review_surface.html`; verified 0 occurrences — the extraction removed
  them. §2.6 had left this line standing while rewriting the delta below
  it, so the entry asserted the inline styles *and* their replacement.

The header's dated bulletin — including this sweep's own four block
counts — was replaced by a **How to read an entry** note. The counts
were the same mistake one level up: a measurement pasted into a spec,
where nothing renews it. They live in §1 here instead.

### 6.2 What was *not* stripped, and the distinction that decides it

The file carries a lot of pre-existing history: a dated correction note
in §6, three *"Corrected 2026-09-08"* annotations, retired-class
records in §4 / §7 / §10, and an `added <date>` / `restyled` column on
§10's primitives table — a changelog inside a spec. **None of it was
touched in this pass**, because the instruction arrived against six
entries and widening it unilaterally to thirty would be the same
overreach in the other direction.

But sizing it is not the only open question, because **history that
explains why something must not change is load-bearing, and history
that records when something landed is not.** §10's
`.session-row-selected` entry is the hard case: its account of 19L.1's
fill — that the fill resolved to `--status-info-bg`'s primitives and so
erased every pill on the row, and that no replacement escapes the
0.810–0.914 luminance band — reads as history and functions as a guard.
Delete it and the next author re-adds the fill. The same is true of the
§6 `.btn-icon` cascade note and §7's padding correction.

So a wider pass is not a sweep of dates. It has to separate:

- **provenance** — when a class landed, which PR, what it was called
  before: goes to `guide/` and `docs/status.md`;
- **rationale expressed historically** — *we tried X and it broke Y*:
  stays, rewritten forward as a constraint (*"the fill is absent
  because…"* rather than *"19L.1 shipped a fill and…"*);
- **absent subjects** — retired classes with 0 occurrences: deleted,
  recorded here.

Recorded as an item's worth of work, not done here. *§4 scoped the
conversion without saying which direction it ran; §6 is the answer, and
it arrived from the author rather than from the sweep.*

## 7. `spec-writer` on the reversal — two more wrong, and the header was vouching for them

The reversal was checked the same way §2 was, and found two errors. Both
sit **inside entries §6.1 had just converted**, which is the part that
matters: the new header tells a reader that converted entries are
authoritative. *An authority claim is a claim, and it was made over text
that had not been checked to that standard.*

**7.1 — "an inline-styled `.card`" was wrong on both counts.** §6.1's
"the family is not universal" paragraph described four out-of-family
banners that way. None is inline-styled, and one is not a card:

- `sys_admin_users.html` (×2) and `session_detail.html` render
  `<div class="card banner-scroll-target" role="alert">` — a **plain**
  card. No inline style, no bespoke border, **no error accent at all**;
  the generic card border, the scroll hook, and `role="alert"` to name
  the intent.
- `next_action_card.html` renders
  `<p class="next-action-signal next-action-signal--error
  banner-scroll-target">` — **not a card**, and styled by a real rule
  (`body.ui-v2 .card.next-action .next-action-signal--error`), not
  inline.

The wording was inherited verbatim from §2.1, where it entered as a
softening of an overstatement — so it was never checked, only *added* to.
That it says "inline-styled" is a leftover from the 2026-05-03 text it
was correcting: **the correction borrowed the error's vocabulary.**

**7.2 — the entry names five tokens that do not exist.** The four-variant
bullet list called them `accent-blue`, `accent-green`, `accent-amber`,
`accent-red` and `text-primary`. **All five have 0 definitions in
`base.html`**; the shipped tokens are `--status-{info,success,warning,
error}-{bg,border}` and `--text-body`. `spec/color_tokens.md`'s opening
paragraph says the flat color-named tokens are *"fully retired"* — so a
live spec was naming a vocabulary another live spec records as retired.
The same names sat in the pills table's middle column, in the two rows
this sweep rewrote.

Corrected, and the variants' actual contract stated with it: each variant
sets **only** `background` and `border-color`, everything else coming
from the `.banner` base.

**7.3 — and the count was a grep count.** *"36 `onclick`s"* is what
`grep -c` returns; **two of the hits are comments** and one is a JS
string builder. It is **33 literal attributes plus one injected at
runtime**. The figure was never wrong as arithmetic and was wrong as a
description, which is the harder kind to notice.

### 7.4 The residue

`accent-*` / `text-primary` names appear on **28 more lines** of this
file, outside the six converted entries and outside this sweep's edits.
That is a **second class of drift** — stale *identifiers*, not stale
*mode* — and it is not what §1 diagnosed. Recorded here; it belongs to
the general sweep rather than to this file's conversion.

**The lesson §6 has to carry, because it is the third time today:**
§2 was wrong in three places and §6 corrected it; §6 was wrong in two
more, both in text it had just declared authoritative. *Each pass caught
the previous pass and introduced its own.* The header no longer promises
that converted entries are right — it says what was checked.

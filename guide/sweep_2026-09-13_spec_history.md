# Sweep — history out of `spec/` (2026-09-13, Segment 19M)

**Swept:** 2026-09-13 onward, per batch · **Scope:** all **39 live
`spec/*.md`** files, 22,493 lines · **Plan:**
`guide/segment_19M_spec_history_sweep.md` · **Trigger:** not cadence —
the author's rule, after `guide/sweep_2026-09-13_ui_elements.md`
established it on one file and then had to be reversed to obey it.

<!-- sweep-scope: partial -->

**This does not reset the corpus cadence.** It reads every live `spec/`
file and **no** `docs/` file and no root document, so it is not the
whole-folder sweep the 8-weeks / 500-merges clock measures. The clock
still runs from `guide/sweep_2026-09-05_spec-docs.md`. Whether a
`spec/`-complete sweep should count is Open question 2 in the plan.

## 0. The rule being applied

> *"Express constraints as such, with brief reasoning if needed. But
> that's not strictly speaking 'history', even though the reasoning was
> confirmed through something in the history."* — the author, 2026-09-13

Three buckets, and the middle one is what makes the sweep safe rather
than destructive:

| bucket | disposition |
|---|---|
| **provenance** — when it landed, which PR, what it was called before, which proposal lost, what a previous draft got wrong | **out**, to `docs/status.md` / segment plans / this record |
| **constraint** — anything telling a future author *this must not change* | **stays**, re-expressed forward with a brief reason. *A reason established historically is not history.* |
| **absent subject** — a class, template or hack with **0** occurrences in `app/` | **deleted**, retirement recorded here |

**Uncertain passages are kept and listed.** A wrongly-kept sentence costs
a reader seconds; a wrongly-deleted constraint costs the next author a
regression.

## 0a. Correction mid-sweep — a spec is a contract, not ship-state

The author, three batches in: *"See sdd in practice doc in repo root for
distinction in function between spec and the other docs."* Then, pointedly:
*"Section 4."*

`rrw_sdd_in_practice.md` §4 splits the three folders **by question
answered**, and the authority column is the part this sweep had been
getting wrong:

| folder | answers | authority |
|---|---|---|
| `spec/` | *What is X supposed to look like and behave like?* | **The contract.** "When the code drifts from a spec, the spec is the canonical source — **fix the code** (or update the spec deliberately as part of a feature change, never silently)." |
| `docs/` | *How does X work today?* | Ship-state |
| `guide/` | *What are we building next, and how?* | The plan |

**The batches had been briefed to write "plain present-tense description
of what ships". That is `docs/`'s function.** The error is not in removing
history — that stands — but in what replaced it. A spec states an
obligation; it does not report the tree.

Three consequences, sent to all six agents mid-run:

1. **No measurements of the current tree.** *"36 `onclick` attributes"*,
   *"18 banner elements"*, *"0 occurrences in `app/`"*, *"no current users
   in app markup"* are ship-state — **and self-staling, which is this
   sweep's own diagnosis one level up.** §1 says a `*Current:*` block rots
   because nothing renews it; a count pasted into a contract rots the same
   way. State the rule, not the tally.
2. **A spec never hedges itself against the code.** *"Checked against
   `base.html`"*, *"verified"*, *"authoritative"*, a caveat naming which
   entries are reliable — none of it belongs in a contract, which does not
   report its own confidence level. **The reversal's own header note did
   exactly this** and is corrected.
3. **Where spec and code disagree, the spec wins — so do not rewrite the
   contract to match the code.** Verification is how a sweeper decides
   what to write, not something written down. A divergence is a **code
   defect or a deliberate contract change**, and §4 says a contract is
   never updated silently. This *reverses* part of the original brief: the
   absent-subject bucket still applies to an entry whose subject is
   genuinely gone with no contract behind it, but a spec **requiring**
   something the code lacks is a finding about the code.

**Consequence for the batches: fewer edits, more findings.** The
rule-shaped batches (Item 4's engine specs, Item 6's CSV contracts) should
now produce divergence reports where they would have produced rewrites,
and that is the correct outcome rather than an under-delivery.

*Item 3 completed before this reached it, so it ran under the old brief.
Its batch record below marks the two places the old framing shows, rather
than presenting them as settled.*


## 1. Why a mechanical pass was refused

The `ui_elements.md` sweep's dead-identifier pass produced twelve
candidates, of which **four were correctly-recorded history** that would
have made the file worse if "fixed". And across its two passes that sweep
made **five false claims** about the code — three in the sweep, two in the
reversal, both of the latter inside text the reversal had just declared
authoritative.

*Every one was possible because the passage being edited was a narrative
about the past rather than a description a reader could check. Prose about
what happened cannot go stale visibly; prose about what is can.* That is
the argument for the sweep and the reason it cannot be run by `grep`.

## 2. Batch records

Appended per item as each batch lands. Each records, per file: what was
removed and under which bucket, what was re-expressed forward, what was
deleted as an absent subject, what was kept as uncertain, every claim the
reading could not verify against the code, and every file read with no
finding.

*A batch that lists only changes implies the rest was read. The
no-finding list is what makes that true.*

<!-- Batch records begin here. -->

---

## Batch record — Item 3, core contracts and cross-cutting

Seven files: `rrw_functional_spec.md`, `architecture.md`, `lifecycle.md`,
`permissions.md`, `audience_and_identity_model.md`, `README.md`,
`domain_assumptions.md`. **412 inserted / 520 deleted.** Dated lines
**63 → 12**, and each of the twelve survivors is a constraint, a pointer,
or an example payload.

**This batch ran under the pre-correction brief** — it finished before
§0a below reached it — so it was asked for "present-tense description of
what ships" rather than for a contract. Its output mostly survives that,
because the files are rule-shaped and the batch treated them so; the two
places where the framing shows are noted as open decisions rather than
quietly kept.

### Provenance removed

Roughly **145 passages**: segment and PR attributions (19F, 18S, 18R,
19C, 19H, 19I, Wave 5, 18G, 18J, 15D, 13E, 11K, 16A/16B/16C), commit SHAs
(`49f1875`, `dfedd22a38da`, `36e7b1e7`), shipped-on dates, retired-on
dates, and **six "this document used to say X until 2026-09-10"
self-correction notes** in the functional spec alone — notes added by the
2026-09-10 sweep that corrected the text, then left behind as a record of
the correction inside the contract.

### Constraints re-expressed forward — the load-bearing ones

- **The audit cutover.** Now a named heading (`### Cutover boundary —
  2026-05-07`) stating the obligation rather than the event: the log is
  append-only, so anything reading `detail` across the whole table must
  branch on `audit_events.created_at`, the only cutover marker there is.
  The `EVENT_SCHEMAS` allowlist and the register-your-event_type
  obligation were **added** — `CLAUDE.md` requires them and this file did
  not state them.
- **Two lifecycle gates, stated as prohibitions.** *"The gate is
  `is_editable`, not `is_ready`"*, and for instruments *"it must not be
  `not is_ready`"* — because `is_ready` protects a surface only while the
  session is collecting, so on `expired` / `archived` the page would
  render live Delete buttons over finished data, and deleting an
  instrument runs the `Instrument` → `assignments` → `responses` cascade.
- **`_REVERT_RETURN_TO` fails silently.** Every slug a template posts must
  be in the allowlist; a missing one still 303s to Session Home, so the
  bug looks like success.
- **The results window needs `expired`, not merely the anchor reached** —
  otherwise an anchor set by any other path would open it.
- **The §19 reading guide**: *"a spec missing from it is a spec nobody is
  sent to."* Verified — all 37 other live specs are named.

### Absent subjects deleted — 4, each verified

The **RTD** glossary entry (no model, table, service or template; 13 hits,
all code comments); two retired bulk audit rows
(`instruments.bulk_accepting_responses`, `.bulk_visibility_when_closed` —
absent from `EVENT_SCHEMAS`, so no allowlist entry depended on them); and
`permissions.md`'s dated *"Drift noted at writing"* section, all three of
whose bullets were confirmed closed.

### Two self-contradictions resolved — flagged, not silent

Both were a file disagreeing with **itself**, which is why they were
fixed rather than reported:

- `lifecycle.md`'s header said **four** live states with `expired`
  reserved, directly above its own five-row table, and against
  `expire_session` at `session_lifecycle.py:459`. Now "five live states …
  none reserved".
- `audience_and_identity_model.md` said **two** live audiences three
  paragraphs above "the reviewee is a live participant audience". Now
  four, verified against the live `_results.py` / `_collation.py` routes
  and the gates in `deps.py`.

### Open decision — the functional spec's currency line

The batch **removed** `rrw_functional_spec.md`'s *"Aligned with the system
as of 2026-08-18"* and replaced it with a pointer to the sweep record,
reasoning that a hand-kept date moves only when someone remembers it.

**That has a precedent and a counter-authority, and the author should
settle it.** The precedent: 19J.1 did exactly this to `spec/README.md`, on
the stated grounds that *"a date nobody owns is what let §9.7 describe a
card that never shipped."* The counter-authority:
`rrw_sdd_in_practice.md` §6.2 presents the currency date as a **property
of the functional altitude** — it "carries a currency date and expects
ship-state may move ahead" — and notes only 4 of the live spec files
carry one, deliberately.

**Two consequences either way.** §6.2's *"4 of 36"* figure is now 3, and
`rrw_sdd_in_practice.md` line 38 **quotes the removed sentence** as
evidence. Those are the author's own measured analysis, so this sweep did
not edit them; a root document was out of scope and editing someone's
measurements as a side effect of a prose sweep would be the wrong kind of
thorough.

### Code-side findings — reported, not fixed

Under §4 the spec is canonical, so these are defects in the code or dead
matter, not stale prose:

- **`session_lifecycle.py:36-38`** — `SessionStatus`'s docstring still
  says `expired` and `archived` are *"reserved for later segments"* while
  `expire_session` (:459) and `archive_session` (:678) write both. The
  code-side twin of the `lifecycle.md` header error above.
- **`_shared.py:298`** — `"group_instrument_no_rule": 409` is a dead
  mapping. **Checked before trusting it**, because the batch wrote a spec
  claim on its strength: `open_instrument` carries a comment at :779
  recording that Wave 5 PR 5.3 retired that gate deliberately. So nothing
  raises the code, the mapping is dead, and the spec claim is true.
- **`app/schemas/rules.py:6,367`** — live docstrings describe themselves
  as mirroring `rule_set_revisions`, a dropped table.
- **`architecture.md:379`** — a stale *forward* pointer: magic-link
  anonymous access "deferred to Segment 16A", which shipped as the
  sys-admin page; `guide/deferred_consolidated.md:749` puts it under 14B.
- **`app/web/static/guide/`** holds 40 files for 20 figures, not the
  "thirty-two files for sixteen" the spec asserted. The count was removed
  rather than restated — nothing renews a count in prose — and the
  pairing rule and its failure mode kept.

### Frozen measurements — one converted, five kept

`permissions.md`'s *"128 of 128 routes carry a dependency"* became **"every
such route carries one"**, with the counting method preserved as the
invariant to check when adding a route. Verified first that no test reads
`128`.

Five test-case counts in `permissions.md` §7 were **kept and not
verified** — the same class of frozen measurement, but the batch could not
tell whether the author uses them as a coverage floor. Carried here as an
open item rather than guessed at.

### Stale identifiers — found and since fixed here

`rrw_functional_spec.md:1022` named `accent-blue` and `lifecycle.md:449`
named `accent-amber-dark` / `accent-amber-bg`, none of which is defined in
`base.html`. Both fixed after the batch closed: lifecycle now names the
shipped `--card-warning-border` / `--card-warning-bg` pair (verified, four
definitions across light and dark), and the functional spec now says
"blue-framed" with **no token identifier at all**, because §6.2 puts that
altitude at technology-neutral and shipped token names belong to the
per-page specs.

### Kept as uncertain — 5

Chief among them `domain_assumptions.md`'s `## Domain` block, whose
`Status:` lines contradict the shipped machine (`ready` described as
deadline-derived; archive described as deleting data). **Kept whole**: it
is undated and reads as the author's original domain intent, which is what
that file exists to record, and rewriting it would be authoring rather
than sweeping. Also kept: `architecture.md`'s consistency-audit ids
(`R1`–`R7`, a findability gap rather than history) and `lifecycle.md`
§8.2.3's auto-archive precondition for an unbuilt trigger.

### Open question 1 answered

The plan left *"one sweep record or six?"* to whoever landed Item 3: **one
file, as started.** Three batches in it is nowhere near the ~1,000-line
revisit threshold, and the three-bucket rule's boundary cases — a
retired-class record that still guards a live allowlist entry, a count
nobody renews — only make sense read across batches. Revisit after Item 6.

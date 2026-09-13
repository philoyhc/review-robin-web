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

# Segment 19D — Sweep follow-through

**Opened:** 2026-09-05 · **Theme:** action the first drift sweep's findings
· **Related:** `guide/sweep_2026-09-05_spec-docs.md` (the findings),
`guide/archive/segment_19A_spec_documentation.md` (Item 2, which produced
the sweep), `guide/sweep_template.md`.

> **Why a new segment rather than an item on 19A or 19C.** Both have
> closed — 19A on 2026-09-05, 19C on 2026-09-04 — and the `segment-plan`
> skill opens a new segment when the live one has closed. 19C also
> carries a **segment-level** `## Doc impact` that `close_check.py 19C`
> passes today; adding an item with its own `### Doc impact` would give
> that file two shapes and fail C1, and adding unhonoured bullets to its
> segment manifest would flip a closed, green segment red. Neither is a
> good way to treat a finished plan.

## Opportunity

The first sweep under `guide/sweep_template.md` ran on 2026-09-05 and
filed **eight update-in-place findings** across ten live `spec/` + `docs/`
files. Per that sweep's own scope rule the fixes are ordinary follow-on
work, not part of the item that produced them — so they are here.

Four of the eight are carried from `spec_sweep_18Aug.md`, where they were
filed as "minor / cosmetic (non-actionable)" and then never re-read for
eighteen days. Two more were **mis-filed** there: one had the drift on the
wrong side entirely, and one was recorded as smaller than it is. That is
the argument for actioning them now rather than filing them again: a
finding that survives two sweeps unactioned is not minor, it is
unattended.

None of these is catchable by a constant. `tests/unit/test_doc_conventions.py`
and `tests/unit/test_spec_coverage.py` both pass on every file below.

## Decision

Fix all eight, grouped into three PRs **by the kind of judgement each
needs** rather than by file: mechanical reference corrections, then spec
content that understates or contradicts the code, then the one finding
that needs a decision from the author before any edit is right.

**Rejected, with reasons.** *Fixing them one file per PR* — ten PRs for
ten small edits, with no reviewer benefit; the grouping above lets a
reviewer check a whole class at once. *Folding them into the sweep's own
PR* — the sweep recommends and a person decides; collapsing the two would
make the sweep an agent that edits, which `constitution.md` Article IV
rules out. *Leaving them as sweep-document findings only* — that is
exactly the failure mode the carry-forward section exists to catch, and it
would be perverse to reproduce it in the first cycle after building the
mechanism.

## Semantics

- **A "stale module path" is prose, not a link.** The five references to
  `app/services/assignments.py` and friends still resolve through the
  package `__init__`, so nothing is broken today. The fix is to name the
  package, not to restructure anything.
- **Finding 2.1 changes code, not a spec.** The docstring in
  `app/web/routes_operator/_preview_surface.py` misattributes its segment;
  the spec it was blamed against is correct. No behaviour changes and no
  test moves, so it rides with the reference fixes.
- **Finding 2.4 is not a rename.** `spec/visual_style_general.md` is the
  *portable* design system, so its token names may be illustrative by
  intent. Either outcome — repoint the 17 `accent-*` names to the
  post-19C vocabulary, or state in the doc that `spec/color_tokens.md` is
  authoritative and these names are examples — is a legitimate close;
  picking silently is not.
- **Nothing here is a contract change.** Every edit makes a document match
  code that already shipped. If any fix turns out to require a code change
  instead, that is a finding for `## Status`, not a quiet widening.

## Judgment calls — decided

- **2026-09-05 — grouped by judgement kind, not by file or by folder.**
  A reviewer checking "are these references dead?" is doing one job;
  checking "does this paragraph match the code?" is another. Mixing them
  in one PR makes both harder.
- **2026-09-05 — finding 2.4 is its own rung and lands last.** It is the
  only one that cannot be verified against the repository alone, so it
  should not block the seven that can.
- **2026-09-05 — a path merely *mentioned* in a `Doc impact` bullet is
  not backticked.** `close_check.py` treats every backticked `spec/` or
  `docs/` path under the heading as a commitment, so naming the retired
  authentication doc or a neighbouring spec in passing would commit this
  segment to editing it — C2 failed on exactly that in this plan's first
  draft. Backticks in a manifest bullet mean "I will change this file".
- **2026-09-05 — `spec/blob_storage.md` is deliberately not a finding.**
  It references `app/services/blob_store.py`, a module never written, but
  the doc is a labelled stub for deferred infrastructure. Recorded in the
  sweep's *Retire* section so the next sweep does not re-propose it.

## Blast radius (measured)

| What | Count | Command |
|---|---|---|
| Findings to action | 8 | `guide/sweep_2026-09-05_spec-docs.md` §2 |
| Live `spec/` + `docs/` files touched | 10 | the eight findings' targets, deduplicated |
| Code files touched | 1 (`_preview_surface.py`, docstring only) | finding 2.1 |
| Stale `app/services/*.py` path references | 5 across 5 files | `grep -rln '\`app/services/<mod>.py\`' spec/ docs/ --exclude-dir=archive` |
| `accent-*` names in `visual_style_general.md` | 17 | `grep -oE "accent-[a-z-]+" spec/visual_style_general.md \| sort -u \| wc -l` |
| Carried from the 2026-08-18 sweep | 6 of 8 | the sweep's §0 table |
| Derived doc gates that pass on all ten files today | 6 checks | `grep -c "^def test_" tests/unit/test_doc_conventions.py tests/unit/test_spec_coverage.py` |

## PR ladder

1. **PR 1 — dead and wrong references.** Findings 2.1, 2.3, 2.7, 2.8:
   the `_preview_surface.py` segment misattribution; five stale
   `app/services/*.py` paths now naming packages; `docs/security_posture.md`
   pointing at the `docs/authentication.md` it absorbed; and
   `spec/visual_style_rrw.md`'s two references to specs consolidated away
   in 2026-05. All verifiable against the repository; no judgement.
   Must not touch spec *content*.
2. **PR 2 — spec content that understates or contradicts the code.**
   Findings 2.2, 2.5, 2.6: the `lifecycle.md` §1 diagram showing three of
   five states; `operator_ui_concept.md`'s user card omitting the
   `(super admin)` / `(sys admin)` suffix `base.html` renders; and
   `domain_assumptions.md`'s "1-6 Instruments" implying a cap that does
   not exist. Must not touch `visual_style_general.md`.
3. **PR 3 — `spec/visual_style_general.md` (finding 2.4).** Lands whichever
   of the two outcomes in *Semantics* the author picks, and records the
   choice in `## Status`. Docs only.

## Definition of done

- All eight findings in `guide/sweep_2026-09-05_spec-docs.md` §2 are
  closed in its own §0-style ledger — actioned, or declined with a reason
  recorded there so the next sweep carries the decision, not the finding.
- No `app/services/*.py` path in live `spec/` or `docs/` names a module
  that is now a package.
- `spec/lifecycle.md` §1 shows all five states.
- The `visual_style_general.md` decision is recorded in `## Status`, not
  only in the diff.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19D` exits 0
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` records intended vs done
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

## Open questions

- Finding 2.4: repoint the names, or declare them illustrative and point
  at `spec/color_tokens.md`? **Decided by the author**, before PR 3.
- Should the sweep document gain its own findings ledger (an §0 that later
  sweeps read), or should closure be tracked only here? Leaning on the
  sweep document, since that is where the next sweep will look — but it
  makes the sweep a living file rather than a dated snapshot. Decide at
  PR 1.

## Out of scope

- Re-sweeping the 51 files the 2026-09-05 sweep did not read — that is the
  next sweep's job, on its own trigger.
- The orphan-spec test and a `CROSS_CUTTING` allowlist — still Segment
  19A Item 3's deferred open question, needing several sweeps' evidence.
- Any code change beyond the one docstring in finding 2.1.
- `spec/blob_storage.md` — deliberately kept (judgment call above).

## Doc impact

- `spec/assignments.md` — name the `app/services/assignments/` package,
  not the retired module path (PR 1).
- `spec/setup_pages.md` — same package rename (PR 1).
- `spec/quick_setup_card_spec.md` — `app/services/session_config_io/`
  package rename (PR 1).
- `spec/settings_inventory.md` — `app/services/scheduled_events/` package
  rename (PR 1).
- `docs/security_posture.md` — drop the reference to the retired
  authentication doc, whose content this file absorbed (PR 1).
- `spec/visual_style_rrw.md` — repoint the two references to specs
  consolidated into the instruments spec in 2026-05 (PR 1).
- `spec/lifecycle.md` — §1 state diagram to show all five states, and the
  package rename (PR 1 + PR 2).
- `spec/operator_ui_concept.md` — document the `(super admin)` /
  `(sys admin)` suffix on the user card (PR 2).
- `spec/domain_assumptions.md` — drop or qualify the "1-6 Instruments"
  range; there is no cap in code (PR 2).
- `spec/visual_style_general.md` — the finding 2.4 decision (PR 3).
- `docs/status.md` — row when the segment lands.

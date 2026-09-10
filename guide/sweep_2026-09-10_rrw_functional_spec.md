# Sweep — `spec/rrw_functional_spec.md` (2026-09-10)

**Swept:** 2026-09-10 · **Scope:** one file —
`spec/rrw_functional_spec.md`, all 108 headings · **Previous
sweep:** `guide/sweep_2026-09-05_spec-docs.md` (folder-scoped;
this file was not among its findings) · **Trigger:** Segment
19J Item 1, from `guide/codebase_assessment_10sep.md` §8
recommended move #1.

**A single-file sweep, deliberately.** The folder-scoped cadence
(19A Item 2, 8 weeks or 500 merges) covers `spec/` and `docs/` as
a corpus. This one reads one document end to end because the
question is not "is this file stale" but "**which parts of it has
anybody ever checked**" — see *Why this sweep exists* below.

**No spec was edited in this pass.** Rung 1 produces the record;
rung 2 applies the dispositions. Separating finding from fixing is
19G.7's lesson: that item's predecessor certified a corpus clean
and the certification was itself wrong, which only surfaced
because the measurement and the fix were separate artefacts.

---

## Why this sweep exists

The 10sep assessment called this file "the least-audited live
spec … 23 days stale", citing `spec/README.md`'s "Aligned with
the system as of 2026-08-18". **Both halves of that are wrong,
and the truth is worse.** Measured at the top of Item 1:

```
$ git log --oneline --since=2026-08-18 -- spec/rrw_functional_spec.md | wc -l
9
$ git diff <first-since>^ HEAD -- spec/rrw_functional_spec.md
725 insertions(+), 381 deletions(-)
```

Nine edits, 1,106 changed lines, in the three weeks the index line
claims alignment *from*. The file is not neglected. Every one of
those nine edits was made by a segment revising **the sections its
own work touched** — 19C's label carrier, 19F's specs pass,
19I.2, 19I.4, 19I.10, 19I.12 — and none read the document
through.

**The clearest single piece of evidence is inside the document.**
19F changed the reviewee results gate to require a currently
resolving visibility grant. §10.9 says so, correctly, naming
`require_reviewee_with_current_grant` and the segment. §4.4 —
describing the same gate, 700 lines earlier — still describes the
pre-19F roster-and-email check. §17 gate 5 does too. One fact,
three places, and the one that is right is the one 19F PR 6
happened to open.

That is the defect this sweep is for: **piecemeal currency reads
as whole-document currency**, over an index line that no edit ever
moves.

---

## 0. Carried forward

`guide/sweep_2026-09-05_spec-docs.md` left no finding against this
file, and its own carried-forward section was empty at close. One
finding arrives from outside the sweep cadence:

| Finding | From | Age | Now | Note |
|---|---|---|---|---|
| §9.7 names an Assignments "Self-reviews card" that does not exist | 19I.12 close (`spec-writer`), 2026-09-10 | 0 d | **open — F7 below** | Reported and deliberately left at 19I.12; the only ⚠ row in the 10sep compliance table. This sweep confirms it and finds it is not what it looked like. |

---

## 1. Write or deepen

**None.** Every section has a subject and says something about it.
This document's failure mode is not thinness.

---

## 2. Update in place

Fifteen findings across fourteen sections. Every one carries
`path:line` evidence checked in this session.

### F1 · §4.4 — the reviewee results gate is described pre-19F

**Says:** "Access is gated on the reviewee's `email_or_identifier`
parsing as a real email that matches the signed-in user
(case-insensitive)."

**Code:** that is `require_reviewee_in_session`
(`app/web/deps.py:382`). The results surface's actual gate is
`require_reviewee_with_current_grant` (`deps.py:436`), which
composes the roster check **with a currently-resolving visibility
grant** — `app/web/routes_reviewer/_results.py:37,56,92`. Without
a grant the route answers 404.

**Wins:** the code. §10.9 already describes it correctly.

### F2 · §5.3 — contradicts §4.4 on whether reviewees are users

**Says:** "Reviewees **do not sign in to RRW**; they are the
*subjects* of evaluation, **not participants**."

**Contradicted by §4.4** in the same document: "an
email-identified reviewee is now a **live authenticated
audience** (shipped 2026-05-30 → 06-03)", signs in, reaches `/me`
and `/results`. §5.3 is the pre-participant-model paragraph,
untouched for over three months of shipped work.

**Wins:** §4.4 and the code.

### F3 · §5.8 — "seven sources", and "the other five are opt-in"

**Says:** "Display fields draw from **seven sources**" … "The
reviewee's name and email are always present (cannot be turned
off); the other **five** sources are opt-in."

**Code:** `_VALID_DISPLAY_SOURCES`
(`app/services/instruments/_display_fields.py:84`, over
`_DEFAULT_DISPLAY_LABELS:42`) holds **nine**: reviewee name,
email, tag 1/2/3, profile link, pair-context 1/2/3. Two are locked
(`_LOCKED_DISPLAY_SOURCES:74`), so **seven** are opt-in. Both
numbers are wrong, each by two — the arithmetic collapses the two
tag triples somewhere it should not.

**Wins:** the code. Note §8.5 already gets the parallel tag count
right ("nine in-scope tag slots"), so the document holds both the
right and the wrong arithmetic.

### F4 · §5.9 — self-review is defined by the individual rule only

**Says:** "self-review flag (computed: true when reviewer.email
matches reviewee.email, case-insensitive)".

**Code:** `classify_self_review`
(`app/services/assignments/_self_review.py:85–107`) branches on
`instrument.group_kind`. That is the individual-scoped half. For a
**group-scoped** instrument the whole-group rule applies: true iff
the reviewer is a member of the group being reviewed, and when it
fires **every assignment in the group is flagged**, not just the
`(R, R)` cell.

**Wins:** the code. `spec/assignments.md` § *Self-review policy*
is the authority and already carries both halves.

### F5 · §6.2 — the lock card, on the wrong states and the wrong pages

**Says:** "In `ready`, every setup page renders with a prominent
yellow 'lock' card explaining that the session is open for
responses and offering a one-click Pause action."

**Code, two errors:**

1. **States.** Since 19H.6 the card renders in every non-editable
   state — `ready`, `expired`, `archived` — from one partial,
   `app/web/templates/operator/partials/_roster_lock_card.html`,
   gated on `{% if not is_editable %}`, branching per state
   (`archived` carries no control at all because `/revert` answers
   409 from there).
2. **Pages.** Not "every setup page": the Email Template page
   renders none by design (`spec/email_template_editor.md` §5),
   and Assignments / Invitations / Responses retired theirs with
   the Workflow-card rollout.

**Wins:** the code. `spec/lifecycle.md` §5 is the authority and is
current as of 19H.6/19H.7.

### F6 · §9.5 — the friendly-label editor does not edit identity slots

**Says:** "**Friendly-label editor card** — inline editors for the
display labels of this entity's tag **and identity** slots."

**Code:** `_VALID_SOURCE_FIELDS`
(`app/services/field_labels.py:80`) holds the nine tag slots only.
The reviewee identity/photo overrides were retired 2026-05-31
(comment at `:73`); `upsert` refuses them.

**Contradicted by §8.5** in the same document, which records the
retirement explicitly.

**Wins:** the code and §8.5.

### F7 · §9.7 — the "Self-reviews card", and what is actually true

**Says:** "**Self-reviews card** — session-wide
self-reviews-active toggle."

**Code — and this is not the simple deletion the 10sep assessment
implied.** Three separate facts:

1. **No such card exists.** No template renders
   `self_reviews_active` (grep over `app/web/templates/`: zero
   hits).
2. **The session-wide flag is real.**
   `review_session.self_reviews_active`
   (`app/db/models/review_session.py:35`) exists, is serialised to
   the Settings CSV
   (`session_config_io/_serialize.py:146`), applied on import
   (`_apply_session.py:39`), and copied by clone
   (`session_clone.py:108`).
3. **It has no *setter* in the UI**, but it is not inert. The
   session-wide setter retired — `set_instrument_self_reviews_active`'s
   own docstring calls itself the "mirror of the retired
   session-wide `set_self_reviews_active`". The flag is written
   only by the Settings CSV apply path and clone.

**Corrected 2026-09-10, at rung 2.** Point 3 first read "**its
only operator surface is the Settings CSV round-trip**", which
implied the column does nothing. It does: `_generate.py:346`
reads it — `review_session.self_reviews_active if is_self else
True` — so the flag **seeds the `include` value of every
self-review pair at generation time**. The operator then flips
those assignments per instrument from the Assignments status
card's Self review column (`session_assignments.html:85–90`,
audited `assignments.instrument_self_reviews_active_set`). Two
layers, both live: a generation default and a per-instrument
override. §8.6's existing wording — "When true, self-review pairs
participate … Per-pair include overrides apply post-flip" — turns
out to describe exactly that and needs no change.

**Author's decision (2026-09-10):** "Self review assignments are
flipped active/inactive through Assignments page." So §9.7's card
bullet is deleted and §9.7 / §10.3 name the Assignments page as
the surface. Not a gap; the sweep's first reading of it was.

So the spec names a card that never shipped for a flag that is
genuinely settable — just not by clicking anything. §8.6's "The
flag is editable only in `draft` / `validated`" is true and
silent on *where*, which is the part a reader needs. §10.3 repeats
the phantom: "the operator controls session-wide self-review
behaviour via the self-reviews-active toggle".

**Disposition, applied at rung 2:** §9.7's card bullet deleted;
§9.7 and §10.3 now name the Assignments page as where self-review
assignments are flipped, and §5.9 records that the session flag
seeds `include` at generation. §8.6 unchanged — it was right.

### F8 · §9.7 — the Assignments operator-actions card, as of 19I.9

**Says:** "search box + Search-by dropdown (All / Reviewer /
Reviewee) + bulk Inactivate / Activate / Show-pair-row controls."

**Code:** the Search-by dropdown is accurate and still live
(`session_assignments.html:192–200`, `_SEARCH_BY_VALUES` at
`_assignments.py:114`) — **checked deliberately**, because it sits
in the same bullet list as F7 and one wrong sentence is not
evidence about its neighbours. What the bullet omits is what 19I.9
added: the **status filter** (`:184`) and the **search typeahead**
(`:214`).

**Wins:** the code. Additive fix.

### F9 · §7.2 and §10.2 — the account-mismatch banner is on the other path

**Says (§7.2, under "Direct session link"):** "Mismatch produces a
friendly account-mismatch banner pointing the user at their
account-debug page." **§10.2** repeats it for the reviewer surface
generally.

**Code:** the direct-link gate `require_reviewer_in_session`
answers a **bare 404** (`app/web/deps.py:377`) — 19F PR 1's
session-id enumeration fix. The banner is real but belongs to the
**invitation redemption** path only:
`app/web/routes_reviewer/_invite.py:51` renders
`reviewer/invite_mismatch.html` with `status_code=403`.

§17's "403 on mismatch" for the token landing is therefore
**correct**; §7.2 has attached the banner to the one bullet where
it does not happen.

**Wins:** the code. Both sections need the split named.

### F10 · §12.3 — the Responses extract's column name and order

**Says:** 21 columns, listed as "… `RevieweeEmail_or_Identifier`
… `Value, SavedAt, SubmittedAt, Version, SelfReview,
InstrumentFlavour`".

**Code:** `HEADER`
(`app/services/extracts/responses_extract.py:61`) is 21 columns —
**the count is right** — but the tenth is named **`RevieweeEmail`**
(the comment at `:68` says it deliberately mirrors the roster CSV
header even though the model column is `email_or_identifier`), and
the tail order is `Value, **SelfReview**, SavedAt, SubmittedAt,
Version, InstrumentFlavour`.

**Why it matters more than a typo:** §12.7 promises byte-stable
round trip and this list is the column contract a downstream
consumer builds against. A wrong name and a wrong position are
exactly the two things that break such a consumer.

**Wins:** the code.

### F11 · §17 gate 5 — the same omission as F1

**Says:** gate 5 "**Reviewee in session** — the reviewee results
surface; a reviewee whose identifier is not an email can never
reach it", under a preamble reading "Three gates apply to
participant surfaces, all by case-insensitive email match against
an **active** roster row."

**Code:** true of gates 4 and 6; gate 5 additionally requires the
resolving visibility grant (F1). Third instance of one fact.

### F12 · §18 glossary — "seven D6 sources", twice, plus self-review

**Says:** "**D6 source** — One of the **seven** possible
display-field sources (reviewee name, reviewee email, photo link,
three reviewee tags, three pair-context tags)." And "**Display
field** — … one of seven D6 sources."

**The parenthetical enumerates nine** — 1 + 1 + 1 + 3 + 3 — so the
entry disproves its own number in its own brackets. Same defect as
F3, in two more places.

Also: "**Self-review** — An assignment where the reviewer and the
reviewee are the same person (matched by email,
case-insensitive)" repeats F4's individual-only definition.

Minor, recorded rather than fixed at rung 2's discretion: **"D6"
is never expanded** anywhere in the document.

### F13 · §19 — a reading-guide row that the target file refutes

**Says:** "UI vocabulary (button styles, layout) |
`spec/domain_assumptions.md`".

**That file's own opening paragraph**
(`spec/domain_assumptions.md:1–10`): "The original UI-vocabulary
content (button styles, banners, typography, layout primitives)
was officially **superseded 2026-05-03** by
`spec/visual_style_general.md` + `spec/visual_style_rrw.md` +
`spec/ui_elements.md`".

So the reading guide sends its named audience — a new reader — to
a file whose first act is to say "not here". **Wrong for four
months**, and invisible to the dead-path check because the file
exists.

### F14 · §19 — eleven live specs the reading guide never names

The table's stated job is "the per-page / per-subsystem specs that
this document references", and by that literal wording it is
consistent. As **a map of the corpus for a new reader**, which is
what §19 is for, it omits:

`spec/ui_elements.md` (the canonical `.btn` roles, per
`CLAUDE.md`), `spec/visibility_policy.md` (the subject of §5.16),
`spec/participant_model.md` (§4.4, §10.9, §10.10),
`spec/validate_page.md` (§9.8), `spec/role_navigator.md` (§10.1),
`spec/extract_data.md` (§9.12), `spec/rehydrate.md`,
`spec/roundtrip_coverage.md` (§12.7),
`spec/role_landing_and_visibility.md`, `spec/color_tokens.md`,
`spec/blob_storage.md`.

Seven of those eleven are the governing spec for a section this
document already has.

### F15 · §11.6 — two names for one segment, and the split is corpus-wide

**Says:** "lighting it up is the scope of **Segment 14-1 Part A**".
The plan file is `guide/segment_14B_email_infrastructure.md`, and
**14B** is the name in `guide/todo_master.md`, `docs/status.md` and
the 10sep assessment's §3 blocked row.

**This finding was written wrong and is corrected here rather than
silently rewritten**, because the error is the exact one the sweep
exists to catch. The first draft said "*Segment 14-1* appears once
in the entire repository: here" — asserted, not measured. Measured:

```
$ grep -rn "14-1" --include="*.md" --include="*.py" . | grep -v __pycache__
app/db/models/email_outbox.py          5 occurrences
tests/integration/test_email_outbox_schema.py    2
alembic/versions/c4f6a8b0d2e5_…outbox_audit_log_scaffolding.py   2
spec/rrw_functional_spec.md            1
```

**Ten occurrences, four files.** "14-1" is not a typo in this
spec — it is the name the *code, tests and a shipped migration*
use for the same work the *plans* call 14B, and this spec is the
one place where the two vocabularies meet.

**Disposition, resolved at rung 2 — and the equivalence already
existed.** The author's read was right and checkable: segment
numbering moved from a `-1` / `-2` suffix to letters (the archive
still holds `segment_12A-1`, `-2`, `-3`), and
`guide/segment_14B_email_infrastructure.md` **line 4 already says
"Renamed from `segment_14-1_email_infra.md`"**.

So no corpus-wide rename is needed and none was done. §11.6 now
says **14B**, cites that plan file, and states in one sentence why
`email_outbox.py`, its test and the `c4f6a8b0d2e5` migration still
say 14-1 in their comments. A reader who follows the pointer lands
on the document that reconciles both names — which is what the
concern above was asking for, already built.

---

## 3. Consolidate

**None.** The overlap between this document and the per-subsystem
specs is by design — it describes the product, they describe
surfaces. What is missing is the precedence rule saying so, which
rung 3 adds to `spec/README.md`.

## 4. Retire

**None.** Retiring this file was considered and rejected in the
item's Decision: it is the only document that describes the
product rather than a surface.

## 5. Move

**None.**

## 6. Read, no action

**Ninety-four of 108 headings** were read and found current.
Named individually rather than by exclusion, because the whole
point of this sweep is that "not mentioned" has meant "not
checked" in this file for three weeks:

- **§1** Purpose and framing · **§2** Functional goals (all 15) ·
  **§3** Non-goals — framing prose, no code-checkable claim beyond
  goal 10's file inventory, which §12 carries and which checks out.
- **§4.1** Sys admin three-tier · **§4.2** Operator · **§4.3**
  Reviewer · **§4.5** Observer · **§4.6** Downstream consumer.
- **§5.1** Session · **§5.2** Reviewer · **§5.4** Relationship ·
  **§5.5** Instrument · **§5.6** Observer · **§5.7** Response
  Field · **§5.10** Response · **§5.11** Rule and RuleSet ·
  **§5.12** Invitation · **§5.13** Audit event · **§5.14**
  Workspace · **§5.15** Email Outbox · **§5.16** Visibility policy
  (the 3 × 2 grid and the `Anonymized` / `Summarized` labels match
  `app/services/visibility_policies.py`) · **§5.17** Feature
  toggles (lock-on-data verified at `app/services/sessions.py:195–210`
  and `_has_relationships:395`).
- **§6** lifecycle table (display labels match
  `lifecycle_display.py`) · **§6.1** Transitions · **§6.3** Lazy
  deadline closure.
- **§7.1** Operator identity · **§7.3** Workspace allowlist ·
  **§7.4** Session ownership.
- **§8.1**–**§8.8** — all eight. §8.5's "nine in-scope tag slots"
  is right where §5.8's arithmetic is wrong.
- **§9.1** Lobby · **§9.2** Create session · **§9.3** Session Home
  · **§9.4** Config card · **§9.6** Instruments · **§9.8**
  Validation and activation · **§9.9** Invitations · **§9.10**
  Responses · **§9.11** Previews · **§9.12** Extract data ·
  **§9.13** Operator settings · **§9.14** Sys admin.
- **§10.1** Access · **§10.3** Review surface (except the
  self-review sentence, F7) · **§10.4** Group-scoped surface ·
  **§10.5** Saving · **§10.6** Submission · **§10.7** Clear all ·
  **§10.8** Personal extract — **the 21-column claim was checked
  column by column** against `responses_extract.py:61` and is
  right · **§10.9** Reviewee results (correct where §4.4 is wrong)
  · **§10.10** Observer collation.
- **§11** intro · **§11.1**–**§11.5** · **§11.6** except F15.
- **§12** intro · **§12.1** Envelope · **§12.2** Per-entity files ·
  **§12.4**–**§12.8**.
- **§13**–**§13.4** Validation, all four boundaries · **§14**
  Reconciling regeneration · **§15** Audit and logging ·
  **§16**–**§16.7** Retention, all seven · **§17** except gate 5
  (F11) — the "403 on mismatch" claim was checked and is right.
- **Title**, **Table of contents**, **§18** except F12, **§19**
  except F13/F14.

**Mechanical pass:** the dead-cross-reference check from
`guide/sweep_template.md` returns **0** dead paths in this file.
F13 is the case that check cannot see — a live path pointed at for
content it no longer holds.

## 7. Not read

**Nothing.** All 108 headings were opened. The sweep is complete
over its scope; its scope is one file.

---

## Headline numbers

| | |
|---|---|
| In scope | 1 file, **108** headings (1 title + 20 `##` + 87 `###`), 2,235 lines |
| Read | 108 headings (100%) |
| Findings | 15 (write 0 / update 15 / consolidate 0 / retire 0 / move 0), across 14 sections |
| Carried in / closed / still open | 1 / 0 / 1 |
| Sections current | 94 of 108 (87%) |

---

## Three things this sweep found that are not spec findings

Recorded here because a reader of this document will want them,
and because the class — a comment that describes a world that has
moved — is the same one the findings above are about. **None was
fixed in this pass**; they are code, and this item's scope is one
spec file.

1. **`app/web/deps.py:398`** — `require_reviewee_in_session`'s
   docstring says "Phase 1 stub — defined but not referenced by
   any route yet." It is referenced at `deps.py:438`, by the gate
   that 19F built on top of it.
2. **`app/services/field_labels.py:89`** —
   `FieldLabelSourceError` says "not one of the **12** in-scope
   slots"; `_VALID_SOURCE_FIELDS` holds **9**. The identical
   9-vs-12 drift was fixed *in the specs* on 2026-08-20 ("docs:
   fix the 9-vs-12 friendly-label slot drift"); the code comment
   was not swept with them.
3. **`app/services/sessions.py:190`** — "The Edit Session UI
   renders the checkbox `disabled` in this state". That page
   retired in 18R Item 4; the affordance now lives on the Session
   details config card.

Each is a candidate for a 19J item if the author wants the class
chased in `app/` the way it has now been chased in one spec.

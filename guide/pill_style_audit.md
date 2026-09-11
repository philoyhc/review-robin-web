# Pill-style audit — where the rounded pill is a label and where it is a control

**Written 2026-09-11 (Segment 19J.7, step 1).** The operator UI uses the
same rounded-pill vocabulary for two unrelated jobs: **stating a fact**
("3 reviewers", "Draft", "At risk") and **offering a click** (the
column-visibility chips, the lobby's tag filters). This document
measures how far that goes before anyone proposes a fix, because the
question "how should they differ?" is unanswerable without knowing how
many there are and which ones already disagree.

It is an audit, not a plan. The decision lives in
`guide/segment_19J_assessment_moves.md` Item 7.

## How this was measured

A scan over every `.html` under `app/web/templates/` (excluding
`base.html`, which defines rather than uses), collecting each element
whose `class` carries a token matching `pill` or `chip`, and
classifying it:

- **interactive** — the element is an `<a>`, `<button>`, `<input>` or
  `<label>`, **or** it carries `role="button"`, `tabindex`,
  `aria-pressed`, `onclick`, or one of the `data-*` hooks the inline
  scripts bind to (`data-col-toggle`, `data-shaper*`, `data-severity`,
  `data-new-model-band2-pill`);
- **display** — everything else.

The classifier was checked against the markup rather than trusted: its
"interactive" `.pill` hits are 50 `<span>`, 6 `<p>` and 5 `<a>`, and
the spans are the `role="button" tabindex="0" aria-pressed` chips, so
the span-heavy result is real and not a parsing artefact.

## What is out there

**250 pill/chip elements across 28 templates**, in **32 distinct class
combinations**.

| | count |
|---|---:|
| display-only | **189** |
| interactive | **61** |

The base class does both jobs:

| class | interactive | display | templates |
|---|---:|---:|---:|
| `pill` | 53 | 176 | 28 |
| `pill-count` | 46 | 52 | 18 |
| `pill-empty` | 2 | 55 | 16 |
| `tag-chip` | 46 | 1 | 10 |
| `pill-info` | 0 | 22 | 12 |
| `pill-warning` | 0 | 14 | 5 |
| `pill-success` | 0 | 9 | 5 |
| `pill-error` | 0 | 5 | 3 |

Where they cluster:

| template | total | interactive | display |
|---|---:|---:|---:|
| `operator/session_extract_data.html` | 38 | 32 | 6 |
| `operator/instruments_index.html` | 23 | 6 | 17 |
| `operator/partials/session_setup_status_row.html` | 20 | 0 | 20 |
| `operator/session_invitations.html` | 19 | 2 | 17 |
| `reviewer/dashboard.html` | 16 | 3 | 13 |
| `operator/partials/next_action_card.html` | 14 | 0 | 14 |
| `operator/sessions_list.html` | 14 | 3 | 11 |
| `operator/session_responses.html` | 13 | 2 | 11 |

## The finding

**Only one thing distinguishes a clickable pill from a label today, and
it is `cursor: pointer`.**

```
body.ui-v2 .tag-chip { cursor: pointer; }
```

A cursor is invisible until the pointer is already over the element,
absent entirely on touch, and absent from any screenshot — including
the Guide's. Nothing in the resting state of a pill says whether
clicking it will do something.

**Six class combinations are used both ways**, and one of them is not
a rounding error:

| combination | interactive | display |
|---|---:|---:|
| `pill pill-count tag-chip` | **44** | **1** |
| `col-chip-row` | 6 | 6 |
| `chip.role pill pill-role-` | 1 | 2 |
| `pill pill-role-reviewer` | 1 | 1 |
| `pill pill-role-reviewee` | 1 | 1 |
| `pill pill-role-observer` | 1 | 1 |

### The clearest case, in two lines of markup

The column-visibility toggle, on `session_assignments.html:298`:

```jinja
<span class="pill pill-count tag-chip is-selected"
      data-col-toggle="{{ slot }}"
      role="button" tabindex="0" aria-pressed="true">
```

And `b3_static_pill`, on `instruments_index.html:3896`:

```jinja
<span class="pill pill-count tag-chip is-selected"
      title="Fixed">
```

**The class strings are identical.** One toggles a column; the other
states that a Band 3 value is fixed. The difference is carried entirely
by attributes the eye cannot see — and because the static one carries
`tag-chip`, it also inherits `cursor: pointer`, so the single existing
affordance is pointing the wrong way on it.

> **Fixed 2026-09-11 (19J.7 rung 1).** `b3_static_pill` now renders
> `pill pill-count` and nothing else. Two corrections to the table
> above, both caused by this document's own method: the macro's **1**
> display use is really **5** — the scan reads `class="..."` strings,
> so it counted the macro definition and could not see the five
> `{{ b3_static_pill(...) }}` call sites — and those five have now left
> the `pill pill-count tag-chip` row entirely, so every remaining use
> of that combination is interactive. The rest of the audit is
> unchanged and still describes the code.

## What is already right, and should survive any change

- **The interactive pills are accessible.** They carry `role="button"`,
  `tabindex="0"` and `aria-pressed`, so a screen reader and a keyboard
  already distinguish what the eye cannot. Whatever visual treatment is
  chosen must not be a reason to drop those.
- **The state vocabulary is consistent.** `is-selected` means "on" for
  every chip that has an on/off state, and the semantic modifiers
  (`pill-info` / `-success` / `-warning` / `-error` / `-super`) are
  **display-only in every one of their 50 uses** — no clickable pill
  borrows a status colour, so status and interactivity are not yet
  entangled.
- **The two jobs are unevenly distributed**, which makes a fix cheap
  to aim: 32 of the 61 interactive pills are on one page
  (`session_extract_data.html`), and three of the heaviest templates
  are display-only.

## Open questions for the decision

1. **Which side moves?** 189 display against 61 interactive says the
   label is the default reading and the control is the exception — so
   the control is the one that should look different. The reverse
   (restyling 189 labels) is three times the diff for the same result.
2. **What carries the signal?** A border, a background, an affordance
   glyph, or shape (a pill for labels, something squarer for buttons).
   Not decided here.
3. **Does `is-selected` survive?** It currently means "this filter is
   on", which is only meaningful on a control. If controls grow their
   own vocabulary, the selected state may belong to it rather than to
   the pill.
4. **What about `b3_static_pill`?** It is a label wearing a control's
   classes. It wants fixing whatever else is decided, and it is the
   one item in this audit that is a defect rather than a design
   question.
5. **Scope of `col-chip-row`** — 6 / 6 is a container class, not an
   element one, so its split probably means something different from
   the others and needs a closer look before it is counted as
   ambiguous.

## Reproducing this

The scan is a throwaway script, deliberately not committed: the numbers
are a snapshot taken to inform one decision, and a committed scanner
would invite someone to trust it after the markup has moved. To re-take
them, walk `app/web/templates/**/*.html`, collect elements whose class
tokens match `pill|chip`, and classify on the tag name plus the
attribute list above.

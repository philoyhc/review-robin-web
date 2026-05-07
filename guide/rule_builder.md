# Rule Builder card layout

Layout spec for the Rule Builder page
(`/operator/sessions/{id}/assignments/rule-based-editor`).
The title card with the breadcrumb and the `<h1>Rule Builder</h1>`
heading is **not** in scope here — this spec covers the two cards
below it: the **Rule Builder card** (left) and the **Available
rulesets** card (right).

> Status: implemented in Segment 13A-1 (PRs #587, #588, #589, #596,
> #597, #598, #599). This doc captures the as-shipped layout so a
> future revisit has a single reference point.

## Page shape

The two cards sit side-by-side in a flex grid, each at half the
page content width. The Rule Builder card is on the left; the
Available rulesets card is on the right.

```
┌─────────── Rule Builder card (½) ──────────┐  ┌──── Available rulesets card (½) ────┐
│                                             │  │                                      │
│  [ RuleSet selector ▾ ]   [ Name input  ]   │  │  ▶ Full Matrix          [seed]       │
│  Pair every reviewer with every reviewee.   │  │    Pair every reviewer with every…   │
│  (caption only on seeded read-only)         │  │                                      │
│                                             │  │    Intra-group peer review  [seed]   │
│  Friendly Description (optional)            │  │    Match same-group reviewer/…       │
│  [ User created ruleset                  ]  │  │                                      │
│  (only on editable branches)                │  │    Cross-group peer review  [seed]   │
│                                             │  │    …                                 │
│  Combine these rules with:                  │  │                                      │
│  [ All of  ▾ ]                              │  │    My team review     [personal]     │
│                                             │  │    A team review                     │
│  Rules                                      │  │                                      │
│  1. Match — reviewer.tag1 is the same as …  │  └──────────────────────────────────────┘
│  2. Filter — reviewer.email is set          │
│                                             │
│  [ + MATCH rule ] [ + FILTER rule ] …       │
│                                             │
│  [ Copy ] [ Save ] [ Cancel ] [ Delete ]    │
│  ↑ bottom-left, outside the body            │
└─────────────────────────────────────────────┘
```

## Rule Builder card (left)

1. **Width.** Half the page content width. The width comes from a
   page-level flex grid that holds the Rule Builder card + the
   Available rulesets card; the card itself doesn't carry a
   `max-width`.

2. **Inner row** at the top — chromeless (no card border, no
   padding, transparent background — visually part of the outer
   card, structurally a flex row). Two flex children at 1/2 each:
   - **RuleSet selector** (left). Always present, in every state.
   - **Name input** (right). Visible only when an editable name
     exists — i.e., on saved Personal RuleSets, Copy drafts (pre-
     populated with `Copy of <source>`), and the blank draft (pre-
     populated with `New RuleSet`). Hidden for seeded selections;
     when hidden, the selector stays at 1/2 width and the right
     half stays empty (the selector does **not** expand).
   - On seeded read-only selections the RuleSet's stored
     description renders as a one-line caption immediately under
     the dropdown, as a passive helper. Editable branches drop
     this caption — the description moves into the editable
     textarea below (rule #4).

3. **No separate title heading.** The dropdown's selected option
   (for seeds) and the inline name input (for editable selections)
   carry the title. No `<h2>` heading row, no scope pill above the
   body.

4. **Friendly Description (optional)** textarea, full width, below
   the inner row. Editable branches only (drafts + saved Personal).
   - Hoisted into the editable POST form via the HTML
     `form="rule-based-editor-form"` attribute so it can sit
     visually outside the form's body but still submit with it.
   - **Default value on a fresh Copy / blank draft:** `"User
     created ruleset"`. Operators are expected to overwrite.
     Saved-Personal selections preserve their stored description
     across reloads.
   - Persists via the existing `/save` route, which writes
     through to `rule_sets.description`.

5. **Body** — single column, top-to-bottom:
   - `Combine these rules with:` helper sentence above the
     combinator selector / read-only pill. No bold "Combinator"
     heading.
   - Random seed input (when the RuleSet revision carries one).
   - "Rules" list — sentence-shaped sentences for seeds (read-
     only), inline-composite editable form for editable branches.
   - `+ MATCH rule`, `+ FILTER rule`, `+ QUOTA rule`, `+ COMPOSITE
     rule` buttons (no `Add` prefix) on editable branches.
   - **No "Exclude self-review" affordance** — that control lives
     on the main Assignments page. The `exclude_self_reviews`
     value still travels with each RuleSet revision; the Rule
     Builder card just doesn't expose a UI for it. Seeded views
     similarly omit the "Exclude self-review: on/off" pill row.

6. **Banners** sit between the inner row and the body. State-
   driven, copy-locked:
   - Seeded → "This is a read-only seeded RuleSet. Click **Copy**
     to create an editable Personal copy."
   - Blank-draft sentinel → "Starting from scratch. Add at least
     one rule, then click **Save** to persist a new Personal
     RuleSet."
   - Copy / draft → "Unsaved draft. Edit and **Save** to persist a
     new Personal RuleSet, or **Cancel** to discard."
   - Save error / save success → standard error / info banners
     keyed off `?error=` / `?saved=1`.

7. **Action row** at the bottom of the card, **outside** the body.
   Left-aligned. Selection-aware:
   - Seeded → `[ Copy ]`
   - Saved Personal → `[ Copy ] [ Save ] [ Cancel ] [ Delete ]`
   - Copy draft / blank draft → `[ Save ] [ Cancel ]`
   - Blank draft's `Save` is `disabled` client-side until the
     rule list grows past zero rows; the server-side gate is the
     source of truth and rejects a zero-rule submit with
     `?error=empty_rules`.

## Available rulesets card (right)

1. **Width.** Half the page content width — paired with the Rule
   Builder card via the page-level flex grid.

2. **Title.** `<h2>Available rulesets</h2>` at the top of the
   card.

3. **List.** One row per visible RuleSet, in the same order as the
   Rule Builder dropdown:
   - Seeds first, in install order (Full Matrix → Intra-group →
     Cross-group → Same-group different-role → Three reviewers
     per reviewee).
   - Caller-owned Personal RuleSets after, in id order (matches
     the dropdown convention until the field reports a need for
     most-recently-updated sort).
   - Each row carries `name`, a `seed` / `personal` pill, and the
     RuleSet's `description` as a `form-help` caption beneath.

4. **Active row highlight.** The row matching the Rule Builder's
   current selection renders highlighted (`▶` prefix on the name
   + `available-ruleset-row-active` class). Drafts (Copy / blank)
   produce no highlight — they don't correspond to a persisted
   row.

5. **Click behaviour.** Out of scope — rows are read-only at the
   moment. Operators switch RuleSets via the Rule Builder
   dropdown. Adding "click row to load" is a future enhancement.

## Out of scope

- Mobile / narrow viewport: the side-by-side flex grid will need a
  collapse rule when the page narrows. Capture when we wire
  responsive breakpoints in Segment 14.
- Click-to-load on Available rulesets rows.
- Search / filter on the Available rulesets list (assumes
  operators have a handful of saved RuleSets per session).

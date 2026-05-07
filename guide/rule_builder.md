# Rule Builder card layout — spec

Layout spec for the rule-editing card on the Rule Builder page
(`/operator/sessions/{id}/assignments/rule-based-editor`). The
title card with the breadcrumb and the `<h1>Rule Builder</h1>`
heading is **not** in scope here — this is just the card below it
that holds the selector + form.

> Status: spec only, not implemented. Apply on top of Segment 13A-1.

## Shape

```
┌─────────────────────────── outer card (½ width of page) ──────────────────────────┐
│                                                                                    │
│  ┌─────────────────────── inner card ──────────────────────────────────────────┐  │
│  │                                                                              │  │
│  │   [ RuleSet selector ▾ ]              [ Copy Name input        ]             │  │
│  │   ←——— ½ of inner ———→                ←——— ½ of inner ———→                   │  │
│  │                                       (only when an editable name exists)    │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                    │
│   [ All of  ▾ ]                                                                    │
│                                                                                    │
│   Rules                                                                            │
│   1. Match — reviewer.tag1 …                                                       │
│   2. Filter — reviewer.email …                                                     │
│                                                                                    │
│   [ + MATCH rule ] [ + FILTER rule ] …                                             │
│                                                                                    │
│   [ Copy ] [ Save ] [ Cancel ] [ Delete ]                                          │
│   ↑ bottom-left, outside the body                                                  │
└────────────────────────────────────────────────────────────────────────────────────┘
```

## Rules

1. **Outer card width.** Half the page content width. (Sits in a
   layout that leaves the right half free for a future preview /
   adjacent panel; nothing renders there in this spec.)

2. **Nested inner card** at the top of the outer card. Holds:
   - **RuleSet selector** (the dropdown). Half width of the inner
     card. Always present, in every state.
   - **Name input** to its right. Half width of the inner card.
     Visible only when an editable name exists — i.e., on saved
     Personal RuleSets, on Copy drafts (pre-populated with `Copy of
     <source>`), and on the blank draft (pre-populated with
     `New RuleSet`). Hidden for seeded selections (read-only).

3. **No separate title heading.** Drop the current
   `<h2>{name}</h2> + <pill>{seed|personal|draft}</pill>` row.
   - For editable selections the name input *is* the title.
   - For seeded read-only selections the dropdown's selected option
     *is* the title. The "seed" pill goes away (the `(seeded)`
     suffix in the dropdown carries the same signal).

4. **Body keeps its current single-column layout.** Combinator
   selector, Random seed (when applicable), Rules list, and the
   "+ MATCH/FILTER/QUOTA/COMPOSITE rule" buttons render top-to-
   bottom inside the outer card, exactly as the current Segment
   13A-1 PR 1–3 implementation does, with these trims:
   - **Drop the "Combinator" heading.** The selector / read-only
     pill stands on its own — its purpose is obvious from the
     dropdown's labels (`All of` / `Any of` / `In sequence`).
   - **Drop the "Exclude self-review" checkbox** (and its "Self-
     review" heading). The same affordance is exposed on the main
     Assignments page; surfacing it inside the Rule Builder card
     duplicates a control. The underlying `exclude_self_reviews`
     value still travels with each RuleSet revision — the editor
     just doesn't expose a UI for it. Read-only seeded views also
     drop the "Exclude self-review: on/off" pill row.

5. **Action row.** Stays at the bottom of the outer card, **outside**
   the body. Left-aligned. Same selection-aware buttons as today
   (Segment 13A-1 PR 2 locked decisions):
   - Seeded → `[ Copy ]`
   - Saved Personal → `[ Copy ] [ Save ] [ Cancel ] [ Delete ]`
   - Copy draft / blank draft → `[ Save ] [ Cancel ]`

6. **Name input hidden state.** When the Name input is hidden
   (seeded selection), the selector stays at half width — it does
   **not** expand. The right half of the inner card stays empty.

## Out of scope

- Mobile / narrow viewport: the half-width outer card will need a
  collapse rule. Capture when we wire responsive breakpoints in
  Segment 14.

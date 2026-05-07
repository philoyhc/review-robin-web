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
│   Combinator               │    Self-review                                        │
│   [ All of  ▾ ]            │    [✓] Exclude self-review …                          │
│                            │                                                       │
│                            │    Rules                                              │
│                            │    1. Match — reviewer.tag1 …                         │
│                            │    2. Filter — reviewer.email …                       │
│                            │                                                       │
│                            │    [ + Add MATCH ] [ + Add FILTER ] …                 │
│                            │                                                       │
│   ↑ 1/3 width              ↑ 2/3 width, vertical line separates                    │
│                                                                                    │
│   [ Copy ] [ Save ] [ Cancel ] [ Delete ]                                          │
│   ↑ bottom-left, OUTSIDE the two columns                                           │
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

4. **Two-column body** below the inner card:
   - **Left column, 1/3 width.** "Combinator" heading + the
     combinator selector / read-only label.
   - **Right column, 2/3 width.** Everything else from the current
     card body — Self-review, Random seed (when applicable), Rules
     list, "+ Add MATCH/FILTER/QUOTA/COMPOSITE" buttons.
   - **Vertical divider** between the two columns. (1px line, same
     visual weight as the inner-card border.)

5. **Action row.** Stays at the bottom of the outer card, **outside**
   the two-column body. Left-aligned. Same selection-aware buttons
   as today (Segment 13A-1 PR 2 locked decisions):
   - Seeded → `[ Copy ]`
   - Saved Personal → `[ Copy ] [ Save ] [ Cancel ] [ Delete ]`
   - Copy draft / blank draft → `[ Save ] [ Cancel ]`

6. **Name input hidden state.** When the Name input is hidden
   (seeded selection), the selector stays at half width — it does
   **not** expand. The right half of the inner card stays empty.

7. **Read-only seeded body split.** The seeded read-only body uses
   the same two-column convention as the editable body: Combinator
   label on the left (1/3), sentence-shaped rule lines + self-
   review status on the right (2/3), vertical divider between them.

## Out of scope

- Mobile / narrow viewport: the half-width outer card will need a
  collapse rule. Capture when we wire responsive breakpoints in
  Segment 14.


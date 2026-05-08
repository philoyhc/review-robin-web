# Functional Specification

## Advanced Mode for Reviewer–Reviewee Assignment Generation

---

## 1. Purpose and Scope

The assignment engine currently exposes two modes in the UI:

- **Simple mode** — toggles for *Full Matrix* and *Exclude self-reviews*.
- **Manual mode** — users upload the exact assignments they want.

This document specifies a third mode, **Advanced mode**, which generates assignments from a configurable **RuleSet** that references the unique identifier (email) and the three attribute tags carried by every reviewer and reviewee. Advanced mode also introduces persistence: RuleSets can be saved, named, edited, and reused across cycles, and the system ships with a small library of seeded RuleSets covering common patterns.

Simple and Manual modes are unchanged. Advanced mode appears alongside them as a third option in the mode picker.

---

## 2. Relationship to Existing Modes

| Mode | Input | Output | Status |
|---|---|---|---|
| Simple | Two toggles | Generated assignments | Existing, unchanged |
| Manual | Uploaded list of pairs | Those exact assignments | Existing, unchanged |
| **Advanced** | **A RuleSet** | **Generated assignments** | **New, this spec** |

Advanced mode is conceptually a superset of Simple mode — anything Simple mode can produce, Advanced mode can also produce — but the two remain separate UI surfaces. Users who only need Full Matrix or self-exclusion are not pushed into the rule editor.

---

## 3. Domain Model

### 3.1 Person

A Person is the common shape used for both reviewers and reviewees. A single individual may appear in both populations.

| Field | Type | Notes |
|---|---|---|
| `name` | string | Display name. Not used for matching. |
| `email` | string (unique) | Canonical identifier. Case-insensitive. Used to detect self-pairings. |
| `tag1`, `tag2`, `tag3` | string (nullable) | Three free-form attribute tags per Person, e.g. group, cohort, seniority, department, region. |

### 3.2 Assignment

An Assignment is an ordered pair `(reviewer, reviewee)`. The pair `(A, B)` is distinct from `(B, A)`; each represents a different review obligation.

### 3.3 Reviewer and Reviewee Populations

The reviewer set **R** and the reviewee set **E** are supplied independently. They may be identical, disjoint, or overlapping. All rules operate on the Cartesian product **R × E** and progressively constrain it.

---

## 4. RuleSet Model

### 4.1 Conceptual Pipeline

```
candidates = R × E    →    apply RuleSet    →    final Assignments
```

A RuleSet is an ordered list of Rules together with a top-level **combinator**. Each Rule classifies a candidate pair as included, excluded, or untouched. The combinator decides how the per-rule verdicts are merged into the final decision.

### 4.2 Rule Kinds

- **Filter rules** — remove pairs that match a predicate (e.g. exclude cross-group pairings).
- **Match rules** — include pairs that match a predicate (e.g. same Tag1, different Tag2).
- **Quota rules** — cap or require a number of reviewers per reviewee (or vice versa).
- **Composite rules** — group other rules under AND / OR / NOT.

### 4.3 Combinator Semantics

| Combinator | Semantics |
|---|---|
| `ALL_OF` (AND) | A pair is included iff every rule includes it. Strictest; intersection of allowed sets. |
| `ANY_OF` (OR) | A pair is included iff at least one rule includes it. Used to union relationships (e.g. "same group OR same cohort"). |
| `PIPELINE` | Rules are applied in order; each rule may add to or remove from the working set. Last-writer-wins per pair. Useful for "start with everything, then exclude…" patterns. |

### 4.4 Predicate Vocabulary

Filter and Match rules are defined as predicates over a candidate pair `(r, e)`. The vocabulary uses two address spaces: `reviewer.*` and `reviewee.*`. The available fields are `email`, `tag1`, `tag2`, `tag3`.

| Operator | Operand | Meaning |
|---|---|---|
| `equals` / `not_equals` | literal or field | Direct comparison. Compare to a literal (`"Group01"`) or to another field (`reviewee.tag1`). |
| `in` / `not_in` | list of literals | Set membership, e.g. `reviewer.tag2 in ["Senior", "Lead"]`. |
| `matches` / `not_matches` | regex string | Pattern match. Useful for prefix conventions like `Group\d+`. |
| `is_empty` / `is_not_empty` | (none) | Treats null and empty string as empty. |
| `same_as` / `different_from` | field on the other side | Sugar for cross-side comparison. `reviewer.tag1 same_as reviewee.tag1`. |

All string comparisons are case-insensitive and trim leading/trailing whitespace by default. A rule may opt in to case-sensitive comparison via a flag on the predicate.

### 4.5 Filter Rule Example

```json
{
  "id": "no_cross_region",
  "kind": "FILTER",
  "predicate": { "reviewer.tag3": { "different_from": "reviewee.tag3" } }
}
```

### 4.6 Match Rule Example

```json
{
  "id": "same_group",
  "kind": "MATCH",
  "predicate": { "reviewer.tag1": { "same_as": "reviewee.tag1" } }
}
```

### 4.7 Quota Rule

A Quota rule constrains the **multiplicity** of assignments. It does not select pairs by content; it caps the number of pairs that survive after the content rules have run.

- `scope` — `PER_REVIEWER` or `PER_REVIEWEE`.
- `min`, `max` — inclusive bounds. Either may be `null`.
- `selection` — `RANDOM` (with optional seed) or `ROUND_ROBIN`.

```json
{
  "id": "three_reviewers_each",
  "kind": "QUOTA",
  "scope": "PER_REVIEWEE",
  "min": 3, "max": 3,
  "selection": { "strategy": "RANDOM", "seed": 42 }
}
```

### 4.8 Composite Rule

```json
{
  "id": "intra_group_cross_role",
  "kind": "COMPOSITE",
  "op": "AND",
  "rules": [
    { "kind": "MATCH", "predicate": { "reviewer.tag1": { "same_as": "reviewee.tag1" } } },
    { "kind": "MATCH", "predicate": { "reviewer.tag2": { "different_from": "reviewee.tag2" } } }
  ]
}
```

### 4.9 RuleSet Structure

```
RuleSet {
  id:           string                  // stable across edits; assigned on save
  name:         string                  // user-visible
  description:  string
  combinator:   ALL_OF | ANY_OF | PIPELINE
  rules:        Rule[]                  // ordered
  options: {
    excludeSelfReviews: boolean         // shorthand for the canonical filter
    seed:               integer | null  // global seed for any RANDOM selections
  }
  metadata: {
    isSeed:     boolean                 // true for system-provided RuleSets
    createdBy:  string | null           // null for seeds
    createdAt:  timestamp
    updatedAt:  timestamp
  }
}
```

The `excludeSelfReviews` option is preserved at the RuleSet level even though Filter rules can express the same thing. It is the single most common control, and surfacing it as a checkbox on every RuleSet is clearer than expecting users to add the rule each time. Internally it is desugared to a filter applied before any other rule.

---

## 5. Persistence and Library

### 5.1 Storage Scopes

Saved RuleSets live in two scopes:

- **Personal** — visible only to the user who saved them. The default scope when a user clicks Save.
- **Shared** *(optional, behind a permission)* — visible to all users in the workspace. Used for organisation-wide standards.

Seeded RuleSets are read-only. A user who wants to modify one duplicates it; the duplicate becomes a Personal RuleSet that can be edited freely.

### 5.2 Operations

The library supports the standard set of operations on RuleSets:

- **Save** — persist the current editor state. New RuleSets are created in Personal scope; existing ones can be saved in place or saved as a new copy.
- **Load** — open a saved RuleSet in the editor.
- **Duplicate** — create an editable copy of any RuleSet, including seeds.
- **Rename** — change the user-visible name.
- **Delete** — remove a Personal or Shared RuleSet. Seeded RuleSets cannot be deleted.
- **Export / Import** — JSON download and upload, so RuleSets can be shared across workspaces or version-controlled outside the system.

### 5.3 Versioning

Each Save updates `updatedAt` and writes a new revision. The library shows the current revision; previous revisions are retained for audit and can be restored by an administrator. RuleSets in active use by a scheduled or in-progress assignment cycle are pinned by reference, so editing the RuleSet does not retroactively change past assignments.

### 5.4 Seeded RuleSets

The system ships with the following seeds. Each is intended to be useful as-is and also as a starting point for duplication.

| Seed name | Combinator | Behaviour |
|---|---|---|
| **Full Matrix** | `ALL_OF`, no rules, exclude self | Equivalent to Simple mode's default. Included for completeness. |
| **Intra-group peer review** | `ALL_OF`, exclude self | Reviewer and reviewee share `tag1`. The canonical small-group case. |
| **Cross-group peer review** | `ALL_OF`, exclude self | Reviewer and reviewee have *different* `tag1`. Useful for fresh-perspective rounds. |
| **Same group, different role** | `ALL_OF`, exclude self | Same `tag1`, different `tag2`. Pair within the team but never with someone of the same role. |
| **Three reviewers per reviewee** | `ALL_OF`, exclude self | Full candidate pool, then a `PER_REVIEWEE` quota of `min=3, max=3`, random with a fixed seed. |

Seed names are illustrative; the final set is chosen with the product owner before release. The point is that the library is non-empty on first use, so a user can pick a working RuleSet without authoring one from scratch.

---

## 6. Evaluation Algorithm

Given populations R and E and a RuleSet S:

1. Build the candidate set **C = R × E**.
2. If `options.excludeSelfReviews` is true, drop pairs where `reviewer.email` equals `reviewee.email` (case-insensitive).
3. Partition the rules into **content rules** (`FILTER`, `MATCH`, `COMPOSITE`) and **quota rules** (`QUOTA`).
4. Apply the content rules according to the combinator: `ALL_OF` intersects allowed sets; `ANY_OF` unions them; `PIPELINE` applies each rule in order to the working set.
5. Apply quota rules in declaration order. Where a quota cannot be satisfied (e.g. the candidate pool is too small), surface a validation error rather than silently producing fewer assignments.
6. Emit the surviving pairs as Assignments, in deterministic order (`reviewer.email`, then `reviewee.email`).

---

## 7. Advanced Mode UI

The Advanced mode UI is split between two surfaces:

- The **Rule Based card** on the per-session Assignments page (`/operator/sessions/{id}/assignments`) — picks a RuleSet from the visible library, runs `Generate` against the current populations, and writes the resulting Assignments into the cycle. Records which RuleSet (and revision) was used so the cycle's provenance is preserved.
- The **Rule Builder page** at `/operator/sessions/{id}/assignments/rule-based-editor` — an authoring surface for creating, copying, editing, and deleting Personal RuleSets.

### 7.1 Rule Based card on the Assignments page

Lives in the top-left of the action grid on `/operator/sessions/{id}/assignments` (per `spec/setup_pages.md` "Assignments page"). The card lets the operator pick a RuleSet from the visible library, dry-run it against the current populations, and click `Generate` to write the resulting Assignments. Top to bottom:

1. **RuleSet dropdown.** Populated with every visible RuleSet (5 seeds in install order, then caller-owned Personal RuleSets, sorted oldest-first). Default selection is the first seed (Full Matrix).

2. **Description line.** A `form-help` paragraph rendering the selected RuleSet's `description`. Inline JS keeps it in sync with the dropdown selection without a page reload.

3. **"Number of eligible pairs found: {N}"** pill row. The `{N}` is the engine's dry-run pair-count for the selected RuleSet against the *current* reviewer / reviewee populations. Computed at view-shape build time by running `engine.evaluate(rule_set_schema, reviewers, reviewees)` per visible RuleSet and recording `len(result.pairs)` on `RuleBasedSelectorOption.eligible_pair_count`. Each `<option>` carries the count as a `data-eligible-pairs` attribute so the inline JS can swap the pill text on dropdown `change` without a reload. Engine bails (malformed schema) fall back to `0` so the card still renders. Empty populations → `0`.

4. **Exclude self-review** checkbox. Default mirrors the selected RuleSet's `excludeSelfReviews` flag; the checkbox value is the override that travels with the audit row.

5. **Confirm-replace** checkbox (only when assignments already exist on the session).

6. **Action row** (bottom-left): `Generate` (Secondary, posts `/assignments/rule-based/generate`) + `Edit ruleset` (Secondary, opens the Rule Builder page focused on the currently-selected RuleSet).

7. **"Last generated using {RuleSet}: {N} assignments"** form-help line. Renders only when the session has a prior rule-based generation in the audit log. The card previously surfaced a redundant `{N} unique pairs` pill alongside `{N} assignments` — that pill was retired since the new "Number of eligible pairs found" row covers the pre-Generate visibility.

### 7.2 Rule Builder page

> Implemented in Segment 13A-1 (PRs #587, #588, #589, #596, #597, #598, #599 plus the iterated layout-spec stream #590–#600).

The page renders, top-to-bottom: the chrome (with `Assignments` highlighted as the current Setup tab), a top-of-body `<a class="back-link">← Back to Assignments</a>`, then two cards side-by-side in a flex grid, each at half the page content width — the **Rule Builder card** (left) and the **Available rulesets card** (right). The Rule Builder's H2 title sits inside the Rule Builder card itself; there is no separate title card on the page.

```
┌─────────── Rule Builder card (½) ──────────┐  ┌──── Available rulesets card (½) ────┐
│  Rule Builder                               │  │                                      │
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

#### 7.2.1 Rule Builder card (left)

1. **Width.** Half the page content width. The width comes from a page-level flex grid that holds the Rule Builder card + the Available rulesets card; the card itself doesn't carry a `max-width`.

2. **Inner row** at the top — chromeless (no card border, no padding, transparent background — visually part of the outer card, structurally a flex row). Two flex children at 1/2 each:
   - **RuleSet selector** (left). Always present, in every state.
   - **Name input** (right). Visible only when an editable name exists — i.e., on saved Personal RuleSets, Copy drafts (pre-populated with `Copy of <source>`), and the blank draft (pre-populated with `New RuleSet`). Hidden for seeded selections; when hidden, the selector stays at 1/2 width and the right half stays empty (the selector does **not** expand).
   - On seeded read-only selections the RuleSet's stored description renders as a one-line caption immediately under the dropdown. Editable branches drop this caption — the description moves into the editable textarea below (rule #4).

3. **No separate title heading.** The dropdown's selected option (for seeds) and the inline name input (for editable selections) carry the title. No `<h2>` heading row, no scope pill above the body.

4. **Friendly Description (optional)** textarea, full width, below the inner row. Editable branches only (drafts + saved Personal).
   - Hoisted into the editable POST form via the HTML `form="rule-based-editor-form"` attribute so it can sit visually outside the form's body but still submit with it.
   - **Default value on a fresh Copy / blank draft:** `"User created ruleset"`. Operators are expected to overwrite. Saved-Personal selections preserve their stored description across reloads.
   - Persists via the existing `/save` route, which writes through to `rule_sets.description`.

5. **Body** — single column, top-to-bottom:
   - `Combine these rules with:` helper sentence above the combinator selector / read-only pill. No bold "Combinator" heading.
   - Random seed input (when the RuleSet revision carries one).
   - "Rules" list — sentence-shaped sentences for seeds (read-only), inline-composite editable form for editable branches. Each editable rule row carries a 6 px-wide vertical bar at its left edge (rendered as an absolutely-positioned `::before` so it can be inset 6 px top + bottom for a small gap between consecutive rows). The bar colour comes from a per-row inline `--rule-bar-color` CSS custom property — `#999` on COMPOSITE rows, `#ddd` elsewhere.
   - `+ MATCH rule`, `+ FILTER rule`, `+ QUOTA rule`, `+ COMPOSITE rule` buttons (no `Add` prefix) on editable branches.
   - **No "Exclude self-review" affordance** — that control lives on the main Assignments page. The `exclude_self_reviews` value still travels with each RuleSet revision; the Rule Builder card just doesn't expose a UI for it. Seeded views similarly omit the "Exclude self-review: on/off" pill row.

6. **Banners** sit between the inner row and the body. State-driven, copy-locked:
   - Seeded → "This is a read-only seeded RuleSet. Click **Copy** to create an editable Personal copy."
   - Blank-draft sentinel → "Starting from scratch. Add a rule, then **Save** to persist new Personal RuleSet."
   - Copy / draft → "Unsaved draft. Edit and **Save** to persist a new Personal RuleSet, or **Cancel** to discard."
   - Save error / save success → standard error / info banners keyed off `?error=` / `?saved=1`.

7. **Action row** at the bottom of the card, **outside** the body. Left-aligned. Selection-aware:
   - Seeded → `[ Copy ]`
   - Saved Personal → `[ Copy ] [ Save ] [ Cancel ] [ Delete ]`
   - Copy draft / blank draft → `[ Save ] [ Cancel ]`
   - Button taxonomy: Copy, Save, and Cancel render `btn secondary` (Secondary); Delete renders `btn destructive` (Destructive). See `guide/all_buttons.md` Section 16 for the canonical row.
   - Blank draft's `Save` is `disabled` client-side until the rule list grows past zero rows; the server-side gate is the source of truth and rejects a zero-rule submit with `?error=empty_rules`.

#### 7.2.2 Available rulesets card (right)

1. **Width.** Half the page content width — paired with the Rule Builder card via the page-level flex grid.

2. **Title.** `<h2>Available rulesets</h2>` at the top of the card.

3. **List.** One row per visible RuleSet, in the same order as the Rule Builder dropdown:
   - Seeds first, in install order (Full Matrix → Intra-group → Cross-group → Same-group different-role → Three reviewers per reviewee).
   - Caller-owned Personal RuleSets after, in id order (matches the dropdown convention until the field reports a need for most-recently-updated sort).
   - Each row carries `name`, a `seed` / `personal` pill, and the RuleSet's `description` as a `form-help` caption beneath.

4. **Active row highlight.** The row matching the Rule Builder's current selection renders highlighted (`▶` prefix on the name + `available-ruleset-row-active` class). Drafts (Copy / blank) produce no highlight — they don't correspond to a persisted row.

5. **Click behaviour.** Out of scope today — rows are read-only. Operators switch RuleSets via the Rule Builder dropdown. Adding "click row to load" is a future enhancement.

#### 7.2.3 Out of scope

- Mobile / narrow viewport: the side-by-side flex grid will need a collapse rule when the page narrows. Capture when we wire responsive breakpoints in Segment 14.
- Click-to-load on Available rulesets rows.
- Search / filter on the Available rulesets list (assumes operators have a handful of saved RuleSets per session).

### 7.2 Predicate editor

Inside the Rule Builder card's editable branches, each rule row is an indented inline-composite form: an `enabled` checkbox + a kind selector + a field/operator/operand picker (or quota controls for `QUOTA`, or a child rule list for `COMPOSITE`). Field, operator, and operand pickers are populated from the schema's vocabulary (§4.4); they aren't tied to the loaded populations' actual values — populations may not yet exist when the RuleSet is authored. (A future enhancement could populate operand suggestions from the live populations once present.)

### 7.3 Save / Save-As / Delete

Saving an existing Personal RuleSet appends a new revision in place; saving a draft (Copy or blank) creates a new Personal row. The Copy flow stores no row until the operator hits Save (locked decision: "Copy creates an unsaved draft"). Delete soft-deletes the RuleSet — past `assignments.generated` audit refs still resolve through `library.load_rule_set`, which intentionally doesn't filter on `deleted_at`.

Seeded RuleSets are read-only — their action row exposes only `[ Copy ]`. Selecting a seed and clicking Copy creates an unsaved draft cloning that seed's rules; saving the draft creates a Personal RuleSet.

---

## 8. Worked Example: Small-Group Peer Review

Reviewers and reviewees are the same population. Every Person has Tag1 set to a group code such as `Group01`, `Group02`, with five members per group. The desired behaviour is that each Person reviews every other member of their group.

The user opens Advanced mode, picks **Intra-group peer review** from the seed library, reviews the preview (it confirms 20N assignments for N groups of 5), and clicks Generate. No editing required.

If the user later wants to add cross-group lead reviews, they Duplicate the seed, add a second rule under `ANY_OF`:

```json
{
  "id": "cross_group_leads", "kind": "COMPOSITE", "op": "AND",
  "rules": [
    { "kind": "MATCH", "predicate": { "reviewer.tag2": { "equals": "Lead" } } },
    { "kind": "MATCH", "predicate": { "reviewee.tag2": { "equals": "Lead" } } },
    { "kind": "MATCH", "predicate": { "reviewer.tag1": { "different_from": "reviewee.tag1" } } }
  ]
}
```

…and save it as a Personal RuleSet named *"Peer review with cross-group leads"*. The next cycle reuses it from the library.

---

## 9. Validation and Error Handling

- Unknown fields or operators in a predicate are rejected at save time.
- Quotas that cannot be satisfied by the candidate pool produce a structured error identifying the affected reviewers or reviewees.
- A RuleSet that produces zero assignments emits a warning, not an error; the user may have intended an empty result.
- Empty tag values are treated consistently as missing; predicates referencing a missing field evaluate to false unless the operator is `is_empty`.
- Importing a RuleSet whose schema version is newer than the current engine is rejected with a clear message.

---

## 10. Out of Scope

- Workload balancing across multiple review cycles.
- Reviewer preferences or conflict-of-interest declarations beyond what the three tags encode.
- Optimisation objectives such as minimising repeat pairings across cycles. These may be addressed in a later iteration by extending Quota rules with history-aware selection strategies.
- Editing or deleting Seeded RuleSets in place. Seeds are managed by a separate administrative process.

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
| **Lead-led review** | `ANY_OF`, exclude self | Union of (a) intra-group pairings and (b) cross-group pairings where both sides have `tag2 = "Lead"`. |

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

### 7.1 Editor

The Advanced mode screen has three regions:

- **Library panel** — lists Seeded, Personal, and Shared RuleSets. Selecting one loads it into the editor. A New button creates a blank RuleSet.
- **Rule editor** — shows the RuleSet's metadata (name, description), the combinator selector, the `excludeSelfReviews` checkbox, and the ordered list of rules. Each rule has an enable toggle, a kind selector, and a predicate editor. The predicate editor's field, operator, and operand pickers are populated from the actual tag values present in the loaded populations, so users select from real data rather than typing strings.
- **Preview panel** — shows the assignment count the current RuleSet would produce, the distribution per reviewer and per reviewee, and a sampled set of pairs. The preview updates as rules are edited so misconfiguration is caught before generation.

### 7.2 Save Dialogue

The Save action prompts for name, description, and scope (Personal / Shared). Saving an existing RuleSet offers Save (overwrite) and Save As (new copy). Save As is the primary action when the loaded RuleSet is a seed, because seeds are read-only.

### 7.3 Generate

A Generate button at the bottom of the editor runs the evaluation algorithm against the current populations and writes the resulting Assignments into the cycle. The button records which RuleSet (and revision) was used so the cycle's provenance is preserved.

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

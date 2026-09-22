# Findings — `spec/csv_contracts.md` §3.2, 2026-09-22

**19S Item 4 rung 1.** Ten findings: **four spec-vs-code, five
spec-silent, one code-internal**. The section documents the
Relationships importer. 19R Item 4 and 19R's closing `spec-writer` pass both found
its signature line stale; the item exists because **nobody had checked
the rest of the section against the code at all**, and fixing the one
visible line would have made the unexamined claims *look* verified.

So this is the behavior first, adjudication second — the author's
framing. Every answer below was **run**, not read: the probe built a
two-reviewer / two-reviewee roster in memory and called
`parse_relationship_csv` on twelve CSVs, one per question. Nothing here
is a restatement of the spec.

**One seam runs through several rows.** The parser reports; the two
callers decide whether to save. §3.2 documents the first and is silent
on the second, so five rows need a sentence *added* to
the spec rather than a sentence *corrected*.

Rung 1 changed no spec and no code. Each divergence is a choice between
*fix the code* and *change the contract deliberately*, which
`rrw_sdd_in_practice.md` §4 makes the author's call, not an
investigation's.

## What the code does

| Question | The code's answer | Where |
|---|---|---|
| Resolves against what, by string or by row? | **Loaded ORM rows.** `reviewers: list[Reviewer]` / `reviewees: list[Reviewee]`; the parser builds `normalize_email`-keyed dicts from `reviewer.email` and `reviewee.email_or_identifier` and returns resolved FK ids so save need not re-look-up. | `relationships.py:49`, `:94` |
| Unknown reviewer / reviewee | Per-row `error`, *"Unknown reviewer 'x' — import reviewers first."*, then `continue`. | `:137`, `:152` |
| Blank cell / whitespace-only cell | Identical: `_cell` strips, so `"   "` is `""` → *"ReviewerEmail is required"*. | `csv_imports.py:163`, `relationships.py:105` |
| Duplicate pair | Keyed on the **resolved `(reviewer_id, reviewee_id)`**, so two spellings of one pair collide. **The first occurrence is the one kept in `ParseResult`**; the second is rejected with a message naming the prior row, reported against `field="ReviewerEmail"`. Whether either reaches storage is row 4's question, not this one. | `:159` |
| Case difference | Folded by `normalize_email` on both the roster key and the cell — `str.lower`, not `casefold` (19N Item 2). Applies to non-email reviewee identifiers too: `ANON-007` and `anon-007` are one key. | `email_identity.py:76` |
| A row naming an `inactive` roster member | **Accepted, silently.** The parser filters no status, and both callers pass every roster row (`assignments.list_reviewers` is session-scoped only). The saved relationship's own `status` comes from the CSV's `Status` column, not from the roster member. | `_coverage.py:236`, route `_setup_relationships.py:111` |
| `Status` accepted values | **Case-insensitive and whitespace-tolerant**: `_cell` strips, then `.strip().lower()`, then membership in `ROSTER_STATUSES`. `  ACTIVE  ` is accepted. Absent column or blank cell ⇒ `active`. | `:177`, `roster_status.py:22` |
| What the caller receives | `ParseResult(rows, issues, field_labels)` — the class at `csv_imports.py:36`, its `is_blocked` property at `:51`, neither in `relationships.py`. **Fatal** (no rows, returns early): decode failure, row-count issue, missing required column. **Per-row**: everything else — and the valid rows come back *alongside* the errors, which is where the parser's job ends. What the **import** does with a `ParseResult` carrying both is the callers' `is_blocked` gate, not the parser's: see row 4. | `csv_imports.py:36`, `relationships.py:76`/`:83`/`:92` |

## Divergences found and left standing

Rows 1–8 came from reading and running the code. **Rows 9 and 10 came
from a `spec-writer` verification pass over this register** — a checker
who did not write it, per `constitution.md` III. Row 9 is a live bug the
twelve-case probe missed, because no case combined two failure modes in
one file; row 10 is outside §3.2's boundary and inside its subject. Both
are why the pass was worth running: the pass confirmed all eight
original rows and still found two things.

| # | Kind | Where | What | What deciding it involves |
|---|---|---|---|---|
| 1 | spec-vs-code | §3.2 ¶1 | The signature reads `parse_relationship_csv(content, *, reviewer_emails, reviewee_identifiers)`. The code takes `reviewers: list[Reviewer]`, `reviewees: list[Reviewee]` — different names **and** different types, so a caller written to the spec raises `TypeError`. The prose beside it (*"resolves the two FK columns against the already-loaded session rosters"*) is **correct**. | Spec edit, no code question. The one row where the answer is obvious. |
| 2 | spec-vs-code | §3.2 Save ¶ | `save_relationships(db, session, rows)` omits three **required** keyword arguments: `user`, `filename`, `correlation_id`. Same failure mode as row 1 in a paragraph nobody had checked. | Spec edit, or state that the Save lines are deliberately abbreviated — which §3.1's `save_reviewers(db, session, rows)` would then also need. |
| 3 | spec-vs-code | §3.2 table, *Status value* | *"must be `active` / `inactive` (lowercase)"*. Case-insensitive in fact. A reader building a template would lower-case a column the importer never required lower-cased. | Spec edit (drop *lowercase*), or code edit to actually require it. The permissive read matches every other roster importer, so the spec is the likely wrong one. **§3.1 does not need the same edit** — an earlier draft of this row said it did; §3.1 says *"`active` / `inactive` only"* with no case qualifier at all (`csv_contracts.md:329`), so it is silent where §3.2 is wrong. |
| 4 | spec-silent | §3.2, the whole section | **The save policy is all-or-nothing and undocumented.** `Severity.error` is blocking and both callers gate on `result.is_blocked`, so **one bad row rejects the whole file**. Measured: a two-row CSV with one unknown reviewer returns `rows=1, blocked=True` and saves neither. **This is not a contradiction** — the table is headed *Per-row validation* over a *Detection* column, so *"per-row error"* describes where an error is attached, and the parser does exactly that. What §3.2 never states is what the import then does with a file containing one. | Spec edit: state the policy. **No behavior question is forced** — the section never promised partial import, so making the import partial would be a new product decision, not the resolution of a divergence. |
| 5 | spec-silent | §3.2 table, *Within-file duplicates* | Says the second occurrence is rejected; does not say that the **first is normally the one kept in `ParseResult`** (storage is a separate question — under row 4's gate a file with a duplicate stores nothing at all), that dedup happens **after** case-folded resolution (so `A@x` and `a@x` are one pair), or that the message names the prior row. *"Normally"* because of **row 9**, where the first row is kept by neither. | Spec edit. No code question in this row — row 9 carries it. |
| 6 | spec-silent | §3.2 table | **A row yields at most one issue.** Every check `continue`s, so a row with both cells blank reports only `ReviewerEmail`, and a row with an unknown reviewer *and* an unknown reviewee reports only the reviewer. An operator fixing errors may need several upload rounds. | Spec edit, or collect all of a row's issues before moving on. The second is a real UX improvement and a code change; it is not this item's. |
| 7 | spec-silent | §3.2, whole section | An `inactive` reviewer or reviewee **resolves and imports**. Nothing in §3.2 mentions roster status, and the relationship's own `status` is independent of the member's. | Needs a product answer before a spec one: is a pair naming a soft-deleted member meant to import? The Validate page is where the consequence would surface. |
| 8 | spec-silent | §3.2 ¶1 | The column is `RevieweeEmail` but it resolves against `reviewees.email_or_identifier`, and `normalize_email` lower-cases a **non-email** identifier. Deliberate reuse, undocumented; `spec/participant_model.md` is where non-email identifiers otherwise live — as *"confidential / opaque identifiers"*. An earlier draft of this row called that **W8**; the `W8` label belongs to `reviewees.unreachable_for_results` in `spec/validate_page.md`, not to that file. | Spec edit naming the column it really resolves against. No code question. |
| 9 | code-internal | `relationships.py:159` vs `:176` | **A rejected row still reserves its pair.** `seen_pairs[(reviewer_id, reviewee_id)] = index` is set **before** the `Status` check, so a first row with a bad `Status` is dropped *and* keeps the key. A later row naming the same pair with a valid status is then rejected as *"Duplicate pair … also on row 1"* — a misleading error on the row that was not the problem, and the pair reaches `ParseResult` from neither. Measured: two rows, first `Status=bogus`, second valid ⇒ `rows=0` and two issues. | A code fix — reserve the key only on a row that survives every check, i.e. move the `seen_pairs` write below the status check or after `parsed.append`. Then the second row imports and only the first errors. Not rung 1's to make. |
| 10 | spec-vs-code | §5 shared primitives, `csv_contracts.md:556` | The table says `_parse_email` is used on *"`ReviewerEmail` / `RevieweeEmail` in the Relationships importer"*. **It is not.** `relationships.py` neither imports nor calls it (0 occurrences); `_parse_email` runs only in `parse_reviewer_csv`, `parse_reviewee_csv` and `parse_observer_csv`. So **the Relationships importer performs no email-format validation at all** — a malformed cell fails FK resolution and is reported as *"Unknown reviewer"*, not as a bad address. §3.2 is consistent with the code here (it claims no format check); §5 is not. | Spec edit to §5, or a code edit adding the format check §5 already advertises. The second would change which error an operator sees for a typo. |

## Code observations — not §3.2's business

Found in the path while answering the above. Recorded so they are not
re-found; none is in this item's scope and none is a spec divergence.

- **A dead branch.** `relationships.py:178`'s `if status_raw == "":
  status_raw = "active"` cannot fire: the line above is
  `(_cell(raw, "Status") or "active")`, and `_cell` already returns
  `""` for blank, so the `or` has handled it.
- **A redundant clause.** `_quick_setup.py:562`'s
  `any(issue.severity == "error" for issue in result.issues)` is exactly
  `result.is_blocked`, which the same `if` already tests. It reads as a
  guard against `Severity` not being a string enum; it is one
  (`validation.py:9`), so the clause is redundant rather than dead.
- **The status parse is open-coded.** `csv_imports._parse_status` and
  `roster_status.normalise_status` both exist; the relationships parser
  inlines the fold instead. `normalise_status` *raises* where a parser
  must collect, so inlining is defensible — but `_parse_status` is the
  helper built for exactly this, and the roster parsers use it.

## What the checker corrected

The `spec-writer` pass confirmed rows 1–8 as substantively true and
corrected three asides in them, each now marked in the row: row 3's
claim that §3.1 needs the same edit (it does not — it is silent on
case, not wrong about it), row 8's attribution of the `W8` label to
`spec/participant_model.md` (it is `spec/validate_page.md`'s), and the
`is_blocked` citation, which pointed at the class rather than the
property.

It also read my instructions as saying this register held *"three
correct claims"* out of eight. That phrase was about **§3.2's** three
correct claims, listed below — not a confidence level on these rows.
Recorded because the ambiguity was mine.

## What §3.2 gets right

The *"already-loaded session rosters"* prose; the required and optional
column lists; and the `seed_display_fields_from_assignments` note,
including its explanation of the name — verified to read
`Relationship.tag_{1,2,3}`.

## How to re-run the probe

The twelve cases are reproducible from this file's answers: build two
`Reviewer` and two `Reviewee` objects (one of each inactive, one
reviewee with a non-email identifier), then call
`parse_relationship_csv` per row above and read `rows`, `is_blocked`
and each issue's `(row_number, field, message)`. No database is needed
— the parser touches none.

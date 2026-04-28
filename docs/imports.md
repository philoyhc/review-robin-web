# CSV imports

Operators populate a session's reviewers and reviewees by uploading
CSV files. Reviewer and reviewee imports are independent: a failed
reviewee parse cannot affect the reviewers table, and vice versa.

The implementation contract for this feature lives in
`guide/segment_06A.md`. This document is the operator-facing how-to.

## Reviewer CSV

Required columns: `ReviewerName`, `ReviewerEmail`.

Optional columns (used by the Segment 11 RuleBased assignment
generator): `ReviewerTag1`, `ReviewerTag2`, `ReviewerTag3`.

Any other columns are ignored.

```csv
ReviewerName,ReviewerEmail,ReviewerTag1,ReviewerTag2
Alice Example,alice@example.edu,senior,math
Bob Example,bob@example.edu,junior,physics
```

## Reviewee CSV

Required columns: `RevieweeName`, `RevieweeEmail`.

Optional columns: `PhotoLink` (a URL stored against the reviewee's
profile), `RevieweeTag1`, `RevieweeTag2`, `RevieweeTag3`.

`RevieweeEmail` accepts either an email address (validated) or a free
identifier without an `@` (stored as-is, e.g. a student number).

```csv
RevieweeName,RevieweeEmail,PhotoLink,RevieweeTag1
Carol Example,carol@example.edu,https://example.edu/c.jpg,cohort-A
Dan Example,dan-2026,,cohort-B
```

## Replace-with-confirmation behaviour

Each import is **all-or-nothing for that table**:

- If the CSV has any blocking errors, no rows are written and the form
  re-renders with the issue list.
- If the CSV is clean and the session has no reviewers (or reviewees)
  yet, the rows are saved and you are redirected to the session detail
  page.
- If the CSV is clean **and the session already has reviewers** (or
  reviewees), the form requires you to tick a "Yes, replace the
  existing N" checkbox before the upload is accepted. Without it, the
  POST is rejected with HTTP 400 and no rows are touched.

A successful import writes a `reviewers.imported` (or
`reviewees.imported`) audit event recording the old count, the new
count, and the original filename — useful if you ever need to confirm
which CSV produced which state.

## File limits

- **Encoding:** UTF-8. A leading byte-order mark (BOM) is tolerated;
  any other encoding produces a single blocking error.
- **Max file size:** 1 MiB.
- **Max row count:** 5000.

## Common errors

| Error | What to do |
|---|---|
| `Missing required column: ReviewerEmail` | Add the column to the CSV header. Column names are case-sensitive. |
| `ReviewerEmail 'foo@' is not a valid email address` | Email must look like `local@domain.tld`. Reviewees can use a non-email identifier (no `@` at all) instead. |
| `Duplicate ReviewerEmail 'x' (also on row 3)` | Each reviewer email must be unique within the file. Remove or merge the duplicate row. |
| `File too large (max 1024 KiB)` | Split the import into smaller batches, or remove unused columns. |
| HTTP 400 with no error list shown | The form is asking for the replace-confirmation checkbox; tick it and re-submit. |

## ManualAssignment CSV

Required columns: `ReviewerEmail`, `RevieweeEmail`. Both must already
exist in the session's reviewer / reviewee rosters — manual rows
**never** auto-create reviewers or reviewees.

Optional columns: `IncludeAssignment`, `AssignmentContext1`,
`AssignmentContext2`, `AssignmentContext3`. Any other columns are
ignored.

```csv
ReviewerEmail,RevieweeEmail,IncludeAssignment,AssignmentContext1
alice@example.edu,carol@example.edu,true,morning
bob@example.edu,carol@example.edu,false,afternoon
```

`IncludeAssignment` accepts (case-insensitive):

| Value | Parsed as |
|---|---|
| `true`, `yes`, `1` | `true` |
| `false`, `no`, `0` | `false` |
| empty / column absent | `true` (default) |
| anything else | blocking error |

`AssignmentContext1`/`2`/`3` are stored together in the assignment's
`context` JSON column under the keys `context_1`, `context_2`,
`context_3`. Used by Segment 11 RuleBased reviews and as a free-form
operator note in the meantime.

### Workflow

1. Open the **Assignments** page on a session that already has at
   least one reviewer and one reviewee.
2. Under **Manual CSV**, pick your file and click **Preview manual
   import**.
3. The preview shows total rows, an `include=false` count if any,
   and a table of the first 200 pairs (with truncation note if the
   file is longer). Blocking errors are listed inline; nothing is
   saved when errors are present.
4. To save, **re-upload the same file** in the Save card and (if the
   session already has assignments) tick the replace-confirm
   checkbox.

### Blocking errors

| Error | Cause |
|---|---|
| `Missing required column: …` | Add the column to the CSV header. Names are case-sensitive. |
| `Unknown reviewer: 'x' is not in this session's reviewer roster` | The reviewer email doesn't match any row in the session's reviewers table. Re-import reviewers or fix the CSV. |
| `Unknown reviewee: 'x' is not in this session's reviewee roster` | Same idea for reviewees. |
| `Duplicate assignment: 'a' -> 'b' (also on row N)` | Each `(reviewer, reviewee)` pair must be unique in the file. |
| `IncludeAssignment 'maybe' is not a recognised true/false value` | Use one of the documented truthy/falsy strings (or leave blank). |
| `File too large` / `Too many rows` | Same caps as roster CSVs (1 MiB / 5000 rows). |

## What's not implemented yet

- Excel upload (still CSV-only).
- Append / merge instead of replace.
- Importing custom instrument fields (Segment 8).
- RuleBased assignment generation (Segment 11).

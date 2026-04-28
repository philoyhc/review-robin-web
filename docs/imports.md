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

## What's not implemented yet

- Excel upload (still CSV-only).
- Append / merge instead of replace.
- Importing custom instrument fields (Segment 8).
- Importing assignments (Segment 7).

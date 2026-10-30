# Email Address Checker

> **Built so far:** segment U1 rung 3 built "Input", "Preview" and
> "Output". "Lookup", "Classification", "Duplicate groups" and "Access"
> are rung 4's and 5's; until then the design is
> `utilityapps/docs/email_address_checker_functional_spec_v0.1.md`
> ("the functional spec") §§5–7 and §10.

The checker's contract: what it reads, what it shows before checking, and
what it writes. The pages and where they mount are
`utilityapps/spec/utilities.md`. The code is
`utilityapps/email_check/csvio.py` (CSV in and out) and
`utilityapps/email_check/routes.py` (the pages).

## Input

A file is refused whole, back on the upload page with a `400` and one
line saying why, rather than checked in part:

| Refused when | Message names |
|---|---|
| No file was chosen | choosing one |
| Over 1 MiB (`MAX_BYTES`) | the limit in KiB |
| Not UTF-8 | saving as CSV UTF-8 |
| A NUL character | that it is not a CSV |
| Malformed quoting | the parser's reason |
| A cell over 131,072 characters, the `csv` module's limit, which is process-wide and left as RRW's importers rely on it | the limit |
| No header row, or a header of blank cells | the header |
| A header and no rows | the rows |
| Over 500 rows (`MAX_ROWS`) | the count and the limit |
| A row with more cells than the header | its line number |

- UTF-8 with or without a BOM; quoted cells may hold commas and line
  breaks.
- Blank lines before the header and after the last row are dropped. A
  blank line between rows **is a row**: a one-column file writes a blank
  cell that way, and it is kept as `INVALID_INPUT`.
- A row shorter than the header is padded with empty cells.
- **The address column** is the one headed `email`, matched trimmed and
  in any case. With none, or more than one, the operator chooses from
  the header.
- **The lookup key** is the cell stripped and lowercased. A cell that is
  blank, or is not one `@` between non-blank parts with a dot in the
  domain, has no key: it is `INVALID_INPUT` and never queried. The cell
  itself is never rewritten.

## Preview

Posting the file renders the preview: the file's name, the column choice,
and four counts:

| Count | Is |
|---|---|
| Rows | every data row |
| Addresses to check | rows with a key |
| Blank or not an address | rows without one |
| Repeats | rows whose key an earlier row already has; each key is looked up once |

Nothing is looked up yet. **Nothing is kept between steps:** the preview
page carries the file back as base64 in a hidden field, and choosing
another column posts it again with the column's index. The form accepts a
part up to twice `MAX_BYTES`, enough for the carried copy.

## Output

The result CSV is every input row, in order, with its cells as uploaded,
then nine result columns in this order (`RESULT_COLUMNS`): `status`,
`match_type`, `lookup_coverage`, `recommended_email`,
`user_principal_name`, `display_name`, `entra_object_id`,
`duplicate_account_group`, `notes`.

- A result column whose name the input already has (trimmed, any case)
  takes the prefix `check_`, repeated until it is unique.
- Every cell, input or result, header included, that starts with `=`,
  `+`, `-`, `@`, a tab or a carriage return gets a leading `'`, so a
  spreadsheet shows it as text rather than running it.
- Lines end `CRLF`.

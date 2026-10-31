# Email Address Checker

The design it follows is
`utilityapps/docs/email_address_checker_functional_spec_v0.1.md`
("the functional spec").

The checker's contract: what it reads, what it shows before checking, and
what it writes. The pages and where they mount are
`utilityapps/spec/utilities.md`. The code is
`utilityapps/email_check/csvio.py` (CSV in and out),
`utilityapps/email_check/check.py` (lookup and classification) and
`utilityapps/email_check/routes.py` (the pages). The directory is the
host's (`cordware/spec/identity.md` "Graph").

## Access

Every checker route is the platform super-admin's alone
(`Identity.is_super_admin`; functional spec §3). Anyone else signed in
gets a `403` page that says the tool is not available, with no invitation
to ask for access; nobody signed in gets the host's `401`. The Utilities
index and `/utilities/health` are not gated. Every checker page is
`Cache-Control: no-store`, except the `403` page, which holds no data.

## Input

A file is refused whole, back on the upload page with a `400` and one
line saying why, rather than checked in part:

| Refused when | Message names |
|---|---|
| No file was chosen | choosing one |
| The request says no size (no `Content-Length`) | uploading again |
| The request is over its limit, read from `Content-Length` before anything is parsed: the upload's whole multipart request over 1 MiB (`MAX_BYTES`), so a file a few hundred bytes under it is the largest taken; the preview's carried copy over 2 MiB | the limit in KiB |
| Over 1 MiB (`MAX_BYTES`) once read | the limit in KiB |
| Not UTF-8 | saving as CSV UTF-8 |
| A NUL character | that it is not a CSV |
| Malformed quoting | the parser's reason |
| A cell over 131,072 characters, the `csv` module's limit, which is process-wide and left as RRW's importers rely on it | the limit |
| No header row, or a header of blank cells | the header |
| A header and no rows | the rows |
| Over 500 rows (`MAX_ROWS`) | the count and the limit |
| A row with more cells than the header | its line number |
| The multipart body can't be read, or the carried copy isn't valid base64 | uploading again |

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
and four counts, in this order, so they read as a subtraction:

| Count | Is |
|---|---|
| Rows | every data row |
| Blank or not an address | rows without a key |
| Repeats | rows whose key an earlier row already has; each key is looked up once |
| Addresses to check | the distinct keys: rows less blanks less repeats, one lookup each |

Nothing is looked up yet. *Check addresses* posts the carried file and
the column to `/email-check/check`; it is disabled until a column is
chosen, and after the `503` below. Posting `/check` with no column renders
the preview again, checking nothing. A step reached by its address (`GET /email-check/preview` or
`/check`) redirects to the upload page. **Nothing is kept between steps:** the preview
page carries the file back as base64 in a hidden field, and choosing
another column posts it again with the column's index. That form is
URL-encoded, not multipart, so the carried copy is a field and never a
file part: Starlette spools a file part past 1 MiB to a temporary file,
which is why the upload's whole request is held under 1 MiB. A column
that is not a plain index (`isdecimal`), or is past the last header cell, is
ignored and the detected column stands.

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

## Lookup

Each distinct key is looked up once, at most four at a time
(`check.WORKERS`), through `cordware.graph`'s `find_users`: one query
matching `mail` or `userPrincipalName`. With fake auth on a local run
that is the fake directory. Alias lookup is not built, so every row's
`lookup_coverage` is `BASIC_ONLY`.

- **A time budget.** The check takes at most 120 s (`check.BUDGET`),
  under App Service's front-end limit. A lookup not finished by then is
  `ERROR` with kind `timeout`, and the rest still download.
- **A refused sign-in stops the run.** The first `unauthorized` or
  `forbidden` marks every lookup not yet started `ERROR` with the same
  kind, rather than sending one doomed request per address; those rows'
  `notes` say to sign out and in again.

With no delegated token the check stops before any lookup: the preview
returns with a `503` and says the directory can't be reached, and
nothing is checked.

## Classification

| `status` | `match_type` | When | Account columns |
|---|---|---|---|
| `OK` | `PRIMARY_MAIL` | One account; its `mail` is the key | all; `recommended_email` is the mail |
| `USE_PRIMARY` | `UPN` | One account; its UPN is the key and it has a mail | all; `recommended_email` is the mail |
| `FOUND_NO_PRIMARY` | `UPN` | One account; its UPN is the key and it has no mail | all but `recommended_email` |
| `NOT_FOUND` | `NONE` | No account | none |
| `AMBIGUOUS` | `MULTIPLE` | More than one account, or one that matches on neither field as compared here | none |
| `INVALID_INPUT` | `NONE` | No key; never looked up | none |
| `ERROR` | `NONE` | The lookup did not finish (any `GraphError`) | none; `notes` names the kind |

Comparison is on the lowercased key. An `ERROR` is never `NOT_FOUND`: the
directory could not be asked.

## Duplicate groups

Rows with one account (`OK`, `USE_PRIMARY`, `FOUND_NO_PRIMARY`) are
grouped by its object ID. An account reached by **two or more distinct
keys** gets a group number, from 1 in the order the file first names it,
in `duplicate_account_group`. Repeats of one key never make a group.

## Result

The result page shows the row count, the count per status, the number of
duplicate groups, a warning when any row is `ERROR` (to sign out and in
again after a refusal, to try later or in smaller parts after a
timeout, else to try later), and the alias caveat. The CSV is the page's download: a `data:` link holding it as
UTF-8 with a BOM, named `email-check-results-YYYYMMDD.csv`. The server
keeps no copy.

## Logging

Logger `utilityapps.email_check.routes`: one `email_check.completed`
record per check, carrying the row and lookup counts, the count per
status, the number of groups and the `GraphError` kinds seen. Never an
address, a name, an object ID or a cell.

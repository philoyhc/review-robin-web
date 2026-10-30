# U1 browser checks: the Email Address Checker

A walk through the Utilities index and the checker, end to end against
the fake directory (segment U1, closed 2026-10-30;
`utilityapps/guide/archive/segment_U1_email_checker.md`). The tests already check
what each page contains and every status; this is for copy, layout and
the flow. A change becomes a follow-up PR; a ruling is recorded here
beside its question. It outlived U1's close because the browser pass had
not happened yet: delete it once the pass is done and R1–R3 are ruled.

## Start the app

Utilities alone, as a super-admin (rung 5 gates the checker to one).
Change `C:\GitHub\review-robin-web` if your clone lives elsewhere; the
`Set-ExecutionPolicy` line is explained in
`residentialapps/guide/fake_ids.md`.

```powershell
Set-Location C:\GitHub\review-robin-web
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
$env:APP_ENV = "local"
$env:ALLOW_FAKE_AUTH = "true"
$env:FAKE_AUTH_EMAIL = "admin@example.edu"
$env:FAKE_AUTH_NAME = "Platform super-admin"
$env:FAKE_AUTH_SUPER_ADMIN = "true"
$env:CORDWARE_APPS = "utilities"
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/utilities/" } | Out-Null
uvicorn cordware.main:app --reload
```

The `pip install` line is needed once after this pull: it registers the
new `utilityapps` package. Stop with Ctrl+C; to clear the settings, use
`fake_ids.md`'s "Clearing the settings" block.

## A file to check

Save this as `sample.csv` (CSV UTF-8). Its addresses are the fake
directory's invented accounts (`cordware/graph.py`, `FAKE_USERS`), one per
status:

```
Name,Work email,Role
Jane Tan,jane.tan@example.edu,Reviewer
Jane Tan,e0123456@example.edu,Reviewer
Lab,lab01@example.edu,Observer
Office,office@example.edu,Reviewer
Arun Kumar,ARUN.KUMAR@example.edu,Reviewer
Arun Kumar,arun.kumar@example.edu,Observer
Nobody,nobody@example.edu,Reviewer
Busy,throttled@example.edu,Reviewer
Blank,,Reviewer
```

## The steps

Check each at desktop width, in light and dark (the system setting:
these pages follow it). Mobile is not a priority for this utility
(author, 2026-10-30): a narrow window need only stay usable (spec §3),
so one glance at a 390 px phone is enough.

| # | Step | Look for |
|---|---|---|
| 1 | `/utilities/` | One card, *Email Address Checker*; *All applications* returns to the host's list |
| 2 | The upload page | The purpose line, the limits, the four "does and doesn't" lines |
| 3 | Upload `sample.csv` | The preview: no `email` column, so *Choose a column…*; pick *Work email*, then *Use this column*: 9 rows, 8 to check, 1 blank, 1 repeat (Arun's two spellings); *Check addresses* now enabled |
| 4 | *Check addresses* | Counts: `OK` 3, `USE_PRIMARY` 1, `FOUND_NO_PRIMARY` 1, `NOT_FOUND` 1, `AMBIGUOUS` 1, `INVALID_INPUT` 1, `ERROR` 1; one account under two addresses (Jane); the red line about the unfinished lookup |
| 5 | *Download checked CSV* | Opens in Excel with the input's columns first, then the nine result columns; Jane's two rows share `duplicate_account_group` 1; Arun's two do not form a group |
| 6 | A bad file (a `.txt` renamed `.csv`, or one with only a header) | Back on the upload page with one red line saying why |
| 7 | Not a super-admin: restart with `$env:FAKE_AUTH_SUPER_ADMIN = "false"` | Every checker page says *Not available*; the index still lists the tool |

## Rulings to give while looking

- **R1. Status names on screen** (5): the CSV's codes (`USE_PRIMARY`),
  as now, or plain labels with the code beside them?
- **R2. Per-row results on screen** (5): the spec asks for counts and a
  download only (§11). Is that enough, or should the rows needing action
  (`USE_PRIMARY`, `AMBIGUOUS`, `ERROR`) be listed too?
- **R3. The no-directory message** (4): is "sign out and in again" the
  right first step to offer?

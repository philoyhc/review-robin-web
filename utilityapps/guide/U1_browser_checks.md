# U1 browser checks: the Email Address Checker's pages

A walk through the Utilities index and the checker's three pages, built
as placeholders by segment U1 rung 2
(`utilityapps/guide/segment_U1_email_checker.md`). Copy, layout and the
flow are what to judge: every control is disabled and the counts are
samples. The tests already check what each page contains. A change
becomes a follow-up commit before rung 3; a ruling goes in the plan's
open questions. Delete this file when U1 closes.

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

## The pages

Check each at desktop width, in light and dark (the system setting:
these pages follow it). Mobile is not a priority for this utility
(author, 2026-10-30): a narrow window need only stay usable (spec §3),
so one glance at a 390 px phone is enough.

| # | Page | Address | Look for |
|---|---|---|---|
| 1 | Utilities index | `/utilities/` | One card, *Email Address Checker*, linking to the checker; *All applications* returns to the host's list |
| 2 | Upload | `/utilities/email-check/` | The purpose line; the file limits; the four "does and doesn't" lines read as true and enough |
| 3 | Preview | `/utilities/email-check/preview` | The column choice (the sample file has no `email` column); the four counts; *Check addresses* and *Start over* |
| 4 | Preview, no directory | `/utilities/email-check/preview?state=no-graph` | The amber message, and whether it tells an operator what to do |
| 5 | Result | `/utilities/email-check/result` | The seven statuses with their meanings; the duplicate-account line; the alias caveat; *Download checked CSV* |

The upload page links to 3–5 at its foot, as placeholder links that go
when the pages are wired.

## Rulings to give while looking

- **R1. Status names on screen** (5): the CSV's codes (`USE_PRIMARY`),
  as now, or plain labels with the code beside them?
- **R2. Per-row results on screen** (5): the spec asks for counts and a
  download only (§11). Is that enough, or should the rows needing action
  (`USE_PRIMARY`, `AMBIGUOUS`, `ERROR`) be listed too?
- **R3. The no-directory message** (4): is "sign out and in again" the
  right first step to offer?

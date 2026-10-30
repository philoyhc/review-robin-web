# Fake identities: Support Logs

Copy-and-paste PowerShell blocks for running Support Logs locally as each
sample viewer of segment 1D item 1. Use them with
`residentialapps/guide/1D_browser_checks.md`. Each block stands alone: it
activates the virtualenv, sets fake auth for that shell only, opens the
browser on the viewer's page a few seconds after the app starts, and runs
the app.

- **Run from the repository root.** The first line moves there. Change
  `C:\GitHub\review-robin-web` if your clone lives elsewhere.
- **The `Set-ExecutionPolicy` line** lets this window run `Activate.ps1`,
  which Windows PowerShell blocks by default ("running scripts is
  disabled on this system"). It lasts until the window closes and needs no
  admin rights. To lift the block for good instead, run
  `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`
  once (`docs/local_setup.md`, "Windows-specific gotchas").
- **Stop with Ctrl+C**, then paste the next block. Closing the shell drops
  the settings, which never touch `.env`.
- **Who a page is drawn for is the `?as=` in the address**, not the fake
  account. The account gives the top bar its name and gets you past
  sign-in. So one running app serves every viewer: the **Sample viewer**
  card switches between them without a restart. A block per viewer sets
  both, so the name in the top bar matches the viewer.
- Fake auth works only with `APP_ENV=local`, and the host refuses to start
  otherwise. Never set it on a deployment.

| Viewer | Holds | Lands on |
|---|---|---|
| Daniel Koh | Frontline | Home, the frontline dashboard |
| Priya Raman | Frontline, Safety-flag recipient | Home, with every active safety flag |
| Sam Lee | Senior identifiable, Safety-flag recipient | Overview |
| Hui Min Goh | Safety-flag recipient | Home, the flags only |
| Marcus Tan | Consultation check | Consultation check |
| Kenneth Lau | Other Staff view: aggregate | Overview, counts only |
| Siti Rahman | Other Staff view: identifiable | Overview, read-only |
| Nadia Hassan | Consultation check, Other Staff view: identifiable | Home, listing Overview and Consultation check |
| Rachel Yeo | Sys admin | Sys admin › Access |
| Platform super-admin | Super-admin | Sys admin › Access, with Sys admin grants |
| Wei Jie Ong | RF, no Support Logs access | the 403 page |

## Daniel Koh

RF: Frontline. Lands on Home, the frontline dashboard.

```powershell
Set-Location C:\GitHub\review-robin-web
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "local"
$env:ALLOW_FAKE_AUTH = "true"
$env:FAKE_AUTH_EMAIL = "daniel.koh@example.edu"
$env:FAKE_AUTH_NAME = "Daniel Koh"
$env:FAKE_AUTH_SUPER_ADMIN = "false"
Remove-Item Env:CORDWARE_APPS -ErrorAction SilentlyContinue
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/supportlogs/" } | Out-Null
uvicorn cordware.main:app --reload
```

## Priya Raman

RSLM: Frontline, Safety-flag recipient. Lands on Home, with every active safety flag.

```powershell
Set-Location C:\GitHub\review-robin-web
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "local"
$env:ALLOW_FAKE_AUTH = "true"
$env:FAKE_AUTH_EMAIL = "priya.raman@example.edu"
$env:FAKE_AUTH_NAME = "Priya Raman"
$env:FAKE_AUTH_SUPER_ADMIN = "false"
Remove-Item Env:CORDWARE_APPS -ErrorAction SilentlyContinue
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/supportlogs/?as=Priya%20Raman" } | Out-Null
uvicorn cordware.main:app --reload
```

## Sam Lee

Master: Senior identifiable, Safety-flag recipient. Lands on Overview.

```powershell
Set-Location C:\GitHub\review-robin-web
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "local"
$env:ALLOW_FAKE_AUTH = "true"
$env:FAKE_AUTH_EMAIL = "sam.lee@example.edu"
$env:FAKE_AUTH_NAME = "Sam Lee"
$env:FAKE_AUTH_SUPER_ADMIN = "false"
Remove-Item Env:CORDWARE_APPS -ErrorAction SilentlyContinue
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/supportlogs/?as=Sam%20Lee" } | Out-Null
uvicorn cordware.main:app --reload
```

## Hui Min Goh

Exec: Safety-flag recipient. Lands on Home, the flags only.

```powershell
Set-Location C:\GitHub\review-robin-web
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "local"
$env:ALLOW_FAKE_AUTH = "true"
$env:FAKE_AUTH_EMAIL = "huimin.goh@example.edu"
$env:FAKE_AUTH_NAME = "Hui Min Goh"
$env:FAKE_AUTH_SUPER_ADMIN = "false"
Remove-Item Env:CORDWARE_APPS -ErrorAction SilentlyContinue
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/supportlogs/?as=Hui%20Min%20Goh" } | Out-Null
uvicorn cordware.main:app --reload
```

## Marcus Tan

RSLM: Consultation check. Lands on Consultation check.

```powershell
Set-Location C:\GitHub\review-robin-web
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "local"
$env:ALLOW_FAKE_AUTH = "true"
$env:FAKE_AUTH_EMAIL = "marcus.tan@example.edu"
$env:FAKE_AUTH_NAME = "Marcus Tan"
$env:FAKE_AUTH_SUPER_ADMIN = "false"
Remove-Item Env:CORDWARE_APPS -ErrorAction SilentlyContinue
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/supportlogs/?as=Marcus%20Tan" } | Out-Null
uvicorn cordware.main:app --reload
```

## Kenneth Lau

RF: Other Staff view: aggregate. Lands on Overview, counts only.

```powershell
Set-Location C:\GitHub\review-robin-web
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "local"
$env:ALLOW_FAKE_AUTH = "true"
$env:FAKE_AUTH_EMAIL = "kenneth.lau@example.edu"
$env:FAKE_AUTH_NAME = "Kenneth Lau"
$env:FAKE_AUTH_SUPER_ADMIN = "false"
Remove-Item Env:CORDWARE_APPS -ErrorAction SilentlyContinue
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/supportlogs/?as=Kenneth%20Lau" } | Out-Null
uvicorn cordware.main:app --reload
```

## Siti Rahman

RF: Other Staff view: identifiable. Lands on Overview, read-only.

```powershell
Set-Location C:\GitHub\review-robin-web
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "local"
$env:ALLOW_FAKE_AUTH = "true"
$env:FAKE_AUTH_EMAIL = "siti.rahman@example.edu"
$env:FAKE_AUTH_NAME = "Siti Rahman"
$env:FAKE_AUTH_SUPER_ADMIN = "false"
Remove-Item Env:CORDWARE_APPS -ErrorAction SilentlyContinue
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/supportlogs/?as=Siti%20Rahman" } | Out-Null
uvicorn cordware.main:app --reload
```

## Nadia Hassan

RSLM: Consultation check, Other Staff view: identifiable. Lands on Home, listing Overview and Consultation check.

```powershell
Set-Location C:\GitHub\review-robin-web
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "local"
$env:ALLOW_FAKE_AUTH = "true"
$env:FAKE_AUTH_EMAIL = "nadia.hassan@example.edu"
$env:FAKE_AUTH_NAME = "Nadia Hassan"
$env:FAKE_AUTH_SUPER_ADMIN = "false"
Remove-Item Env:CORDWARE_APPS -ErrorAction SilentlyContinue
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/supportlogs/?as=Nadia%20Hassan" } | Out-Null
uvicorn cordware.main:app --reload
```

## Rachel Yeo

Admin: Sys admin. Lands on Sys admin › Access.

```powershell
Set-Location C:\GitHub\review-robin-web
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "local"
$env:ALLOW_FAKE_AUTH = "true"
$env:FAKE_AUTH_EMAIL = "rachel.yeo@example.edu"
$env:FAKE_AUTH_NAME = "Rachel Yeo"
$env:FAKE_AUTH_SUPER_ADMIN = "false"
Remove-Item Env:CORDWARE_APPS -ErrorAction SilentlyContinue
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/supportlogs/?as=Rachel%20Yeo" } | Out-Null
uvicorn cordware.main:app --reload
```

## Platform super-admin

Super-admin. Lands on Sys admin › Access, with Sys admin grants.

```powershell
Set-Location C:\GitHub\review-robin-web
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "local"
$env:ALLOW_FAKE_AUTH = "true"
$env:FAKE_AUTH_EMAIL = "operator@example.edu"
$env:FAKE_AUTH_NAME = "Local Super-admin"
$env:FAKE_AUTH_SUPER_ADMIN = "true"
Remove-Item Env:CORDWARE_APPS -ErrorAction SilentlyContinue
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/supportlogs/?as=Platform%20super-admin" } | Out-Null
uvicorn cordware.main:app --reload
```

## Wei Jie Ong

RF, no Support Logs access. Lands on the 403 page.

```powershell
Set-Location C:\GitHub\review-robin-web
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "local"
$env:ALLOW_FAKE_AUTH = "true"
$env:FAKE_AUTH_EMAIL = "weijie.ong@example.edu"
$env:FAKE_AUTH_NAME = "Wei Jie Ong"
$env:FAKE_AUTH_SUPER_ADMIN = "false"
Remove-Item Env:CORDWARE_APPS -ErrorAction SilentlyContinue
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/supportlogs/?as=Wei%20Jie%20Ong" } | Out-Null
uvicorn cordware.main:app --reload
```

## Clearing the settings

To go back to `.env`'s values in the same shell:

```powershell
Remove-Item Env:APP_ENV, Env:ALLOW_FAKE_AUTH, Env:FAKE_AUTH_EMAIL, Env:FAKE_AUTH_NAME, Env:FAKE_AUTH_SUPER_ADMIN -ErrorAction SilentlyContinue
```

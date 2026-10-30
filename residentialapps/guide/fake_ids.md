# Fake identities: Residential Apps

Copy-and-paste PowerShell blocks for running Residential Apps locally as
each sample viewer. This file holds every command; the browser walkthroughs hold the checks
and point here:

| Walkthrough | Its blocks |
|---|---|
| `residentialapps/guide/1B_browser_checks.md` | Rosters and setup, Sys admin (1B) |
| `residentialapps/guide/1C_browser_checks.md` | RA Leave (1C) |
| `residentialapps/guide/1D_browser_checks.md` | Support Logs (1D) |

Each block stands alone. It:

1. activates the virtualenv;
2. sets fake auth for that shell only;
3. opens the browser on the viewer's page a few seconds after the app
   starts;
4. runs the app.

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
  sign-in. So one running app serves every viewer: each page's viewer
  chips or card switch between them without a restart. A block per viewer
  sets both, so the name in the top bar matches the viewer.
- Fake auth works only with `APP_ENV=local`, and the host refuses to start
  otherwise. Never set it on a deployment.

## Once, after a pull

The virtualenv is set up once as in `docs/local_setup.md` §G. After pulling
new work, refresh the dependencies only if they changed:

```powershell
Set-Location C:\GitHub\review-robin-web
git pull
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## In the browser

- **Phone width:** open DevTools (F12), toggle the device toolbar
  (Ctrl+Shift+M) and pick a 390 px phone; set 360 px from the width box.
- **Dark mode:** the Light/Dark toggle at the top right. The choice is kept
  across the host's applications.
- **A kept sort or column choice** lives in this browser's storage. To start
  clean, open DevTools › Application › Local storage and clear the site.

## Rosters and setup, Sys admin (1B)

These pages have no viewer switch; they are drawn for a sys admin. The
landing at `/residentialops/` switches viewer with its chips. Sys admin
says "You see this read-only" unless the fake account is the super-admin.

### The landing (Chloe Lim)

The landing, whose chips switch between Chloe Lim, Daniel Koh, Priya
Raman, Hui Min Goh, Rachel Yeo and Sam Lee.

```powershell
Set-Location C:\GitHub\review-robin-web
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "local"
$env:ALLOW_FAKE_AUTH = "true"
$env:FAKE_AUTH_EMAIL = "chloe.lim@example.edu"
$env:FAKE_AUTH_NAME = "Chloe Lim"
$env:FAKE_AUTH_SUPER_ADMIN = "false"
Remove-Item Env:CORDWARE_APPS -ErrorAction SilentlyContinue
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/residentialops/" } | Out-Null
uvicorn cordware.main:app --reload
```

### Rosters and setup (Rachel Yeo)

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
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/residentialops/rosters/" } | Out-Null
uvicorn cordware.main:app --reload
```

### Sys admin as a sys admin (Rachel Yeo)

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
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/residentialops/sys-admin/" } | Out-Null
uvicorn cordware.main:app --reload
```

### Sys admin as the super-admin

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
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/residentialops/sys-admin/" } | Out-Null
uvicorn cordware.main:app --reload
```

## RA Leave (1C)

The RA pages and the staff pages each switch viewer with chips under the
title. RA Leave admin has no switch; reach it from Rachel Yeo's or Sam Lee's
landing card.

| Viewer | Side | Shows |
|---|---|---|
| Chloe Lim | RA | cover asked of her, a draft, an email not sent |
| Hana Ito | RA | her cover declined: name new cover |
| Ethan Wong | RA | awaiting cover confirmation; a withdrawn application; a draft |
| Gwen Ho | RA | an appeal with the Master |
| Lucas Teo | RA | extra leave granted |
| Faris Iskandar | RA | a rejected application |
| Maya Seah | RA | an appeal the Master refused |
| Kai Ng | RA | approved leave cancelled; invited to appeal (preview appeals by invitation) |
| Daniel Koh | staff | RF, first approver for Cypress A 04-12 |
| Priya Raman | staff | RSLM, no decisions under the policy |
| Rachel Yeo | staff | Residential Admin, final approver |
| Sam Lee | staff | Master, decides appeals |
| Hui Min Goh | staff | Residential Executive, oversees no RA |

### Chloe Lim (RA)

Cover asked of her, a draft, an email not sent.

```powershell
Set-Location C:\GitHub\review-robin-web
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "local"
$env:ALLOW_FAKE_AUTH = "true"
$env:FAKE_AUTH_EMAIL = "chloe.lim@example.edu"
$env:FAKE_AUTH_NAME = "Chloe Lim"
$env:FAKE_AUTH_SUPER_ADMIN = "false"
Remove-Item Env:CORDWARE_APPS -ErrorAction SilentlyContinue
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/residentialops/ra-leave/" } | Out-Null
uvicorn cordware.main:app --reload
```

### Hana Ito (RA)

Her cover declined: name new cover.

```powershell
Set-Location C:\GitHub\review-robin-web
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "local"
$env:ALLOW_FAKE_AUTH = "true"
$env:FAKE_AUTH_EMAIL = "hana.ito@example.edu"
$env:FAKE_AUTH_NAME = "Hana Ito"
$env:FAKE_AUTH_SUPER_ADMIN = "false"
Remove-Item Env:CORDWARE_APPS -ErrorAction SilentlyContinue
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/residentialops/ra-leave/?as=Hana%20Ito" } | Out-Null
uvicorn cordware.main:app --reload
```

### Ethan Wong (RA)

Awaiting cover confirmation; a withdrawn application; a draft.

```powershell
Set-Location C:\GitHub\review-robin-web
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "local"
$env:ALLOW_FAKE_AUTH = "true"
$env:FAKE_AUTH_EMAIL = "ethan.wong@example.edu"
$env:FAKE_AUTH_NAME = "Ethan Wong"
$env:FAKE_AUTH_SUPER_ADMIN = "false"
Remove-Item Env:CORDWARE_APPS -ErrorAction SilentlyContinue
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/residentialops/ra-leave/?as=Ethan%20Wong" } | Out-Null
uvicorn cordware.main:app --reload
```

### Gwen Ho (RA)

An appeal with the Master.

```powershell
Set-Location C:\GitHub\review-robin-web
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "local"
$env:ALLOW_FAKE_AUTH = "true"
$env:FAKE_AUTH_EMAIL = "gwen.ho@example.edu"
$env:FAKE_AUTH_NAME = "Gwen Ho"
$env:FAKE_AUTH_SUPER_ADMIN = "false"
Remove-Item Env:CORDWARE_APPS -ErrorAction SilentlyContinue
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/residentialops/ra-leave/?as=Gwen%20Ho" } | Out-Null
uvicorn cordware.main:app --reload
```

### Lucas Teo (RA)

Extra leave granted.

```powershell
Set-Location C:\GitHub\review-robin-web
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "local"
$env:ALLOW_FAKE_AUTH = "true"
$env:FAKE_AUTH_EMAIL = "lucas.teo@example.edu"
$env:FAKE_AUTH_NAME = "Lucas Teo"
$env:FAKE_AUTH_SUPER_ADMIN = "false"
Remove-Item Env:CORDWARE_APPS -ErrorAction SilentlyContinue
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/residentialops/ra-leave/?as=Lucas%20Teo" } | Out-Null
uvicorn cordware.main:app --reload
```

### Faris Iskandar (RA)

A rejected application.

```powershell
Set-Location C:\GitHub\review-robin-web
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "local"
$env:ALLOW_FAKE_AUTH = "true"
$env:FAKE_AUTH_EMAIL = "faris.iskandar@example.edu"
$env:FAKE_AUTH_NAME = "Faris Iskandar"
$env:FAKE_AUTH_SUPER_ADMIN = "false"
Remove-Item Env:CORDWARE_APPS -ErrorAction SilentlyContinue
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/residentialops/ra-leave/?as=Faris%20Iskandar" } | Out-Null
uvicorn cordware.main:app --reload
```

### Maya Seah (RA)

An appeal the Master refused.

```powershell
Set-Location C:\GitHub\review-robin-web
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "local"
$env:ALLOW_FAKE_AUTH = "true"
$env:FAKE_AUTH_EMAIL = "maya.seah@example.edu"
$env:FAKE_AUTH_NAME = "Maya Seah"
$env:FAKE_AUTH_SUPER_ADMIN = "false"
Remove-Item Env:CORDWARE_APPS -ErrorAction SilentlyContinue
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/residentialops/ra-leave/?as=Maya%20Seah" } | Out-Null
uvicorn cordware.main:app --reload
```

### Kai Ng (RA)

Approved leave cancelled; invited to appeal (preview appeals by invitation).

```powershell
Set-Location C:\GitHub\review-robin-web
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "local"
$env:ALLOW_FAKE_AUTH = "true"
$env:FAKE_AUTH_EMAIL = "kai.ng@example.edu"
$env:FAKE_AUTH_NAME = "Kai Ng"
$env:FAKE_AUTH_SUPER_ADMIN = "false"
Remove-Item Env:CORDWARE_APPS -ErrorAction SilentlyContinue
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/residentialops/ra-leave/?as=Kai%20Ng" } | Out-Null
uvicorn cordware.main:app --reload
```

### Daniel Koh (staff)

RF, first approver for Cypress A 04-12.

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
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/residentialops/ra-leave/staff/" } | Out-Null
uvicorn cordware.main:app --reload
```

### Priya Raman (staff)

RSLM, no decisions under the policy.

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
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/residentialops/ra-leave/staff/?as=Priya%20Raman" } | Out-Null
uvicorn cordware.main:app --reload
```

### Rachel Yeo (staff)

Residential Admin, final approver.

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
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/residentialops/ra-leave/staff/?as=Rachel%20Yeo" } | Out-Null
uvicorn cordware.main:app --reload
```

### Sam Lee (staff)

Master, decides appeals.

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
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/residentialops/ra-leave/staff/?as=Sam%20Lee" } | Out-Null
uvicorn cordware.main:app --reload
```

### Hui Min Goh (staff)

Residential Executive, oversees no RA.

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
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/residentialops/ra-leave/staff/?as=Hui%20Min%20Goh" } | Out-Null
uvicorn cordware.main:app --reload
```

### RA Leave admin (Rachel Yeo)

The admin pages, drawn for a sys admin.

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
Start-Job { Start-Sleep -Seconds 4; Start-Process "http://127.0.0.1:8000/residentialops/ra-leave/admin/" } | Out-Null
uvicorn cordware.main:app --reload
```

## Support Logs (1D)

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

### Feedback session: one laptop, testers' phones

For a feedback session (`residentialapps/guide/1D_browser_checks.md` §0):
the app runs on your laptop and each tester opens it on their own phone,
on the same Wi-Fi. Nothing to install on theirs.

- **Only Support Logs is served** (`CORDWARE_APPS = "supportlogs"`):
  Review Robin and Residential Operations answer 404, so nothing but
  sample data is on the network.
- **The first time**, Windows Firewall asks whether to allow Python:
  allow it on **private** networks only.
- **The block prints the address** testers type, one line per network
  your laptop is on; use the Wi-Fi one (often `192.168…` or `10…`). If
  unsure, `ipconfig` lists it under "Wireless LAN adapter Wi-Fi", IPv4
  Address.
- **If phones cannot connect**, the Wi-Fi keeps devices apart, as campus
  networks often do: put the laptop and the phones on your phone's
  hotspot instead, and run the block again for the new address.
- **Each tester picks who they are** on the page's **Sample viewer** card,
  or opens the address with `?as=Daniel%20Koh` (frontline) or
  `?as=Sam%20Lee` (senior) on the end. The name in the top bar stays
  yours: it is the fake account, not the viewer.
- **Stop with Ctrl+C when the session ends.** While it runs, anyone on
  that network can open it.

```powershell
Set-Location C:\GitHub\review-robin-web
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "local"
$env:ALLOW_FAKE_AUTH = "true"
$env:FAKE_AUTH_EMAIL = "feedback@example.edu"
$env:FAKE_AUTH_NAME = "Feedback session"
$env:FAKE_AUTH_SUPER_ADMIN = "false"
$env:CORDWARE_APPS = "supportlogs"
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } | ForEach-Object { "Testers open: http://$($_.IPAddress):8000/supportlogs/   ($($_.InterfaceAlias))" }
uvicorn cordware.main:app --host 0.0.0.0 --port 8000
```

### Daniel Koh

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

### Priya Raman

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

### Sam Lee

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

### Hui Min Goh

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

### Marcus Tan

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

### Kenneth Lau

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

### Siti Rahman

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

### Nadia Hassan

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

### Rachel Yeo

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

### Platform super-admin

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

### Wei Jie Ong

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
Remove-Item Env:APP_ENV, Env:ALLOW_FAKE_AUTH, Env:FAKE_AUTH_EMAIL, Env:FAKE_AUTH_NAME, Env:FAKE_AUTH_SUPER_ADMIN, Env:CORDWARE_APPS -ErrorAction SilentlyContinue
```

# CLI setup for the Azure + GitHub runbook

Companion to [`azure_github_setup.md`](azure_github_setup.md).
Covers the CLIs you need on your workstation to execute the
runbook, the one-time auth steps, and a set of tests that
prove you can reach the RRW GitHub repo and Azure before you
start provisioning anything.

If you already have `az`, `gh`, `psql`, and `git` working from
your shell of choice and can push to `philoyhc/review-robin-web`
plus `az account show` returns your institutional tenant, skip
straight to the runbook.

The two appendices at the end cover **setting WSL2 up from a
clean Windows 11 install** and a **connectivity test set**
you can run before Phase 1 to catch config problems while
they're cheap.

---

## 1. Required CLIs

| CLI | What it drives | Notes |
|---|---|---|
| **`az`** (Azure CLI) | Every Phase 1 resource create, RBAC assignments, App Service config, Postgres firewall + admin bootstrap, Key Vault put/get, Application Gateway config, Application Insights provisioning. The workhorse. | Pin to `>= 2.60` so `az login --scope` and the current `webapp identity assign` shape work. |
| **`gh`** (GitHub CLI) | Creating repo environments (`production` / `staging`), setting environment variables (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, etc.), attaching required reviewers on `production`, tailing workflow runs, filing PRs. | Alternative to clicking around the GitHub Settings UI; more auditable. |
| **`psql`** (Postgres client) | Phase 2 — connecting as admin to run `CREATE DATABASE rrw` + `CREATE ROLE rrw_app` + grants, plus ad-hoc troubleshooting. | Version 16+ to match the Flexible Server. |
| **`git`** | Repo operations, branch push, tag-based release triggers if you go that route. | |

## 2. Useful adjuncts

| CLI | When it helps |
|---|---|
| **`jq`** | Parsing `az ... -o json` output in shell scripts (e.g. extracting App Service outbound IPs for the Postgres firewall). |
| **`openssl`** | Generating the `rrw_app` DB role password before storing in Key Vault (`openssl rand -base64 24`). |
| **`curl`** | Smoke-testing `/health`, the Easy Auth login redirect, and the App Gateway probe path end-to-end. |
| **`docker`** | Running local Postgres for Phase 6 migration rehearsal before touching NPRD (matches `docs/local_setup.md`). |
| **`bicep`** or **`terraform`** | Only if you want Phase 1 provisioning codified rather than clicked. Not required for v1; useful once NPRD stabilises and you want PRD to be a deterministic replay. `bicep` ships bundled with modern `az`. |
| **Python 3.12 + `pip`** | On your box only for local test runs before pushing; CI has its own Python. |

Not needed (worth calling out because they're the obvious
guesses): `kubectl` (RRW is App Service, not AKS), `node` / `npm`
(no JS build step by design), `azd` (its opinionated scaffold
doesn't match RRW's hand-rolled workflow — use plain `az`
instead), `func` (Functions Core Tools; only if you actually
build a function, which Phase 1 defers).

---

## 3. Shell choice on Windows

| Shell | Verdict |
|---|---|
| **cmd** | Everything runs, but painful — poor quoting, no pipeline objects, weak scripting. Fine for one-off `az` and `gh` invocations, awful for anything scripted. |
| **Windows PowerShell 5.1** (the one shipped with Windows) | **Avoid.** Old TLS support has bitten Azure users; JSON handling is dated. |
| **PowerShell 7+** | Genuinely good. Cross-platform, proper objects, built-in `ConvertFrom-Json` replaces `jq` for many cases, decent quoting. Install from `winget install Microsoft.PowerShell`. |
| **WSL2** (Ubuntu) | What most Azure + GitHub power-users on Windows actually run. Gives you a real bash + all these tools + interop with Windows files. Sample commands from the runbook and from most Azure docs paste in verbatim. **Recommended** for anyone new to this class of work. Set-up steps in Appendix A. |
| **Git Bash** | Bundled with Git for Windows. Bash-like enough for most snippets; some Azure CLI quoting oddities compared to Ubuntu. Fine for git + basic `az`, marginal beyond that. |

## 4. Where shell syntax differs

Three pain points to know if you're translating snippets between
bash and PowerShell.

### Setting environment variables

```bash
export PGPASSWORD='secret'        # bash / WSL / Git Bash
```

```
set PGPASSWORD=secret              :: cmd (no quotes, no export)
$env:PGPASSWORD = 'secret'         # PowerShell
```

### Parsing JSON output from `az`

The `az ... -o json | jq '.foo'` pattern from Azure docs doesn't
translate. In PowerShell:

```powershell
az webapp show --name app-nrrw-nprd --resource-group rg-nrrw-nprd -o json |
    ConvertFrom-Json |
    Select-Object -ExpandProperty defaultHostName
```

`jq` also works on Windows if you prefer bash-style pipelines —
just install it (`winget install jqlang.jq`).

### Quoting `az` args with embedded JSON

The single most common friction point when following Azure docs
written in bash. A Linux one-liner like:

```bash
az webapp config appsettings set --settings '[{"name":"FOO","value":"bar"}]'
```

needs backtick-escaping or double-double-quotes in cmd /
PowerShell, but works fine in WSL as-is. Where possible use
`--settings @file.json` to sidestep the quoting entirely.

---

## 5. One-time auth setup

Do these once per workstation before starting the runbook, in
this order. All examples use bash-style syntax; substitute per
§4 if you're on PowerShell.

```bash
# Azure
az login                                                # browser or device-code flow
az account set --subscription "<subscription-name-or-id>"
az account show --query "{tenantId:tenantId, id:id, user:user.name}" -o table

# GitHub
gh auth login                                           # HTTPS + browser
gh auth status                                          # confirm scope includes repo + workflow

# Postgres (later, after Phase 2 provisions the server)
# ~/.pgpass keeps the password out of shell history:
#   psql-nrrw-nprd.postgres.database.azure.com:5432:*:<admin>:<password>
# chmod 0600 ~/.pgpass
```

Two auth gotchas the runbook doesn't call out but bite in
practice:

- **`az` tenant confusion.** If you have personal + institutional
  Microsoft accounts, `az login --tenant <institutional-tenant-id>`
  forces the right one. Otherwise a `Contributor` role assignment
  on a resource group can silently target the wrong tenant's
  copy of you.
- **`gh` scope for environment secrets.** `gh` defaults don't
  include `admin:repo_hook` or environment-secret write. If a
  Phase 4 "set environment variables" step fails with 403, run
  `gh auth refresh -s workflow,admin:repo_hook`.

---

## Appendix A — WSL2 setup on Windows 11

The fast path from a clean Windows 11 install to a WSL2 Ubuntu
shell ready for the runbook. Copy-paste-friendly. Steps that
need Windows admin rights are called out.

### A.1 Install WSL2 + Ubuntu

Windows 11 ships with a modern `wsl` binary that installs the
kernel + a distribution in one command. Run in an **elevated
PowerShell** (right-click Start → "Terminal (Admin)"):

```powershell
wsl --install
```

That installs the WSL2 kernel + Ubuntu (default distribution)
and enables the Virtual Machine Platform feature. **Reboot** when
prompted.

After the reboot, an Ubuntu terminal opens automatically the
first time and asks you to create a Linux username + password.
Keep the username simple (lowercase, no spaces); the password
is only used inside Ubuntu for `sudo`, so it doesn't need to
match your Windows password.

Verify:

```powershell
wsl --status                     # in PowerShell — should show "Default Distribution: Ubuntu"
wsl --list --verbose             # should show Ubuntu STATE=Running VERSION=2
```

If `wsl --status` reports version 1 for Ubuntu, run
`wsl --set-version Ubuntu 2` (elevated).

### A.2 Update the Ubuntu base image

Inside the Ubuntu terminal:

```bash
sudo apt update && sudo apt upgrade -y
```

Takes a few minutes on first run.

### A.3 Install the required CLIs

```bash
# git — usually pre-installed on Ubuntu; verify
sudo apt install -y git

# GitHub CLI (gh)
(type -p wget >/dev/null || (sudo apt update && sudo apt install wget -y)) \
  && sudo mkdir -p -m 755 /etc/apt/keyrings \
  && wget -qO- https://cli.github.com/packages/githubcli-archive-keyring.gpg \
     | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
  && sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
     | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
  && sudo apt update \
  && sudo apt install -y gh

# Azure CLI (az) — Microsoft's install script
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Postgres client (psql) — version 16 to match Flexible Server.
# Ubuntu's default postgresql-client trails the current major
# version; PostgreSQL's official apt repo pins 16 reliably.
sudo apt install -y curl ca-certificates
sudo install -d /usr/share/postgresql-common/pgdg
sudo curl -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc --fail \
    https://www.postgresql.org/media/keys/ACCC4CF8.asc
sudo sh -c 'echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
sudo apt update
sudo apt install -y postgresql-client-16

# Useful adjuncts
sudo apt install -y jq openssl curl unzip

# Python 3.12 (for local test runs; optional but useful)
sudo apt install -y python3 python3-pip python3-venv
```

### A.4 Verify versions

```bash
git --version                    # expect >= 2.40
gh --version                     # expect >= 2.40
az --version                     # expect >= 2.60 (top line)
psql --version                   # expect 16.x
jq --version
python3 --version                # expect 3.12.x on recent Ubuntu; 3.10.x is fine, CI is 3.12
```

If any of these come back older than the "expect" line, upgrade
before proceeding — several runbook commands use features that
land in the versions above.

### A.5 Log into GitHub + configure git identity

`gh auth setup-git` registers the GitHub CLI as git's credential
helper — after this, `git push` uses the token `gh auth login`
issued, and there's no password prompt on any repo operation.

```bash
gh auth login              # browser + device code
gh auth setup-git          # register gh as the git credential helper

git config --global user.name "philoyhc"
git config --global user.email "philoyhc@users.noreply.github.com"
```

The `@users.noreply.github.com` address is GitHub's privacy
form — commit metadata stays associated with the account
without exposing a real inbox in the repo history.

### A.6 Verify the identity is set

Empty-commit-then-reset — the commit uses the just-configured
name / email, and the reset rewinds immediately, so nothing
lands in the branch history.

```bash
cd ~/src/review-robin-web   # or any existing clone
git commit --allow-empty -m "identity test" && git reset --hard HEAD~1
```

If `gh auth setup-git` didn't run or the identity isn't set,
`git commit` errors with `Please tell me who you are`; if the
token is missing scope, a subsequent `git push` returns 403.

### A.7 (Optional) Move your RRW clone into WSL

WSL2 can read `/mnt/c/Users/...` transparently, but I/O is
noticeably faster when the repo lives inside the WSL filesystem:

```bash
mkdir -p ~/src && cd ~/src
git clone https://github.com/philoyhc/review-robin-web.git
cd review-robin-web
```

Use `code .` from inside the WSL shell to open VS Code with the
WSL Remote extension (it auto-installs on first use).

### A.8 Windows Terminal (nice-to-have)

If it's not already default, install Windows Terminal
(`winget install Microsoft.WindowsTerminal`) and set its default
profile to Ubuntu — it's a substantially better terminal than
the legacy `wsl.exe` console window.

---

## Appendix B — Connectivity tests

Run this test set inside WSL (or PowerShell) after Appendix A
but before Phase 1 of the runbook. Each test proves one
specific reachability + credential story; a failure tells you
exactly which piece is missing.

Every command should complete without prompting for
credentials — if any of them opens a browser or asks for
input, note it and re-run non-interactively before moving on.

### B.1 Outbound HTTPS baseline

```bash
curl -sS -I https://github.com                    | head -1
curl -sS -I https://api.github.com                | head -1
curl -sS -I https://management.azure.com          | head -1
curl -sS -I https://login.microsoftonline.com     | head -1
```

Expected: each returns `HTTP/2 200`, `HTTP/2 301`, or similar.
If any returns "Connection refused" or hangs, your corporate
proxy is blocking outbound HTTPS to that endpoint — you'll need
IT to allow-list before continuing.

### B.2 GitHub — RRW repo reachable

```bash
gh auth status                                    # signed in?
gh api user                                       # returns your GitHub identity
git ls-remote https://github.com/philoyhc/review-robin-web.git HEAD
gh repo view philoyhc/review-robin-web --json name,defaultBranchRef
```

Expected: `gh auth status` shows an active login, `gh api user`
returns your username, `git ls-remote` returns the current
`main` HEAD commit hash, `gh repo view` returns the repo name
and default branch (`main`).

### B.3 GitHub — can you push?

Prove you have write access without pushing anything meaningful:

```bash
cd ~/src/review-robin-web                        # or wherever you cloned
git fetch origin main
git checkout -b test/cli-setup-$(date +%s) origin/main
git commit --allow-empty -m "connectivity test — safe to delete"
git push -u origin HEAD                          # should succeed
# clean up:
git push origin --delete "$(git rev-parse --abbrev-ref HEAD)"
git checkout main
git branch -D "$(git rev-parse --abbrev-ref @{-1})" 2>/dev/null || true
```

Expected: `git push` succeeds without prompting for credentials
(GitHub CLI installed the git credential helper on `gh auth
login`), and the delete succeeds. If push fails with 403, run
`gh auth refresh -s workflow,admin:repo_hook`.

### B.4 GitHub — workflow-scope credential

Phase 4 needs write access to repo secrets + environments.
Confirm the scope up front:

```bash
gh auth status                                   # look for "workflow" in the scope list
gh api /repos/philoyhc/review-robin-web/actions/secrets \
    -q '.total_count'                            # returns a number without 403
```

If the second command errors with "Resource not accessible by
integration" or `HTTP 403`, run `gh auth refresh -s workflow,admin:repo_hook`
and retry.

### B.5 Azure — signed in to the right tenant + subscription

```bash
az account show \
    --query "{tenantId:tenantId, sub:id, subName:name, user:user.name}" \
    -o table
az account list --query "[].{name:name, id:id, tenant:tenantId, default:isDefault}" -o table
```

Expected: `az account show` returns the **institutional** tenant
ID (not a personal MSA tenant) and the subscription IT gave
you. If it shows a personal tenant, run
`az login --tenant <institutional-tenant-id>` and
`az account set --subscription "<name>"`.

### B.6 Azure — role check

You need at minimum `Contributor` on the target resource groups
to run the runbook, plus `User Access Administrator` (or IT
assistance) to make role assignments in Phase 4.

```bash
az role assignment list \
    --assignee "$(az ad signed-in-user show --query id -o tsv)" \
    --query "[].{role:roleDefinitionName, scope:scope}" \
    -o table
```

Expected: at least one row with `Contributor` (or higher) at
subscription or the intended resource group scope. If the list
is empty, IT hasn't granted your account access to the target
subscription yet — surface that before starting Phase 1.

### B.7 Azure — can you provision?

The cheapest "can you actually create things" test — provision
an empty resource group in the runbook's naming convention,
then immediately delete it:

```bash
az group create --name rg-nrrw-clitest --location southeastasia \
    --tags project=nrrw env=clitest
az group show --name rg-nrrw-clitest --query provisioningState -o tsv
az group delete --name rg-nrrw-clitest --yes --no-wait
```

Expected: `az group create` succeeds, `az group show` returns
`Succeeded`, `az group delete` returns without error. An empty
RG costs nothing; the `--no-wait` cleanup finishes in the
background.

If `az group create` errors with `AuthorizationFailed`, your
scope from B.6 doesn't include the region or your role is
narrower than `Contributor`. If it errors with `PolicyViolation`,
IT has an Azure Policy on the subscription (naming, region,
tags) that this test tripped — either adjust the test to match
policy or ask IT which naming/region is enforced.

### B.8 Postgres client — sanity only (no server yet)

Before Phase 2 you can only check the client:

```bash
psql --version                                   # expect 16.x
```

Once Phase 2 provisions the server, the real reachability test
is:

```bash
psql "host=psql-nrrw-nprd.postgres.database.azure.com \
      user=<admin> dbname=postgres sslmode=require" -c "SELECT 1;"
```

Expected: returns `?column?` / `1` after prompting for password
(or auto-reading `~/.pgpass`). SSL failures mean the client
version is too old to negotiate — install `postgresql-client-16`
per Appendix A.3.

### B.9 Current dev slot connectivity (free-tier personal Azure)

Parallel to B.5–B.8 but pointed at the **existing** developer-
owned dev slot (`rg-review-robin-web-dev` / `app-review-robin-web-dev`
/ its Burstable Postgres server). Useful to run alongside B.5–B.8
before starting the runbook, so you catch any residual
credential drift on the current setup — or to confirm the dev
slot is still healthy after you've switched shells / machines /
WSL distributions.

If you switched Azure tenants in B.5 (`az login --tenant
<institutional-id>`) you need to switch **back** to your personal
Azure tenant to run these tests, then switch again for the
institutional runbook. `az account list -o table` shows both.

Substitute `<pg-server>` with the actual Flexible Server name
(check `az postgres flexible-server list --resource-group
rg-review-robin-web-dev --query "[].name" -o tsv` if you don't
remember it).

**B.9.1 Dev-slot resource group + web app reachable.**

```bash
az group show --name rg-review-robin-web-dev \
    --query "{name:name, state:properties.provisioningState}" -o table
az webapp show --name app-review-robin-web-dev \
    --resource-group rg-review-robin-web-dev \
    --query "{name:name, state:state, host:defaultHostName, tls:httpsOnly}" -o table
```

Expected: RG shows `Succeeded`; web app shows `Running` +
default host = `app-review-robin-web-dev-a5c9f3gpfudaambf.southeastasia-01.azurewebsites.net`
(or the current hostname) + `httpsOnly: true`. If `az group
show` errors with `AuthorizationFailed` or `ResourceGroupNotFound`,
you're pointed at the wrong tenant/subscription — see the note
above.

**B.9.2 Dev-slot `/health` reachable anonymously.**

`/health` is the one route excluded from Easy Auth (per
`docs/security_posture.md`), so it should return 200 with a
JSON body without triggering a login redirect.

```bash
DEV_HOST=$(az webapp show --name app-review-robin-web-dev \
    --resource-group rg-review-robin-web-dev \
    --query defaultHostName -o tsv)
curl -sS "https://${DEV_HOST}/health"
echo   # trailing newline
```

Expected: `{"status":"ok"}` returned in one line, HTTP 200. If
you get an HTML login page (302 to `login.microsoftonline.com`),
`/health` isn't in the Easy Auth exclude list — check the App
Service *Authentication* blade. If you get 503, the app is
booting or has crashed — check `az webapp log tail --name
app-review-robin-web-dev --resource-group rg-review-robin-web-dev`.

**B.9.3 Dev-slot Postgres server reachable via `az`.**

Confirms the server exists in the tenant/subscription you're
pointed at, and prints the connection metadata `psql` needs.

```bash
az postgres flexible-server list \
    --resource-group rg-review-robin-web-dev \
    --query "[].{name:name, host:fullyQualifiedDomainName, state:state, version:version}" \
    -o table
```

Expected: one row with `state=Ready` + Postgres `version=16`.
The `host` value is what goes into the `psql` connection string
below. If the list is empty, either you're in the wrong
subscription or the server has been deleted — surface either
before starting Phase 2.

**B.9.4 Your public IP is in the Postgres firewall allow-list.**

The dev slot uses public access with a firewall allow-list;
your workstation's public IP needs to be on it for `psql` from
your machine to succeed.

```bash
az postgres flexible-server firewall-rule list \
    --resource-group rg-review-robin-web-dev \
    --server-name "${PG_SERVER}" \
    --query "[].{name:name, start:startIpAddress, end:endIpAddress}" \
    -o table
```

Expected: at least one rule whose `[startIpAddress, endIpAddress]`
range covers `${MY_IP}`. If not, add one (name it after the
context so it's revocable):

```bash
az postgres flexible-server firewall-rule create \
    --resource-group rg-review-robin-web-dev \
    --server-name "${PG_SERVER}" \
    --name "home-$(date +%Y%m%d)" \
    --start-ip-address "${MY_IP}" \
    --end-ip-address "${MY_IP}"
```

Remove it when you're done (`firewall-rule delete` with the
same `--rule-name`). Office networks often block outbound 5432
regardless — if you can't add the rule or `psql` still hangs
after adding one, fall back to Azure Cloud Shell (which reaches
the server via the "Allow Azure services" rule).

**B.9.5 Dev-slot `psql` connection as admin.**

```bash
psql "host=<pg-server>.postgres.database.azure.com port=5432 \
      dbname=rrw user=<admin> sslmode=require" -c "SELECT 1;"
```

Expected: prompts for password (or auto-reads `~/.pgpass`),
returns `?column?` / `1`. Handshake failures usually mean B.9.4
hasn't been resolved.

**B.9.6 Dev-slot `psql` connection as `rrw_app` (least
privilege).**

Parallel to B.9.5 but confirms the least-privilege role the
running app uses actually works. If this connects but B.9.5
doesn't, you have the passwords swapped.

```bash
psql "host=<pg-server>.postgres.database.azure.com port=5432 \
      dbname=rrw user=rrw_app sslmode=require" \
     -c "SELECT current_user, count(*) FROM users;"
```

Expected: `current_user = rrw_app`, `count` = whatever the row
count is. If you get `permission denied for table users`, the
`GRANT` from Phase 2 of the runbook was skipped on this server
— see `docs/deployment_dev.md` §Database configuration for the
grant statements.

### B.10 If any test fails

- **Corporate proxy blocking (B.1).** Ask IT to allow-list
  `github.com`, `api.github.com`, `management.azure.com`, and
  `login.microsoftonline.com` from your workstation.
- **GitHub auth issues (B.2, B.3, B.4).** `gh auth logout` then
  `gh auth login` with the `repo`, `workflow`, and
  `admin:repo_hook` scopes.
- **Wrong Azure tenant (B.5).** `az login --tenant <id>` +
  `az account set --subscription "<name>"`.
- **Insufficient Azure role (B.6, B.7).** Not a self-service
  fix — ask IT for `Contributor` at the subscription scope, or
  scoped to the resource groups the runbook creates.
- **`psql` too old (B.8).** `sudo apt install postgresql-client-16`;
  on non-Ubuntu distros, follow the equivalent for
  postgresql.org's official repo.

Once B.1 through B.8 pass (institutional side) — plus B.9 if
you're maintaining the personal dev slot in parallel — you're
ready to work through [`azure_github_setup.md`](azure_github_setup.md)
Phase 1 onwards.

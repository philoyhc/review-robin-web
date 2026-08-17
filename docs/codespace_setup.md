# Testing Review Robin Web from a GitHub Codespace

**Short answer: yes.** RRW's test suite and local dev server need **no
external services** — the tests run against in-memory SQLite and the app
runs against a local SQLite file with a fake-auth fallback. That makes a
Codespace a first-class place to run the suite and click through the app.

The one thing a Codespace *can't* do is exercise **real Entra / Easy Auth
sign-in** — those identity headers are injected by the Azure platform, so
end-to-end auth still needs the Azure dev slot ([§6](#6-what-a-codespace-cant-test)).

This guide is Codespaces-specific. For the shared details (repo layout,
`.env` fields, database tasks, troubleshooting) it defers to
[`local_setup.md`](local_setup.md) rather than repeating them.

---

## 1. What you can and can't test

| Task | In a Codespace? |
|---|---|
| Full `pytest` suite (business logic, routes, services) | ✅ Yes — SQLite in-memory, no setup |
| Alembic migration round-trip on SQLite | ✅ Yes |
| Run the app + click through operator / reviewer surfaces | ✅ Yes — fake auth + forwarded port |
| `ruff` lint | ✅ Yes |
| Postgres-dialect parity (what `ci-postgres` catches) | ⚙️ Optional — add a Postgres service ([§7](#7-optional-postgres-dialect-parity-in-the-codespace)) |
| Real Entra / Easy Auth sign-in, redirect flows, tenant allowlist | ❌ No — needs the Azure dev slot |

---

## 2. Start a Codespace

From the repo on GitHub: **Code ▸ Codespaces ▸ Create codespace on
`main`** (or on your feature branch). This boots a cloud VM with the repo
cloned. The default image includes **Python 3.12** (the project requires
≥3.12) plus Git and the GitHub CLI.

There is **no `.devcontainer/` in the repo yet**, so the first-run setup
below is manual. [§8](#8-optional-add-a-devcontainer-for-one-click-boot)
gives a ready-to-drop-in `devcontainer.json` if you'd rather have the
Codespace boot fully provisioned.

---

## 3. First-time setup (manual)

Run these in the Codespace terminal:

```bash
# 1. Virtual environment (the image ships Python 3.12)
python3.12 -m venv .venv
source .venv/bin/activate

# 2. Runtime + dev dependencies
python -m pip install --upgrade pip
pip install -e .[dev]

# 3. Local environment variables (fake auth is already set in the template)
cp .env.example .env

# 4. Build the local SQLite database
alembic upgrade head
```

`.env.example` already ships with `ALLOW_FAKE_AUTH=true` and a fake
operator identity, so no editing is needed to get a signed-in operator
locally. `DATABASE_URL` is left unset, so the app uses the default
`sqlite:///./review_robin_web.db` (a gitignored file — delete it any time
to start fresh).

> **`.env` stays local.** It's gitignored; never commit it. Setting
> `ALLOW_FAKE_AUTH=true` is safe in a Codespace (a private dev
> environment) but must never reach a deployed App Service.

---

## 4. Run the test suite

```bash
pytest -n auto        # full suite, ~35s (pytest-xdist parallelism)
```

The suite builds its schema straight from the ORM metadata into an
**in-memory SQLite** engine (`tests/conftest.py`), so there's nothing to
provision. Other useful runs:

```bash
pytest tests/integration/test_X.py            # one file
pytest tests/integration/test_X.py::test_name # one test
pytest -k "expression"                         # match by name
ruff check .                                   # lint
```

---

## 5. Run the app and open it in the browser

```bash
uvicorn app.main:app --reload
```

Codespaces auto-detects the listening port (**8000**) and forwards it —
a toast offers **Open in Browser**, and the **Ports** tab lists the
forwarded URL (an `*.app.github.dev` address, private to your GitHub
account by default).

Because `ALLOW_FAKE_AUTH=true`, you land signed in as the fake
`operator@example.edu`, which carries **operator + sys-admin +
super-admin** rights locally (`fake_auth_operator` /
`fake_auth_sys_admin` / `fake_auth_super_admin` default to `True` in
`app/config.py`; super-admin is Segment 18S). Quick surface check on the
forwarded URL:

| Path | Expected |
|---|---|
| `/health` | `200` — `{"status": "ok"}` |
| `/` | `200` — service metadata JSON |
| `/auth/me` | `200` — fake user JSON (`is_fake: true`) |
| `/auth/me/debug` | `200` — HTML with a "fake auth" pill |
| `/docs` | FastAPI Swagger UI |

> **If the port isn't auto-forwarded**, bind explicitly:
> `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`, then add
> port 8000 manually in the **Ports** tab. A `401` on `/auth/me` means
> `.env` is missing or `ALLOW_FAKE_AUTH` isn't `true` — see
> `local_setup.md` §8.

---

## 6. What a Codespace can't test

Real authentication. In deployed environments, Azure App Service **Easy
Auth** performs the Entra sign-in and injects `X-MS-CLIENT-PRINCIPAL*`
headers that `app/auth/identity.py` parses. A Codespace has no Easy Auth
in front of it, so it only ever sees the **fake** user. That means these
are **not** exercisable in a Codespace and still need the **Azure dev
slot**:

- genuine tenant sign-in and the 302 → Microsoft redirect flow,
- the real operator/sys-admin allowlist bootstrap on first real sign-in
  (`OPERATOR_EMAILS` / `SYS_ADMIN_EMAILS`),
- anything that reads real Entra claims (`/auth/me/debug` claims list).

Everything the automated suite covers — routes, services, lifecycle
transitions, audit emission, migrations — is fully testable in the
Codespace. This mirrors the project workflow: the container is the pre-PR
gate (`pytest` + `ruff`), and end-to-end auth verification happens on the
dev slot after deploy.

---

## 7. Optional: Postgres dialect parity in the Codespace

By default the Codespace tests against **SQLite**, exactly like the
primary CI job. The separate `ci-postgres` job already round-trips Alembic
and runs the full suite against `postgres:16` on every PR, so you don't
*need* Postgres locally. But if you want to reproduce a dialect-only issue
(the `BOOLEAN DEFAULT 1`, `WHERE bool_col = 1`, FK-drop-order, or
index-name-mismatch traps called out in `CLAUDE.md`), point the suite at a
Postgres container:

```bash
# Start a throwaway Postgres 16 (Docker is available in the default image)
docker run -d --name rrw-pg -e POSTGRES_PASSWORD=pw -p 5432:5432 postgres:16

# Run the suite against it (conftest honours TEST_DATABASE_URL)
export TEST_DATABASE_URL="postgresql+psycopg://postgres:pw@localhost:5432/postgres"
pytest -n auto
```

The `engine` fixture in `tests/conftest.py` honours `TEST_DATABASE_URL` /
`DATABASE_URL`, so the same suite covers both dialects. Unset the variable
to go back to SQLite.

---

## 8. Optional: add a devcontainer for one-click boot

Dropping a `.devcontainer/devcontainer.json` in the repo makes a Codespace
boot fully provisioned — Python 3.12, dependencies installed, `.env`
seeded, port 8000 forwarded — so you can `pytest` or `uvicorn`
immediately. A minimal one:

```jsonc
{
  "name": "review-robin-web",
  "image": "mcr.microsoft.com/devcontainers/python:3.12",
  "postCreateCommand": "python -m pip install --upgrade pip && pip install -e .[dev] && cp -n .env.example .env && alembic upgrade head",
  "forwardPorts": [8000],
  "portsAttributes": {
    "8000": { "label": "RRW app", "onAutoForward": "notify" }
  },
  "customizations": {
    "vscode": {
      "extensions": ["ms-python.python", "charliermarsh.ruff"]
    }
  }
}
```

With this in place, a fresh Codespace runs the `postCreateCommand` on
first boot and is ready to test with no manual steps. (Adding it is a
project decision — this doc lays out both the manual path and the
devcontainer so you can pick.)

---

## 9. Where to look next

- [`local_setup.md`](local_setup.md) — the full developer setup: repo
  layout, every `.env` field, database tasks, and a troubleshooting
  section this guide defers to.
- [`authentication.md`](authentication.md) — how Easy Auth identity is
  parsed and why fake auth exists.
- [`database.md`](database.md) — migration conventions and the
  cross-dialect type policy behind §7.
- `CLAUDE.md` / `AGENTS.md` — project conventions and the common-commands
  reference.

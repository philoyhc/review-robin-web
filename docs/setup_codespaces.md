# Running RRW in a GitHub Codespace, from a browser

Step by step, using only github.com in a browser: a laptop, or a tablet
or phone. `.devcontainer/devcontainer.json` does the setup, so there is
nothing to install and nothing to type to see the app. What the container
does, and what a Codespace can't do (real Entra sign-in), is in
`docs/local_setup.md` §9.

## First time

1. **Open the repository** on github.com and sign in. On a tablet, if the
   green **Code** button or the **Codespaces** tab is missing, switch the
   browser to its desktop site.
2. **Create the Codespace.** **Code ▸ Codespaces ▸ Create codespace on
   `main`**. To try a branch or a PR instead, pick it in the branch menu
   first, or use **Code ▸ Codespaces** on the PR's own page.
3. **Wait for the first build.** VS Code opens in the browser and a
   terminal shows the install and the database migration. This happens
   once per Codespace.
4. **Open the app.** When port 8000 forwards, the app opens in a new tab.
   If the browser blocked the tab, open the **Ports** panel (bottom of the
   editor) and click the globe icon on the `RRW app` row. You are signed in
   as the fake operator, `operator@example.edu`.

**Keep port 8000 private**, the default. Fake auth makes anyone who can
reach the URL a super-admin.

## Coming back

- Open **github.com/codespaces** and click the Codespace. It restarts,
  migrates, and serves again; open the app from the **Ports** panel.
- **To look at another branch:** in the terminal,
  `git fetch && git switch <branch>`. The server reloads on its own; run
  `alembic upgrade head` if the branch adds a migration.
- **After `.devcontainer/` changes:** Command Palette (F1 or Ctrl+Shift+P)
  ▸ **Codespaces: Rebuild Container**.

## When something is off

- **The app does not answer.** Read `/tmp/rrw-uvicorn.log` in the
  terminal, or restart the server there:
  `pkill -f "uvicorn app.main" ; uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.
- **Run the tests:** `pytest -n auto`. `tests/browser/` skips unless you
  run `python -m playwright install --with-deps chromium` first.

## Stopping and cost

A Codespace stops by itself after a spell of inactivity (30 minutes by
default) and is deleted after some weeks unused. To stop it now, use
**github.com/codespaces ▸ ⋯ ▸ Stop codespace**; delete it from the same
menu when you are done with it. A personal account gets a free monthly
allowance of Codespace hours and storage; **github.com/settings/billing**
shows what is used.

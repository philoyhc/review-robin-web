# tools/

Standalone developer / design tooling — scripts that operate *on* the repo
but aren't part of the app or its test suite.

| Path | What |
|---|---|
| `theme_preview.gen.py` + `theme_preview.html` | **Theme-preview harness.** `theme_preview.gen.py` lifts `app/web/templates/base.html`'s real `<style>` (including the light + dark palette) and renders a component gallery + colour-token swatch grid into the standalone `theme_preview.html` — **open it in a browser** (no server) and use the toolbar to compare Light / Dark. A faithful preview of the shipped themes, kept as a design surface for future theme work (e.g. a sepia theme or a theme customizer): the `EXTRA_THEME_CSS` hook + the script's docstring show how to prototype a new theme before porting it into `base.html`. Regenerate after any `base.html` style change: `python3 tools/theme_preview.gen.py`. Not wired into the app. |

# tools/

Standalone developer / design tooling — scripts that operate *on* the repo
but aren't part of the app or its test suite.

| Path | What |
|---|---|
| `theme_preview.gen.py` + `theme_preview.html` | **Theme-preview harness (read-only).** Lifts `app/web/templates/base.html`'s real `<style>` (light + dark palette) and renders a component gallery + colour-token swatch grid into `theme_preview.html` — **open it in a browser** (no server); the toolbar flips Light / Dark. A faithful preview of the shipped themes. Regenerate after any `base.html` style change: `python3 tools/theme_preview.gen.py`. |
| `theme_customizer.gen.py` + `theme_customizer.html` | **Theme customizer (designer).** Segment 19C Item 5, Plan A of `guide/theme_customizer.md`. Same gallery, but every colour token is **editable** with live repaint. Design a light + dark palette (edit each separately via the toggle), then **Export JSON** — a coding agent ports its flat `tokens` map 1:1 into `base.html`'s `:root` blocks. Controls: Load defaults / Re-read `base.html`… (file-picker) / Save-as named library (localStorage) / Delete / Export + Import JSON. Slice 1 (manual editor); contrast badges + seed-and-derive land in later slices. `python3 tools/theme_customizer.gen.py`. |
| `_harness_common.py` | Shared helpers for the two generators above — the `base.html` `<style>` lift, the `:root` / `:root[data-theme="dark"]` token parse, the harness CSS, and the component-gallery markup. Not a generator; imported by both. |

#!/usr/bin/env python3
"""Generate guide/theme_preview.html — a standalone dark-mode design harness.

Lifts the REAL `<style>` block from app/web/templates/base.html (so the
component CSS is faithful, not a hand-copy), appends a DRAFT dark palette under
the three guarded blocks from guide/ux_theme.md, and renders a component gallery
plus a colour-token swatch grid. Open the output in a browser; the toolbar flips
`data-theme` on <html> so you can compare System / Light / Dark live.

This is a design tool for Segment 19C Item 2 (W4). It is NOT production code and
NOT wired into the app. When the dark palette is finalised here, port the token
values into base.html's `:root` guarded blocks (that is W4 proper). Regenerate
after any base.html style change:  python3 guide/theme_preview.gen.py

The DRAFT dark values below are a first cut — tune them, then re-run.
"""
import re
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = ROOT / "app/web/templates/base.html"
OUT = ROOT / "guide/theme_preview.html"

src = BASE.read_text(encoding="utf-8")

# 1. Lift the <style>…</style> body verbatim (Jinja-free — verified).
m = re.search(r"<style>(.*?)</style>", src, re.DOTALL)
if not m:
    raise SystemExit("Could not find <style> block in base.html")
base_css = m.group(1)

# 2. Parse the light token list (name -> light value) from :root for the swatch grid.
tokens = []
for line in base_css.splitlines():
    tm = re.match(r"\s*(--[a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8});", line)
    if tm:
        tokens.append((tm.group(1), tm.group(2)))
colour_tokens = [(n, v) for n, v in tokens]  # every token in :root is a colour here

# 3. DRAFT dark palette (W4 starter). Tune these. Tokens named *-dark / *-strong /
#    *-text that are DARK text on a LIGHT surface invert to LIGHT text on a dark
#    surface; *-bg tints become dark solids; core accents brighten for contrast.
DARK = {
    # Neutrals
    "--bg-page": "#0f141b",
    "--bg-card": "#1a212e",
    "--text-on-accent": "#ffffff",
    "--bg-muted": "#232c3b",
    "--border-subtle": "#2b3547",
    "--border-default": "#3a465c",
    "--neutral-marker": "#3a465c",
    "--text-primary": "#e6eaf2",
    "--text-secondary": "#a9b4c6",
    "--text-muted": "#6f7b8e",
    # Blue
    "--accent-blue": "#4b8bf5",
    "--accent-blue-bg": "#16324f",
    "--accent-blue-bg-soft": "#12283f",
    "--accent-blue-bg-faint": "#0e1c2c",
    "--accent-blue-light": "#60a5fa",
    "--accent-blue-dark": "#93c5fd",
    "--accent-blue-marker": "#3b82f6",
    "--accent-blue-strong": "#93c5fd",
    # Green
    "--accent-green": "#34d399",
    "--accent-green-bg": "#0f3d2e",
    "--accent-green-marker": "#065f46",
    "--accent-green-text": "#6ee7b7",
    "--accent-green-bg-faint": "#0c2419",
    # Amber
    "--accent-amber": "#fbbf24",
    "--accent-amber-bg": "#3a2c0a",
    "--accent-amber-bg-mid": "#4a3a10",
    "--accent-amber-dark": "#fcd34d",
    "--accent-amber-border": "#b45309",
    # Red
    "--accent-red": "#f87171",
    "--accent-red-bg": "#3d1a1a",
    "--accent-red-soft": "#ef4444",
    "--accent-red-strong": "#f87171",
    "--accent-red-text": "#fca5a5",
    # Violet / sky
    "--accent-violet-bg": "#2e2250",
    "--accent-violet-text": "#c4b5fd",
    "--accent-sky-bg": "#0c2f42",
    "--accent-sky-text": "#7dd3fc",
    # Soft inline-error
    "--danger-bg": "#3d1a1a",
    "--danger-border": "#7f2a2a",
    "--danger-text": "#fca5a5",
    # Instrument tints (dark, subtly hued)
    "--instrument-tint-1": "#0e1a24",
    "--instrument-tint-2": "#0e1f18",
    "--instrument-tint-3": "#191527",
    "--instrument-tint-4": "#241a10",
    "--instrument-tint-5": "#241318",
    "--instrument-tint-6": "#221d0e",
    # Misc
    "--tab-marker-color": "#3b82f6",
}
missing = [n for n, _ in colour_tokens if n not in DARK]
if missing:
    raise SystemExit(f"DRAFT dark palette missing tokens: {missing}")

dark_decls = "\n".join(f"      {n}: {v};" for n, v in DARK.items())
dark_block = f"""
    /* ================= DRAFT DARK PALETTE (W4 starter — TUNE ME) =================
       First-cut dark values. Not yet ported to base.html. Edit here, re-run
       guide/theme_preview.gen.py, refresh the browser. When happy, copy these
       into base.html under the same three guarded blocks. */
    @media (prefers-color-scheme: dark) {{
      :root:not([data-theme="light"]) {{
{dark_decls}
      }}
    }}
    :root[data-theme="dark"] {{
{dark_decls}
    }}
"""

# 4. Harness-only chrome CSS (toolbar + gallery layout + a stand-in for
#    .save-error-banner, which lives in the instruments template not base.html).
harness_css = """
    /* ---- harness-only (not part of the app) ---- */
    body.ui-v2 { margin: 0; }
    .ph-toolbar {
      position: sticky; top: 0; z-index: 50;
      display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
      padding: 10px 20px; margin: 0 0 24px 0;
      background: var(--bg-card); border-bottom: 1px solid var(--border-default);
    }
    .ph-toolbar strong { font-size: 0.95rem; }
    .ph-seg { display: inline-flex; gap: 4px; }
    .ph-seg button {
      font: inherit; cursor: pointer; padding: 4px 12px; border-radius: 6px;
      border: 1px solid var(--border-default); background: var(--bg-page);
      color: var(--text-primary);
    }
    .ph-seg button[aria-pressed="true"] {
      background: var(--accent-blue); color: var(--text-on-accent);
      border-color: var(--accent-blue);
    }
    .ph-note { color: var(--text-secondary); font-size: 0.85rem; }
    .ph-body { padding: 0 20px 60px; max-width: 1100px; }
    .ph-section { margin: 0 0 36px; }
    .ph-section > h2.ph-h { font-size: 0.8rem; letter-spacing: 0.08em;
      text-transform: uppercase; color: var(--text-secondary);
      border-bottom: 1px solid var(--border-subtle); padding-bottom: 6px; }
    .ph-row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
    .ph-swatches { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
    .ph-chip { border: 1px solid var(--border-subtle); border-radius: 8px; overflow: hidden; }
    .ph-chip .sw { height: 46px; }
    .ph-chip .lbl { font-family: ui-monospace, monospace; font-size: 0.7rem;
      padding: 5px 7px; color: var(--text-secondary); word-break: break-all; }
    /* stand-in for the Instruments save-error banner (uses the --danger-* tokens) */
    .ph-save-error {
      margin: 0; padding: 10px 14px; border: 1px solid var(--danger-border);
      border-left-width: 4px; border-radius: 6px;
      background: var(--danger-bg); color: var(--danger-text); font-size: 0.9rem;
    }
    .ph-tint { border: 1px solid var(--border-subtle); border-radius: 8px;
      padding: 14px; font-size: 0.85rem; }
"""

# 5. Component gallery body.
tints = "\n".join(
    f'        <div class="ph-tint" style="background: var(--instrument-tint-{i});">Instrument card tint {i}</div>'
    for i in range(1, 7)
)
swatches = "\n".join(
    f'        <div class="ph-chip"><div class="sw" style="background: var({n});"></div>'
    f'<div class="lbl">{n}<br>light {v}</div></div>'
    for n, v in colour_tokens
)

body = f"""
  <div class="ph-toolbar">
    <strong>Dark-mode preview</strong>
    <span class="ph-seg" role="group" aria-label="Theme">
      <button data-set="system" aria-pressed="true">System</button>
      <button data-set="light" aria-pressed="false">Light</button>
      <button data-set="dark" aria-pressed="false">Dark</button>
    </span>
    <span class="ph-note">Faithful snapshot of base.html @ {{SHA}} + a DRAFT dark palette. Design tool only — not wired into the app.</span>
  </div>

  <div class="ph-body">
    <section class="ph-section">
      <h2 class="ph-h">Buttons (canonical .btn set)</h2>
      <div class="ph-row">
        <button class="btn">Primary</button>
        <button class="btn secondary">Primary Outline</button>
        <button class="btn alert-solid">Alert</button>
        <button class="btn alert">Alert Outline</button>
        <button class="btn danger-solid">Danger</button>
        <button class="btn danger">Danger Outline</button>
        <button class="btn destructive">Destructive</button>
        <button class="btn disabled" disabled>Disabled</button>
      </div>
    </section>

    <section class="ph-section">
      <h2 class="ph-h">Text &amp; links</h2>
      <h1>Heading 1</h1>
      <p class="page-subtitle">A page subtitle in secondary text.</p>
      <p>Body copy with an <a href="#">inline link</a> and some <strong>strong</strong> emphasis.</p>
      <p class="muted">Muted helper text (.muted).</p>
      <nav class="breadcrumb"><a href="#">Sessions</a> <span class="breadcrumb-sep">/</span> <a href="#">Session</a> <span class="breadcrumb-sep">/</span> <span aria-current="page">Instruments</span></nav>
    </section>

    <section class="ph-section">
      <h2 class="ph-h">Cards</h2>
      <div class="card">
        <h2>Plain card</h2>
        <p>A standard raised card surface. Body text sits on <code>--bg-card</code>.</p>
      </div>
      <div class="card rs-help-card"><strong>Help card.</strong> A tinted help slab — body text plus a strong lead.</div>
      <div class="card danger-zone" id="danger-zone">
        <h2>Danger Zone</h2>
        <p>Destructive-action card. The button is fixed-width here.</p>
        <button class="btn destructive">Clear all settings</button>
      </div>
    </section>

    <section class="ph-section">
      <h2 class="ph-h">Pills</h2>
      <div class="ph-row">
        <span class="pill pill-error">error</span>
        <span class="pill pill-warning">warning</span>
        <span class="pill pill-info">info</span>
        <span class="pill pill-success">success</span>
        <span class="pill pill-super">super</span>
        <span class="pill pill-handle">HANDLE_ID</span>
      </div>
    </section>

    <section class="ph-section">
      <h2 class="ph-h">Banners</h2>
      <div class="warning-banner">Warning banner — an amber advisory.</div>
      <div class="danger-banner">Danger banner — a hard red alert.</div>
      <p class="ph-save-error"><strong>Couldn't save.</strong> Soft inline-error treatment (the <code>--danger-*</code> tokens).</p>
    </section>

    <section class="ph-section">
      <h2 class="ph-h">Table &amp; config values</h2>
      <table>
        <thead><tr><th>Field</th><th>Value</th><th>Status</th></tr></thead>
        <tbody>
          <tr><td>Timezone</td><td><span class="config-value">Asia/Singapore</span></td><td><span class="pill pill-success">set</span></td></tr>
          <tr><td>SMTP host</td><td><span class="config-value-resolved">smtp.office365.com</span></td><td><span class="pill pill-info">inherited</span></td></tr>
          <tr><td>App password</td><td><span class="muted">not set</span></td><td><span class="pill pill-warning">pending</span></td></tr>
        </tbody>
      </table>
    </section>

    <section class="ph-section">
      <h2 class="ph-h">Instrument card tints</h2>
      <div class="ph-row">
{tints}
      </div>
    </section>

    <section class="ph-section">
      <h2 class="ph-h">All colour tokens ({len(colour_tokens)}) — swatch = ACTIVE theme; label = light reference value</h2>
      <div class="ph-swatches">
{swatches}
      </div>
    </section>
  </div>

  <script>
    (function () {{
      var root = document.documentElement;
      var btns = document.querySelectorAll(".ph-seg button");
      function apply(mode) {{
        if (mode === "system") root.removeAttribute("data-theme");
        else root.setAttribute("data-theme", mode);
        btns.forEach(function (b) {{
          b.setAttribute("aria-pressed", b.getAttribute("data-set") === mode ? "true" : "false");
        }});
      }}
      btns.forEach(function (b) {{
        b.addEventListener("click", function () {{ apply(b.getAttribute("data-set")); }});
      }});
    }})();
  </script>
"""

SHA = "f0b1f4f"  # base.html snapshot commit; bump when regenerating
body = body.replace("{SHA}", SHA)

html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Review Robin — dark-mode preview</title>
    <!-- GENERATED by guide/theme_preview.gen.py — do not edit by hand.
         Faithful snapshot of base.html's <style> + a DRAFT dark palette.
         Design tool for Segment 19C Item 2 (W4); not wired into the app. -->
    <style>{base_css}
{dark_block}
{harness_css}
    </style>
  </head>
  <body class="ui-v2">
{body}
  </body>
</html>
"""

OUT.write_text(html, encoding="utf-8")
print(f"Wrote {OUT.relative_to(ROOT)} ({len(html)} bytes, {len(colour_tokens)} tokens)")

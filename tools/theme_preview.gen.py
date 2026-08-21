#!/usr/bin/env python3
"""Generate tools/theme_preview.html — a standalone theme-preview harness.

Lifts the REAL `<style>` block from app/web/templates/base.html (so both the
component CSS *and* the light/dark palette are faithful, not a hand-copy) and
renders a component gallery + colour-token swatch grid. Open the output in a
browser; the toolbar flips `data-theme` on <html> to compare Light / Dark live.

Dark mode shipped in Segment 19C Item 2, so base.html is the source of truth —
this harness is a faithful *preview* of it (no separate palette that can drift).
It stays around as a design surface for future theme work:

  * To prototype a new theme (e.g. sepia) BEFORE touching the app, drop a
    `:root[data-theme="sepia"] { ... }` block into EXTRA_THEME_CSS below and add
    a matching `<button data-set="sepia">` to the toolbar; the gallery + swatches
    preview it immediately. Port the values into base.html once you're happy.

Regenerate after any base.html style change:  python3 tools/theme_preview.gen.py
Not production code; not wired into the app.
"""
import re
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = ROOT / "app/web/templates/base.html"
OUT = ROOT / "tools/theme_preview.html"

src = BASE.read_text(encoding="utf-8")

# 1. Lift the real <style>…</style> body verbatim (Jinja-free — verified).
#    Anchor on the <style> TAG at line start, not the first literal "<style>":
#    base.html's head comments mention "<style>" in prose (e.g. the no-FOUC
#    note "before <style>, so ..."), and a bare `<style>` match grabs that,
#    dragging a <script> block into the lifted CSS and corrupting the parse.
m = re.search(r"(?m)^[ \t]*<style>[ \t]*\n(.*?)</style>", src, re.DOTALL)
if not m:
    raise SystemExit("Could not find <style> block in base.html")
base_css = m.group(1)

# 2. Parse the light token list (name -> light value) from :root for the swatch grid.
tokens = []
for line in base_css.splitlines():
    tm = re.match(r"\s*(--[a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8});", line)
    if tm:
        tokens.append((tm.group(1), tm.group(2)))
# base.html now defines each token twice (light :root + the dark
# :root[data-theme="dark"] block); keep the first (light) value per name so the
# swatch grid lists each token once with its light reference value.
colour_tokens = []
_seen = set()
for _n, _v in tokens:
    if _n not in _seen:
        _seen.add(_n)
        colour_tokens.append((_n, _v))

# 3. Optional extra theme blocks to PROTOTYPE here before porting to base.html.
#    base.html already ships light (:root) + dark (:root[data-theme="dark"]),
#    both lifted verbatim above, so nothing is needed for the live preview. To
#    preview a new theme, add its block here and a matching toolbar button, e.g.:
#      EXTRA_THEME_CSS = ':root[data-theme="sepia"] { color-scheme: light; --bg-page: #f4ecd8; ... }'
EXTRA_THEME_CSS = ""

# 4. Harness-only chrome CSS (toolbar + gallery layout + a stand-in for
#    .save-error-banner, which lives in the instruments template not base.html).
harness_css = """
    /* ---- harness-only (not part of the app) ---- */
    /* Full-bleed page: override base.html's body margin so the sticky toolbar
       spans the width. base.html's lifted style already themes html/body
       (background + color-scheme), so nothing else is needed here. */
    html { background: var(--bg-page); }
    body.ui-v2 {
      margin: 0;
      min-height: 100vh;
      background: var(--bg-page);
      color: var(--text-primary);
    }
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
      <button data-set="light" aria-pressed="true">Light</button>
      <button data-set="dark" aria-pressed="false">Dark</button>
    </span>
    <span class="ph-note">Faithful live preview of base.html's real light / dark palette. Design tool only — not wired into the app.</span>
  </div>

  <div class="ph-body">
    <section class="ph-section">
      <h2 class="ph-h">Buttons — canonical roles (spec/ui_elements.md §6): Primary <code>.btn</code>, Secondary <code>.secondary</code>, Destructive <code>.destructive</code>, Alert <code>.danger-solid</code>, Amber <code>.alert</code></h2>
      <p class="muted" style="margin: 0 0 6px;">Active</p>
      <div class="ph-row" style="margin-bottom: 14px;">
        <button class="btn">Primary</button>
        <button class="btn secondary">Secondary</button>
        <button class="btn destructive">Destructive</button>
        <button class="btn danger-solid">Alert</button>
        <button class="btn alert">Amber</button>
      </div>
      <p class="muted" style="margin: 0 0 6px;">Disabled — same shape at opacity 0.5 (colour retained per role)</p>
      <div class="ph-row">
        <button class="btn" disabled>Primary</button>
        <button class="btn secondary" disabled>Secondary</button>
        <button class="btn destructive" disabled>Destructive</button>
        <button class="btn danger-solid" disabled>Alert</button>
        <button class="btn alert" disabled>Amber</button>
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
      <h2 class="ph-h">Form controls (the settings / setup pages are form-heavy)</h2>
      <div class="card">
        <label for="ph-in">Text input</label>
        <input type="text" id="ph-in" placeholder="reviews@your-org.edu" value="Course Reviews">
        <label for="ph-em">Email input</label>
        <input type="email" id="ph-em" placeholder="you@example.com">
        <label for="ph-num">Number input</label>
        <input type="number" id="ph-num" value="587">
        <label for="ph-sel">Select</label>
        <select id="ph-sel"><option>STARTTLS</option><option>SSL/TLS</option><option>None</option></select>
        <label for="ph-ta">Textarea</label>
        <textarea id="ph-ta" placeholder="Type a note…">Multi-line help text sits here.</textarea>
        <label for="ph-dis">Disabled input</label>
        <input type="text" id="ph-dis" value="frozen value" disabled>
        <p class="muted" style="margin-top: 10px;">Click a field to see the focus ring (accent-blue border + halo).</p>
      </div>
    </section>

    <section class="ph-section">
      <h2 class="ph-h">Chrome — top bar</h2>
      <div class="chrome">
        <div class="chrome-left">
          <span class="chrome-app-identity">Review Robin Web App (version 1.2.3)</span>
          <nav class="breadcrumb"><a href="#">Sessions</a> <span class="breadcrumb-sep">/</span> <span aria-current="page">Spring Review</span></nav>
        </div>
        <div class="chrome-user">
          <div>Signed in as Alex Operator (sys admin)</div>
          <a class="chrome-link" href="#">Settings</a>
          <a class="chrome-link" href="#">Admin</a>
          <a class="chrome-link" href="#">About</a>
          <a class="signout" href="#">Sign out</a>
        </div>
      </div>
    </section>

    <section class="ph-section">
      <h2 class="ph-h">Session navigation (tab strips + active states)</h2>
      <div class="session-nav-grid">
        <a class="session-home-anchor" href="#" title="Spring Review"><span class="home-anchor-text">Session Home</span></a>
        <div class="row-label setup-row row-setup active-group">Setup</div>
        <div class="tab-strip tab-strip-setup row-setup">
          <a class="nav-tab active" href="#">Reviewers</a>
          <a class="nav-tab" href="#">Reviewees</a>
          <a class="nav-tab" href="#">Relationships</a>
          <a class="nav-tab" href="#">Instruments</a>
          <a class="nav-tab" href="#">Email Template</a>
        </div>
        <div class="row-label ops-row">Operations</div>
        <div class="tab-strip tab-strip-ops">
          <a class="nav-tab" href="#">Assignments</a>
          <a class="nav-tab" href="#">Validate</a>
          <a class="nav-tab" href="#">Previews</a>
          <a class="nav-tab" href="#">Invitations</a>
          <a class="nav-tab" href="#">Responses</a>
          <a class="nav-tab" href="#">Extract data</a>
        </div>
      </div>
    </section>

    <section class="ph-section">
      <h2 class="ph-h">Tag chips &amp; back-link / page header</h2>
      <a class="back-link" href="#">&larr; Back to Sessions</a>
      <div class="rs-page-header"><h1>Reviewers</h1></div>
      <div class="ph-row" style="margin: 8px 0;">
        <span class="tag-chip is-selected">Tutor</span>
        <span class="tag-chip">Peer</span>
        <span class="tag-chip is-selected">Mentor</span>
        <span class="tag-chip">External</span>
      </div>
      <p class="help-preview">A .help-preview block — the pre-wrapped help text shown under a response field.</p>
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
        if (mode === "dark") root.setAttribute("data-theme", "dark");
        else root.removeAttribute("data-theme");  // light is the default :root
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

html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Review Robin — dark-mode preview</title>
    <!-- GENERATED by tools/theme_preview.gen.py — do not edit by hand.
         Faithful live preview of base.html's <style> (light + dark). A
         design tool for theme work; not wired into the app. -->
    <style>{base_css}
{EXTRA_THEME_CSS}
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

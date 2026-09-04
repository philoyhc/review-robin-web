"""Shared helpers for the theme harness generators.

Both `theme_preview.gen.py` (read-only preview) and `theme_customizer.gen.py`
(editable designer) lift base.html's real `<style>` + palette and render the
same component gallery. This module holds the pieces they share so the gallery
isn't duplicated. Not production code.
"""
import re

_STYLE_RE = re.compile(r"(?m)^[ \t]*<style>[ \t]*\n(.*?)</style>", re.DOTALL)
_TOKEN_RE = re.compile(r"(--[a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8});")


def lift_base_style(base_html_text):
    """Return base.html's real `<style>` body.

    Anchors on the `<style>` TAG at line start, not the first literal
    "<style>": base.html's head comments mention "<style>" in prose (the
    no-FOUC note "before <style>, so ..."), and a bare match grabs that,
    dragging a <script> block into the lifted CSS and corrupting the parse.
    """
    m = _STYLE_RE.search(base_html_text)
    if not m:
        raise SystemExit("Could not find <style> block in base.html")
    return m.group(1)


def parse_light_tokens(base_css):
    """Ordered `[(name, light_value)]`, first (light `:root`) value per token."""
    seen = set()
    out = []
    for line in base_css.splitlines():
        tm = re.match(r"\s*(--[a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8});", line)
        if tm and tm.group(1) not in seen:
            seen.add(tm.group(1))
            out.append((tm.group(1), tm.group(2)))
    return out


def _block(base_css, selector_re):
    m = re.search(selector_re + r"\s*\{(.*?)\}", base_css, re.DOTALL)
    if not m:
        return {}
    return {tm.group(1): tm.group(2) for tm in _TOKEN_RE.finditer(m.group(1))}


def parse_theme_tokens(base_css):
    """`{"light": {name: value}, "dark": {name: value}}` from the two `:root`
    blocks — the light `:root { … }` and `:root[data-theme="dark"] { … }`."""
    return {
        "light": _block(base_css, r":root"),
        "dark": _block(base_css, r':root\[data-theme="dark"\]'),
    }


# ---- Two-tier parsing (data-driven; works for any tokens.css of this shape) ----
# The palette is Tier 1 primitives (`--name: #hex;`) + Tier 2 semantic tokens
# (`--name: var(--primitive);`), the semantic block grouped by `/* Label */`
# cluster comments. Dark `:root` re-maps the same semantic tokens; primitives
# live only in light `:root` (theme-agnostic).
_SEM_RE = re.compile(r"(--[a-z0-9-]+):\s*var\((--[a-z0-9-]+)\)\s*;")
_LIGHT_SEL = r":root"
_DARK_SEL = r':root\[data-theme="dark"\]'


def _block_text(base_css, selector_re):
    m = re.search(selector_re + r"\s*\{(.*?)\n\s*\}", base_css, re.DOTALL)
    return m.group(1) if m else ""


def parse_primitives(base_css):
    """Ordered `[(name, hex)]` — the Tier-1 primitives (hex-valued, light root)."""
    return [(m.group(1), m.group(2))
            for m in _TOKEN_RE.finditer(_block_text(base_css, _LIGHT_SEL))]


def parse_semantic(base_css):
    """`{"light": [(sem, prim)], "dark": [(sem, prim)]}` — semantic→primitive maps."""
    return {
        "light": [(m.group(1), m.group(2))
                  for m in _SEM_RE.finditer(_block_text(base_css, _LIGHT_SEL))],
        "dark": [(m.group(1), m.group(2))
                 for m in _SEM_RE.finditer(_block_text(base_css, _DARK_SEL))],
    }


def parse_clusters(base_css):
    """Ordered `[(cluster_label, [sem_token, …])]` from the light Tier-2
    `/* Label */` comments — the data-driven cluster grouping."""
    text = _block_text(base_css, _LIGHT_SEL)
    if "Tier 2" in text:                       # drop the Tier-1 half
        text = text.split("Tier 2", 1)[1]
    clusters, cur = [], None
    for line in text.splitlines():
        cm = re.match(r"\s*/\*\s*(.+?)\s*\*/\s*$", line)
        sm = re.match(r"\s*(--[a-z0-9-]+):\s*var\(", line)
        if cm:
            label = cm.group(1)
            if label.startswith("==") or "end design tokens" in label:
                continue
            cur = (label, [])
            clusters.append(cur)
        elif sm and cur is not None:
            cur[1].append(sm.group(1))
    return clusters


# Coarse hue family for a hex — groups primitives for seed controls (data-driven,
# no hard-coded token names). Returns one of: neutral, red, amber, green, sky,
# blue, violet.
def hue_family(hex_value):
    h = hex_value.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    mx, mn = max(r, g, b), min(r, g, b)
    if mx - mn < 24:
        return "neutral"
    import colorsys
    hu = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)[0] * 360
    if hu < 20 or hu >= 330:
        return "red"
    if hu < 45:
        return "amber"
    if hu < 90:
        return "amber" if g < 200 else "green"
    if hu < 165:
        return "green"
    if hu < 200:
        return "sky"
    if hu < 255:
        return "blue"
    return "violet"


# Harness-only chrome CSS (toolbar + gallery layout). Consumes only the app's
# Tier-2 **semantic** tokens (like every component now), so it themes for free.
HARNESS_CSS = """
    /* ---- harness-only (not part of the app) ---- */
    html { background: var(--surface-page); }
    body.ui-v2 {
      margin: 0;
      min-height: 100vh;
      background: var(--surface-page);
      color: var(--text-body);
    }
    .ph-toolbar {
      position: sticky; top: 0; z-index: 50;
      display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
      padding: 10px 20px; margin: 0 0 24px 0;
      background: var(--surface-card); border-bottom: 1px solid var(--border-default);
    }
    .ph-toolbar strong { font-size: 0.95rem; }
    .ph-seg { display: inline-flex; gap: 4px; }
    .ph-seg button {
      font: inherit; cursor: pointer; padding: 4px 12px; border-radius: 6px;
      border: 1px solid var(--border-default); background: var(--surface-page);
      color: var(--text-body);
    }
    .ph-seg button[aria-pressed="true"] {
      background: var(--btn-primary-bg); color: var(--btn-primary-fg);
      border-color: var(--btn-primary-border);
    }
    .ph-note { color: var(--text-subtle); font-size: 0.85rem; }
    .ph-body { padding: 0 20px 60px; max-width: 1100px; }
    .ph-section { margin: 0 0 36px; }
    .ph-section > h2.ph-h { font-size: 0.8rem; letter-spacing: 0.08em;
      text-transform: uppercase; color: var(--text-subtle);
      border-bottom: 1px solid var(--border-subtle); padding-bottom: 6px; }
    .ph-row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
    .ph-swatches { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
    .ph-chip { border: 1px solid var(--border-subtle); border-radius: 8px; overflow: hidden; }
    .ph-chip .sw { height: 46px; }
    .ph-chip .lbl { font-family: ui-monospace, monospace; font-size: 0.7rem;
      padding: 5px 7px; color: var(--text-subtle); word-break: break-all; }
    .ph-chip .lbl b { display: block; font-family: system-ui, sans-serif;
      font-size: 0.78rem; font-weight: 600; color: var(--text-body);
      word-break: normal; margin-bottom: 2px; }
    /* stand-in for the Instruments save-error banner (soft error tokens) */
    .ph-save-error {
      margin: 0; padding: 10px 14px; border: 1px solid var(--status-error-soft-border);
      border-left-width: 4px; border-radius: 6px;
      background: var(--status-error-soft-bg); color: var(--status-error-soft-fg); font-size: 0.9rem;
    }
    /* advisory banners — the app-level .warning-/.danger-banner classes lost
       their CSS in the two-tier migration; restyle the preview from the status
       tokens so they render (and so Part C can pick them). */
    .warning-banner, .danger-banner {
      margin: 0 0 10px; padding: 10px 14px; border: 1px solid; border-left-width: 4px;
      border-radius: 6px; font-size: 0.9rem;
    }
    .warning-banner { background: var(--status-warning-bg); color: var(--status-warning-fg); border-color: var(--status-warning-border); }
    .danger-banner { background: var(--status-error-bg); color: var(--status-error-fg); border-color: var(--status-error-border); }
    .ph-tint { border: 1px solid var(--border-subtle); border-radius: 8px;
      padding: 14px; font-size: 0.85rem; }
"""


# The text / links sample markup — shared so the customizer can host it in its
# own "Text, links & background" zone (with the relevant token chips) while the
# read-only preview keeps it as a plain gallery section.
TEXT_LINKS_SAMPLE = """      <h1>Heading 1</h1>
      <p class="page-subtitle">A page subtitle in secondary text.</p>
      <p>Body copy with an <a href="#">inline link</a> and some <strong>strong</strong> emphasis.</p>
      <p class="muted">Muted helper text (.muted).</p>
      <nav class="breadcrumb"><a href="#">Sessions</a> <span class="breadcrumb-sep">/</span> <a href="#">Session</a> <span class="breadcrumb-sep">/</span> <span aria-current="page">Instruments</span></nav>"""


def component_sections():
    """The component gallery as an ordered `[(key, section_html)]` list, so
    callers can reorder / relocate individual zones (the customizer hoists the
    `text` zone to the front and embeds its tokens). Does NOT include the
    toolbar, the token grid, or the `ph-body` wrapper — callers add those.

    Preview-annotation captions carry `.ph-anno` (alongside `.muted`) so the
    customizer's picker can skip them: they label the demo, they aren't app
    screen elements to identify a token for."""
    tints = "\n".join(
        f'        <div class="ph-tint" style="background: var(--surface-tint-{i});">Instrument card tint {i}</div>'
        for i in range(1, 7)
    )
    return [
        ("chrome", """    <section class="ph-section">
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
    </section>"""),
        ("nav", """    <section class="ph-section">
      <h2 class="ph-h">Session navigation, back-link, page header &amp; chips</h2>
      <div class="session-nav-grid">
        <a class="session-home-anchor active" href="#" style="grid-row: 1;" title="Session Home (selected)"><span class="home-anchor-text">Session Home</span></a>
        <a class="session-home-anchor" href="#" style="grid-row: 2;" title="Session Home"><span class="home-anchor-text">Session Home</span></a>
        <div class="row-label setup-row row-setup active-group">Setup</div>
        <div class="tab-strip tab-strip-setup row-setup">
          <a class="nav-tab active" href="#">Reviewers</a>
          <a class="nav-tab" href="#">Reviewees</a>
          <a class="nav-tab" href="#">Relationships</a>
          <a class="nav-tab" href="#">Instruments</a>
        </div>
        <div class="row-label ops-row">Operations</div>
        <div class="tab-strip tab-strip-ops">
          <a class="nav-tab" href="#">Assignments</a>
          <a class="nav-tab" href="#">Validate</a>
          <a class="nav-tab" href="#">Previews</a>
          <a class="nav-tab" href="#">Invitations</a>
        </div>
      </div>
      <a class="back-link" href="#" style="display: inline-block; margin-top: 16px;">&larr; Back to Sessions</a>
      <div class="rs-page-header"><h1>Reviewers</h1></div>
      <div class="ph-row" style="margin: 8px 0;">
        <span class="tag-chip is-selected">Tutor</span>
        <span class="tag-chip">Peer</span>
        <span class="tag-chip is-selected">Mentor</span>
        <span class="tag-chip">External</span>
      </div>
      <p class="help-preview">A .help-preview block — the pre-wrapped help text shown under a response field.</p>
    </section>"""),
        ("text", f"""    <section class="ph-section">
      <h2 class="ph-h">Text &amp; links</h2>
{TEXT_LINKS_SAMPLE}
    </section>"""),
        ("cards", f"""    <section class="ph-section">
      <h2 class="ph-h">Cards</h2>
      <div class="card">
        <h2>Plain card</h2>
        <p>A standard raised card surface. Body text sits on <code>--bg-card</code>.</p>
      </div>
      <div class="card rs-help-card"><strong>Help card.</strong> A tinted help slab — body text plus a strong lead.</div>
      <div class="card danger-zone" id="danger-zone">
        <h2>Danger Zone</h2>
        <p>Destructive-action card. The button is fixed-width here.</p>
        <button class="btn destructive">Destructive</button>
      </div>
      <p class="muted ph-anno" style="margin: 16px 0 6px;">Instrument card tints</p>
      <div class="ph-row">
{tints}
      </div>
    </section>"""),
        ("forms", """    <section class="ph-section">
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
        <p class="muted ph-anno" style="margin-top: 10px;">Click a field to see the focus ring (accent-blue border + halo).</p>
      </div>
    </section>"""),
        ("buttons", """    <section class="ph-section">
      <h2 class="ph-h">Buttons — canonical roles (spec/ui_elements.md §6): Primary <code>.btn</code>, Secondary <code>.secondary</code>, Destructive <code>.destructive</code>, Alert <code>.danger-solid</code>, Amber <code>.alert</code></h2>
      <p class="muted ph-anno" style="margin: 0 0 6px;">Active</p>
      <div class="ph-row" style="margin-bottom: 14px;">
        <button class="btn">Primary</button>
        <button class="btn secondary">Secondary</button>
        <button class="btn destructive">Destructive</button>
        <button class="btn danger-solid">Alert</button>
        <button class="btn alert">Amber</button>
      </div>
      <p class="muted ph-anno" style="margin: 0 0 6px;">Disabled — same shape at opacity 0.5 (colour retained per role)</p>
      <div class="ph-row">
        <button class="btn" disabled>Primary</button>
        <button class="btn secondary" disabled>Secondary</button>
        <button class="btn destructive" disabled>Destructive</button>
        <button class="btn danger-solid" disabled>Alert</button>
        <button class="btn alert" disabled>Amber</button>
      </div>
    </section>"""),
        ("pills", """    <section class="ph-section">
      <h2 class="ph-h">Pills</h2>
      <div class="ph-row">
        <span class="pill pill-error">error</span>
        <span class="pill pill-warning">warning</span>
        <span class="pill pill-info">info</span>
        <span class="pill pill-success">success</span>
        <span class="pill pill-super">super</span>
        <span class="pill pill-handle">HANDLE_ID</span>
      </div>
    </section>"""),
        ("banners", """    <section class="ph-section">
      <h2 class="ph-h">Banners</h2>
      <div class="warning-banner">Warning banner — an amber advisory.</div>
      <div class="danger-banner">Danger banner — a hard red alert.</div>
      <p class="ph-save-error"><strong>Couldn't save.</strong> Soft inline-error treatment (the <code>--danger-*</code> tokens).</p>
    </section>"""),
        ("table", """    <section class="ph-section">
      <h2 class="ph-h">Table &amp; config values</h2>
      <table>
        <thead><tr><th>Field</th><th>Value</th><th>Status</th></tr></thead>
        <tbody>
          <tr><td>Timezone</td><td><span class="config-value">Asia/Singapore</span></td><td><span class="pill pill-success">set</span></td></tr>
          <tr><td>SMTP host</td><td><span class="config-value-resolved">smtp.office365.com</span></td><td><span class="pill pill-info">inherited</span></td></tr>
          <tr><td>App password</td><td><span class="muted">not set</span></td><td><span class="pill pill-warning">pending</span></td></tr>
        </tbody>
      </table>
    </section>"""),
    ]


def component_gallery():
    """The full component gallery as one string — every section in order.
    Used by the read-only preview; the customizer composes from
    `component_sections()` directly so it can relocate individual zones."""
    return "\n\n".join(html for _, html in component_sections()) + "\n"


def page(title, generated_by, base_css, extra_css, body):
    """Assemble the full standalone HTML document."""
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <!-- GENERATED by {generated_by} — do not edit by hand. Not wired into the app. -->
    <style>{base_css}
{extra_css}
{HARNESS_CSS}
    </style>
  </head>
  <body class="ui-v2">
{body}
  </body>
</html>
"""

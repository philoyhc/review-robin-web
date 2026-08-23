#!/usr/bin/env python3
"""Generate tools/theme_customizer.html — a standalone two-tier theme designer.

Item 5 of guide/segment_19C_refinements.md, reworked for the two-tier token
system (Item 6). Lifts base.html's palette and lets you design it live:

- **Primitives** — edit the raw palette. Per-primitive colour pickers grouped
  by name-family, plus **seed** controls that shift a whole chromatic family in
  OKLCH from one swatch. Editing a primitive cascades through `var()` to every
  semantic token and every gallery component instantly.
- **Semantic remaps** — repoint any role to a different primitive, per theme
  (a deliberate re-mapping). Light and dark are edited separately.
- **Export JSON** — `{ primitives, semantic: { light, dark } }`, which a coding
  agent ports 1:1 into base.html's Tier-1 + Tier-2 `:root` blocks.

Data-driven: primitives, families, clusters, and the semantic maps are read
from base.html itself (via _harness_common), so this drives any tokens.css of
the same shape (portability goal, decision #6).

Regenerate after any base.html change:  python3 tools/theme_customizer.gen.py
Not production code; not wired into the app.
"""
import colorsys
import json
import pathlib

import _harness_common as hc

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = ROOT / "app/web/templates/base.html"
OUT = ROOT / "tools/theme_customizer.html"

base_css = hc.lift_base_style(BASE.read_text(encoding="utf-8"))
prims = hc.parse_primitives(base_css)              # [(name, hex)] ordered
prim_val = dict(prims)
sem = hc.parse_semantic(base_css)
sem_light, sem_dark = dict(sem["light"]), dict(sem["dark"])
clusters = [(n, t) for n, t in hc.parse_clusters(base_css) if t]

# --- family grouping by descriptive name prefix (--<prefix>-<shade>) ---
NEUTRAL_PREFIXES = {"white", "paper", "gray", "slate", "ink", "tint"}
PREFIX_ORDER = ["white", "paper", "gray", "slate", "ink",
                "blue", "sky", "green", "amber", "red", "danger", "violet", "tint"]


def prefix(name):
    return name[2:].split("-")[0]


groups = {}
for name, val in prims:
    groups.setdefault(prefix(name), []).append((name, val))
prim_groups = [(p, groups[p]) for p in PREFIX_ORDER if p in groups]


def saturation(hexv):
    h = hexv.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hsv(r, g, b)[1]


# Seeds = chromatic families; anchor = the most-saturated member.
seed_families = {}
for p, members in groups.items():
    if p in NEUTRAL_PREFIXES:
        continue
    anchor = max(members, key=lambda m: saturation(m[1]))[0]
    seed_families[p] = {"anchor": anchor, "members": [n for n, _ in members]}
SEED_ORDER = [p for p in PREFIX_ORDER if p in seed_families]

# --- contrast pairs (semantic tokens; resolved per active theme) ---
PAIRS = [
    ("Body / page", "--text-body", "--surface-page"),
    ("Body / card", "--text-body", "--surface-card"),
    ("Subtle / card", "--text-subtle", "--surface-card"),
    ("Dim / card", "--text-dim", "--surface-card"),
    ("Link / page", "--text-link", "--surface-page"),
    ("Primary btn", "--btn-primary-fg", "--btn-primary-bg"),
    ("Alert btn", "--btn-alert-fg", "--btn-alert-bg"),
    ("Destructive (outline)", "--btn-destructive-fg", "--surface-page"),
    ("Pill · info", "--status-info-fg", "--status-info-bg"),
    ("Pill · success", "--status-success-fg", "--status-success-bg"),
    ("Pill · warning", "--status-warning-fg", "--status-warning-bg"),
    ("Pill · error", "--status-error-fg", "--status-error-bg"),
    ("Selected", "--selected-fg", "--selected-bg"),
]

# --- pick targets: preview element -> the semantic token each colour facet
# paints from. `sel` is scoped inside Part A; `facets` are (label, prop, token)
# where prop is bg / fg / border. This is the authority for Part C's readout
# (which token an element uses) and for "what else uses this token" (grouping
# every facet by token). Verified against base.html's rules; a browser-side
# self-check compares each facet's computed colour to its token to catch drift.
def _btn(mod, label, key):
    sel = "button.btn" + (("." + mod) if mod else ":not(.secondary):not(.destructive):not(.danger-solid):not(.alert)")
    return (sel, label, [("infill", "bg", f"--btn-{key}-bg"),
                         ("text", "fg", f"--btn-{key}-fg"),
                         ("border", "border", f"--btn-{key}-border")])


def _pill(name, label):
    return (f".pill-{name}", label, [("infill", "bg", f"--status-{name}-bg"),
                                     ("text", "fg", f"--status-{name}-fg")])


TARGETS = [
    _btn("", "Primary button", "primary"),
    _btn("secondary", "Secondary button", "secondary"),
    _btn("destructive", "Destructive button", "destructive"),
    _btn("danger-solid", "Alert button", "alert"),
    _btn("alert", "Amber button", "amber"),
    ("h1", "Heading", [("text", "fg", "--text-body")]),
    (".page-subtitle", "Page subtitle", [("text", "fg", "--text-subtle")]),
    ("p a[href]", "Inline link", [("text", "fg", "--text-link")]),
    (".muted", "Muted text", [("text", "fg", "--text-subtle")]),
    # a plain .card fills with --surface-page (raised via its border), not --surface-card
    (".card:not(.rs-help-card):not(.danger-zone)", "Card surface",
     [("background", "bg", "--surface-page"), ("text", "fg", "--text-body")]),
    (".rs-help-card", "Help card", [("background", "bg", "--border-default"), ("text", "fg", "--text-body")]),
    (".danger-zone", "Danger-zone card",
     [("background", "bg", "--card-warning-bg"), ("text", "fg", "--text-body"),
      ("border", "border", "--card-warning-border")]),
    _pill("error", "Error pill"),
    _pill("warning", "Warning pill"),
    # info / success text are remapped under body.ui-v2 (not the -fg token)
    (".pill-info", "Info pill", [("infill", "bg", "--status-info-bg"), ("text", "fg", "--text-body")]),
    (".pill-success", "Success pill", [("infill", "bg", "--status-success-bg"), ("text", "fg", "--status-success-accent")]),
    _pill("super", "Super pill"),
    (".pill-handle", "Handle pill", [("infill", "bg", "--surface-muted"), ("text", "fg", "--text-body")]),
    (".ph-save-error", "Inline save error",
     [("background", "bg", "--status-error-soft-bg"), ("text", "fg", "--status-error-soft-fg"),
      ("border", "border", "--status-error-soft-border")]),
    ("input[type=text]", "Text input",
     [("background", "bg", "--surface-page"), ("text", "fg", "--text-body"), ("border", "border", "--border-default")]),
    (".config-value", "Config value", [("infill", "bg", "--config-value-bg"), ("text", "fg", "--config-value-fg")]),
    (".config-value-resolved", "Resolved config value", [("infill", "bg", "--config-value-resolved-bg")]),
    (".nav-tab.active", "Active nav tab", [("infill", "bg", "--nav-tab-active-bg"), ("text", "fg", "--text-body")]),
    (".nav-tab:not(.active)", "Nav tab", [("text", "fg", "--text-dim")]),
    (".tag-chip.is-selected", "Selected tag chip", [("infill", "bg", "--selected-bg"), ("text", "fg", "--selected-fg")]),
    (".back-link", "Back link", [("text", "fg", "--text-link")]),
    (".help-preview", "Help preview text", [("text", "fg", "--text-body")]),
]
TARGETS += [(f".ph-tint:nth-child({i})", f"Instrument tint {i}", [("background", "bg", f"--surface-tint-{i}")])
            for i in range(1, 7)]

targets_data = [{"sel": s, "el": el, "facets": [{"f": f, "prop": p, "token": t} for f, p, t in fac]}
                for s, el, fac in TARGETS]

DATA = {
    "prims": prim_val,
    "primOrder": [n for n, _ in prims],
    "semLight": sem_light,
    "semDark": sem_dark,
    "families": seed_families,
    "seedOrder": SEED_ORDER,
    "targets": targets_data,
}


def pretty(token):
    return token.lstrip("-").replace("-", " ")


# ---------- markup ----------
seed_swatches = "\n".join(
    f'        <label class="tc-seed" data-fam="{p}">'
    f'<input type="color" class="tc-seed-color" value="{prim_val[seed_families[p]["anchor"]]}" '
    f'aria-label="{p} seed"><span>{p}</span></label>'
    for p in SEED_ORDER
)
seeds_section = f"""    <section class="tc-sec">
      <h2 class="tc-h">Seeds — shift a whole chromatic primitive family (hue / lightness / chroma, OKLCH) from one swatch. The primitive grid below overrides individual primitives.</h2>
      <div class="tc-seed-row">
{seed_swatches}
      </div>
    </section>"""


def prim_chip(name):
    return (
        f'        <div class="tc-chip" data-prim="{name}" title="{name}">'
        f'<input type="color" class="tc-color" value="{prim_val[name]}" aria-label="{name}">'
        f'<input type="text" class="tc-hex" value="{prim_val[name]}" spellcheck="false" aria-label="{name} hex">'
        f'<span class="tc-name">{pretty(name)}</span></div>'
    )


prim_blocks = []
for p, members in prim_groups:
    chips = "\n".join(prim_chip(n) for n, _ in members)
    prim_blocks.append(
        f'      <div class="tc-fam"><h3 class="tc-fam-h">{p} ({len(members)})</h3>'
        f'\n      <div class="tc-grid">\n{chips}\n      </div></div>'
    )
prim_section = f"""    <section class="tc-sec">
      <h2 class="tc-h">Primitives ({len(prims)}) — the raw palette (theme-agnostic). Edit a swatch; every semantic token + component repaints live.</h2>
{chr(10).join(prim_blocks)}
    </section>"""

# semantic remap: per cluster, each token gets light + dark <select>. A role can
# map to a PRIMITIVE (the independent default) or to another SEMANTIC token — a
# deliberate coupling (`--x: var(--y)`, both Tier 2), per the model's @coupled
# rule. The dropdown offers both, grouped.
sem_names = [t for _, toks in clusters for t in toks]
opts = (
    '<optgroup label="Primitive (independent)">'
    + "".join(f'<option value="{n}">{n}</option>' for n, _ in prims)
    + '</optgroup><optgroup label="Semantic (couple → @coupled)">'
    + "".join(f'<option value="{t}">{t}</option>' for t in sem_names)
    + "</optgroup>"
)
sem_blocks = []
for cname, toks in clusters:
    rows = "\n".join(
        f'        <div class="tc-remap" data-sem="{t}">'
        f'<span class="tc-remap-name">{pretty(t)}<span class="tc-coupled" hidden>⛓ coupled</span></span>'
        f'<span class="tc-swatch" style="background: var({t});"></span>'
        f'<select class="tc-sel" data-mode="light">{opts}</select>'
        f'<select class="tc-sel" data-mode="dark">{opts}</select></div>'
        for t in toks
    )
    sem_blocks.append(
        f'      <details class="tc-cluster"><summary>{cname} · {len(toks)}</summary>\n'
        f'      <div class="tc-remap-head"><span>role</span><span></span><span>light → primitive</span><span>dark → primitive</span></div>\n'
        f'{rows}\n      </details>'
    )
sem_section = f"""    <section class="tc-sec">
      <h2 class="tc-h">Semantic remaps — repoint a role, per theme. Target a <strong>primitive</strong> (the independent default) or another <strong>semantic token</strong> — a deliberate coupling (<code>--x: var(--y)</code>, marked ⛓; export it as <code>@coupled</code>). Edit the ACTIVE theme's column; both are saved + exported.</h2>
{chr(10).join(sem_blocks)}
    </section>"""

contrast_rows = "\n".join(
    f'        <div class="tc-cx" data-fg="{fg}" data-bg="{bg}">'
    f'<span class="tc-cx-sample" style="background: var({bg}); color: var({fg})">Aa — {label}</span>'
    f'<span class="tc-cx-ratio">—</span><span class="tc-cx-badge">—</span></div>'
    for label, fg, bg in PAIRS
)
contrast_section = f"""    <section class="tc-sec">
      <h2 class="tc-h">Contrast (AA) — live WCAG ratio per semantic bg/text pair, ACTIVE theme (target 4.5:1)</h2>
      <div class="tc-cx-grid">
{contrast_rows}
      </div>
    </section>"""

toolbar = """  <div class="ph-toolbar">
    <strong>Two-tier theme customizer</strong>
    <span class="ph-seg" role="group" aria-label="Theme">
      <button data-set="light" aria-pressed="true">Light</button>
      <button data-set="dark" aria-pressed="false">Dark</button>
    </span>
    <span class="tc-controls">
      <button data-act="defaults">Load defaults</button>
      <button data-act="export">Export JSON</button>
      <label class="tc-file">Import JSON…<input type="file" accept=".json,application/json" data-act="import"></label>
    </span>
    <span class="tc-status" data-status>Editing <strong>light</strong> · no changes</span>
  </div>"""

editor_css = r"""
    .tc-controls { display: inline-flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .tc-controls button, .tc-controls label.tc-file {
      font: inherit; font-size: 0.8em; cursor: pointer; padding: 3px 10px; border-radius: 6px;
      border: 1px solid var(--border-default); background: var(--surface-page); color: var(--text-body); }
    .tc-controls input[type=file] { display: none; }
    .tc-status { color: var(--text-subtle); font-size: 0.8rem; }
    /* Page layout: the sticky toolbar spans the top. Below it, a left column
       stacks Part A (preview) over Part B (tokens) and scrolls on its own;
       Part C sits on the right (also scrollable). The left column holds five
       primitive cards per row, scaled 20% past the base 5 x 150 width so the
       cards have more room; Part A previews at that width and Part B's
       primitive grid stays five per row (each card stretches to fill). */
    body.ui-v2 { height: 100vh; overflow: hidden; display: flex; flex-direction: column; }
    .ph-toolbar { margin-bottom: 0; flex: none; }
    .tc-cols { --tc-card: 150px; --tc-gap: 8px; flex: 1; min-height: 0; display: flex; align-items: stretch; }
    .tc-left { flex: none; box-sizing: border-box; overflow-y: auto;
      width: calc((5 * var(--tc-card) + 4 * var(--tc-gap) + 40px) * 1.2);
      border-right: 1px solid var(--border-default); }
    .tc-part-c { flex: 1; min-width: 0; overflow-y: auto; }
    .tc-c-placeholder { color: var(--text-subtle); font-size: 0.85rem; max-width: 40ch; }
    /* pickable preview elements + current selection */
    .tc-pickable { cursor: pointer; }
    .tc-pickable:hover { outline: 2px dashed var(--focus-ring); outline-offset: 2px; }
    .tc-picked { outline: 2px solid var(--focus-ring) !important; outline-offset: 2px; }
    /* Part C readout */
    .tc-c-el { font-size: 1rem; font-weight: 600; margin: 2px 0 2px; }
    .tc-c-sub { color: var(--text-subtle); font-size: 0.76rem; margin: 0 0 14px; }
    .tc-facet { border: 1px solid var(--border-subtle); border-radius: 8px; padding: 10px 12px; margin: 0 0 10px; }
    .tc-facet-h { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 0.82rem; margin-bottom: 8px; }
    .tc-facet-h .tc-c-swatch { width: 20px; height: 20px; border-radius: 4px; border: 1px solid var(--border-subtle); flex: none; }
    .tc-facet-h .tc-facet-name { text-transform: capitalize; }
    .tc-facet-h .tc-facet-prop { color: var(--text-dim); font-weight: 400; font-size: 0.72rem; }
    .tc-c-row { display: grid; grid-template-columns: 84px 1fr; gap: 4px 10px; font-size: 0.78rem; align-items: baseline; }
    .tc-c-row dt { color: var(--text-dim); }
    .tc-c-row dd { margin: 0; }
    .tc-c-row code { font-family: ui-monospace, monospace; font-size: 0.74rem; color: var(--text-body); }
    .tc-c-chain { color: var(--text-subtle); }
    .tc-c-hex { font-family: ui-monospace, monospace; font-size: 0.72rem; color: var(--text-dim); margin-left: 4px; }
    .tc-c-users { list-style: none; margin: 0; padding: 0; }
    .tc-c-users li { font-size: 0.76rem; color: var(--text-body); padding: 1px 0; }
    .tc-c-users .tc-c-none { color: var(--text-dim); font-style: italic; }
    .tc-part { box-sizing: border-box; padding: 18px 20px 32px; }
    .tc-part-b { border-top: 1px solid var(--border-default); }
    .tc-part-h { margin: 0 0 14px; padding-bottom: 8px; border-bottom: 1px solid var(--border-subtle);
      font-size: 0.9rem; font-weight: 600; }
    .tc-part-note { font-weight: 400; font-size: 0.78rem; color: var(--text-subtle); }
    .tc-sec { margin: 0 0 34px; }
    .tc-h { font-size: 0.8rem; letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-subtle);
      border-bottom: 1px solid var(--border-subtle); padding-bottom: 6px; }
    .tc-seed-row { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 10px; }
    .tc-seed { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; font-size: 0.85rem; text-transform: capitalize; }
    .tc-seed-color { width: 30px; height: 26px; padding: 0; border: 1px solid var(--border-default); border-radius: 6px; background: none; cursor: pointer; }
    .tc-fam { margin: 12px 0; }
    .tc-fam-h { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-dim); margin: 0 0 6px; }
    .tc-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: var(--tc-gap); }
    .tc-chip { display: flex; align-items: center; gap: 8px; border: 1px solid var(--border-subtle); border-radius: 8px; padding: 6px 8px; }
    .tc-color { width: 34px; height: 26px; padding: 0; border: 1px solid var(--border-default); border-radius: 4px; background: none; cursor: pointer; flex: none; }
    body.ui-v2 .tc-chip input.tc-hex { width: 58px; font-family: ui-monospace, monospace; font-size: 0.68rem; padding: 2px 4px; flex: none; box-sizing: border-box; letter-spacing: -0.01em; }
    .tc-name { flex: 1; min-width: 0; font-size: 0.72rem; color: var(--text-subtle); line-height: 1.2; }
    .tc-cluster { margin: 8px 0; border: 1px solid var(--border-subtle); border-radius: 8px; padding: 4px 12px; }
    .tc-cluster summary { cursor: pointer; font-weight: 600; font-size: 0.85rem; padding: 4px 0; }
    .tc-remap-head, .tc-remap { display: grid; grid-template-columns: 1.4fr 24px 1fr 1fr; gap: 8px; align-items: center; }
    .tc-remap-head { font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-dim); padding: 4px 0; }
    .tc-remap { padding: 3px 0; border-top: 1px solid var(--border-subtle); }
    .tc-remap.is-coupled { box-shadow: inset 2px 0 0 0 var(--status-warning-accent); }
    .tc-remap-name { font-size: 0.76rem; }
    .tc-coupled { display: inline-block; margin-left: 6px; font-size: 0.62rem; font-weight: 600;
      color: var(--status-warning-fg); background: var(--status-warning-bg); border-radius: 9999px; padding: 0 6px; }
    .tc-swatch { width: 18px; height: 18px; border-radius: 4px; border: 1px solid var(--border-subtle); }
    body.ui-v2 .tc-remap select.tc-sel { width: 100%; font-size: 0.72rem; padding: 2px 4px; box-sizing: border-box;
      font-family: ui-monospace, monospace; border: 1px solid var(--border-default); border-radius: 5px; background: var(--surface-page); color: var(--text-body); }
    .tc-cx-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 8px; }
    .tc-cx { display: flex; align-items: center; gap: 8px; }
    .tc-cx-sample { flex: 1; padding: 4px 10px; border-radius: 6px; border: 1px solid var(--border-subtle); font-size: 0.8rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .tc-cx-ratio { font-family: ui-monospace, monospace; font-size: 0.72rem; color: var(--text-subtle); min-width: 58px; text-align: right; }
    .tc-cx-badge { font-size: 0.66rem; font-weight: 600; padding: 1px 8px; border-radius: 9999px; min-width: 34px; text-align: center; }
    .tc-cx-badge.pass { background: var(--status-success-bg); color: var(--status-success-fg); }
    .tc-cx-badge.fail { background: var(--status-error-bg); color: var(--status-error-fg); }
"""

data_script = "  <script>window.RRW = " + json.dumps(DATA) + ";</script>"

editor_js = r"""  <script>
  (function () {
    var root = document.documentElement;
    var D = window.RRW;
    function clone(o) { return JSON.parse(JSON.stringify(o)); }
    var model = { prims: clone(D.prims), semL: clone(D.semLight), semD: clone(D.semDark) };
    var mode = "light";
    var dirty = false;

    function semMap() { return mode === "dark" ? model.semD : model.semL; }
    function norm6(v) { return /^#[0-9a-fA-F]{3}$/.test(v) ? "#" + v[1]+v[1]+v[2]+v[2]+v[3]+v[3] : v; }

    // ---- apply the whole model as inline :root overrides for the active mode ----
    function applyActive() {
      if (mode === "dark") root.setAttribute("data-theme", "dark");
      else root.removeAttribute("data-theme");
      D.primOrder.forEach(function (p) { root.style.setProperty(p, model.prims[p]); });
      var m = semMap();
      Object.keys(m).forEach(function (s) { root.style.setProperty(s, "var(" + m[s] + ")"); });
      refreshInputs(); refreshSeeds(); refreshRemaps(); updateContrast(); status();
    }

    // ---- WCAG contrast ----
    function hexRgb(h) { h = norm6(h).replace("#", ""); return [0,2,4].map(function(i){return parseInt(h.slice(i,i+2),16);}); }
    function relLum(h) { var c = hexRgb(h).map(function (v){ v/=255; return v<=0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055,2.4); }); return 0.2126*c[0]+0.7152*c[1]+0.0722*c[2]; }
    function contrast(a,b){ var x=relLum(a)+0.05, y=relLum(b)+0.05; return x>y ? x/y : y/x; }
    function isSem(t) { return D.semLight[t] != null; }
    // follow the map chain to a primitive: semantic -> (semantic|primitive) -> ... -> hex.
    function resolve(sem) {
      var m = semMap(), seen = {}, cur = sem;
      for (var i = 0; i < 24; i++) {
        if (model.prims[cur] != null) return model.prims[cur];  // reached a primitive
        if (m[cur] == null || seen[cur]) return null;           // unmapped or cycle
        seen[cur] = 1; cur = m[cur];
      }
      return null;
    }
    function updateContrast() {
      document.querySelectorAll(".tc-cx").forEach(function (row) {
        var fg = resolve(row.getAttribute("data-fg")), bg = resolve(row.getAttribute("data-bg"));
        if (!fg || !bg) return;
        var r = contrast(fg, bg), pass = r >= 4.5;
        row.querySelector(".tc-cx-ratio").textContent = r.toFixed(2) + ":1";
        var b = row.querySelector(".tc-cx-badge");
        b.textContent = pass ? "AA" : "AA ✗"; b.className = "tc-cx-badge " + (pass ? "pass" : "fail");
      });
    }

    // ---- OKLCH <-> sRGB (Bjorn Ottosson) for seed family shifts ----
    function s2l(c){ c/=255; return c<=0.04045 ? c/12.92 : Math.pow((c+0.055)/1.055,2.4); }
    function l2s(c){ c = c<=0.0031308 ? c*12.92 : 1.055*Math.pow(c,1/2.4)-0.055; return Math.round(Math.min(1,Math.max(0,c))*255); }
    function rgb2oklch(hex){ hex=norm6(hex); var r=s2l(parseInt(hex.slice(1,3),16)),g=s2l(parseInt(hex.slice(3,5),16)),b=s2l(parseInt(hex.slice(5,7),16));
      var l=Math.cbrt(0.4122214708*r+0.5363325363*g+0.0514459929*b), m=Math.cbrt(0.2119034982*r+0.6806995451*g+0.1073969566*b), s=Math.cbrt(0.0883024619*r+0.2817188376*g+0.6299787005*b);
      var L=0.2104542553*l+0.7936177850*m-0.0040720468*s, A=1.9779984951*l-2.4285922050*m+0.4505937099*s, B=0.0259040371*l+0.7827717662*m-0.8086757660*s;
      var H=Math.atan2(B,A)*180/Math.PI; if(H<0)H+=360; return {L:L,C:Math.sqrt(A*A+B*B),H:H}; }
    function oklch2rgb(o){ var h=o.H*Math.PI/180,A=o.C*Math.cos(h),B=o.C*Math.sin(h),L=o.L;
      var l=L+0.3963377774*A+0.2158037573*B, m=L-0.1055613458*A-0.0638541728*B, s=L-0.0894841775*A-1.2914855480*B; l=l*l*l;m=m*m*m;s=s*s*s;
      var r=4.0767416621*l-3.3077115913*m+0.2309699292*s, g=-1.2684380046*l+2.6097574011*m-0.3413193965*s, b=-0.0041960863*l-0.7034186147*m+1.7076147010*s;
      return "#"+[r,g,b].map(function(v){return ("0"+l2s(v).toString(16)).slice(-2);}).join(""); }
    function clamp(v,a,b){ return Math.max(a,Math.min(b,v)); }

    function shiftFamily(fam, newHex) {
      var f = D.families[fam], old = rgb2oklch(model.prims[f.anchor]), nw = rgb2oklch(newHex);
      var dL = nw.L-old.L, dC = nw.C-old.C, dH = nw.H-old.H;
      f.members.forEach(function (t) {
        var hex;
        if (t === f.anchor) { hex = newHex; }
        else {
          var o = rgb2oklch(model.prims[t]);
          var room = 1 - Math.abs(2*o.L - 1);   // taper near black/white to avoid clipping
          hex = oklch2rgb({ L: clamp(o.L + dL*room, 0, 1), C: Math.max(0, o.C + dC*room), H: ((o.H+dH)%360+360)%360 });
        }
        model.prims[t] = hex; root.style.setProperty(t, hex);
      });
      dirty = true; refreshInputs(); refreshSeeds(); updateContrast(); status();
    }

    function setPrim(name, v) { model.prims[name] = v; root.style.setProperty(name, v); dirty = true; refreshSeeds(); updateContrast(); status(); }

    // ---- refresh UI from model ----
    function refreshInputs() {
      document.querySelectorAll(".tc-chip").forEach(function (c) {
        var n = c.getAttribute("data-prim"), v = model.prims[n]; if (v == null) return;
        c.querySelector(".tc-hex").value = v; var c6 = norm6(v);
        if (/^#[0-9a-fA-F]{6}$/.test(c6)) c.querySelector(".tc-color").value = c6;
      });
    }
    function refreshSeeds() {
      document.querySelectorAll(".tc-seed").forEach(function (el) {
        var a = D.families[el.getAttribute("data-fam")].anchor, c6 = norm6(model.prims[a]);
        if (/^#[0-9a-fA-F]{6}$/.test(c6)) el.querySelector(".tc-seed-color").value = c6;
      });
    }
    function markCoupled(r, s) {
      var c = isSem(model.semL[s]) || isSem(model.semD[s]);
      r.classList.toggle("is-coupled", c);
      var el = r.querySelector(".tc-coupled"); if (el) el.hidden = !c;
    }
    function refreshRemaps() {
      document.querySelectorAll(".tc-remap").forEach(function (r) {
        var s = r.getAttribute("data-sem");
        r.querySelector('select[data-mode="light"]').value = model.semL[s];
        r.querySelector('select[data-mode="dark"]').value = model.semD[s];
        markCoupled(r, s);
      });
    }
    function status() {
      var el = document.querySelector("[data-status]");
      if (el) el.innerHTML = "Editing <strong>" + mode + "</strong> · " + (dirty ? "unsaved changes" : "no changes");
      renderSelected();
    }

    // ---- wiring ----
    document.querySelectorAll(".tc-chip").forEach(function (c) {
      var n = c.getAttribute("data-prim"), col = c.querySelector(".tc-color"), hex = c.querySelector(".tc-hex");
      col.addEventListener("input", function () { hex.value = col.value; setPrim(n, col.value); });
      hex.addEventListener("change", function () {
        var v = hex.value.trim();
        if (/^#[0-9a-fA-F]{3,8}$/.test(v)) { setPrim(n, v); var c6 = norm6(v); if (/^#[0-9a-fA-F]{6}$/.test(c6)) col.value = c6; }
        else { hex.value = model.prims[n]; }
      });
    });
    document.querySelectorAll(".tc-seed").forEach(function (el) {
      var fam = el.getAttribute("data-fam");
      el.querySelector(".tc-seed-color").addEventListener("input", function () { shiftFamily(fam, this.value); });
    });
    document.querySelectorAll(".tc-remap").forEach(function (r) {
      var s = r.getAttribute("data-sem");
      r.querySelectorAll(".tc-sel").forEach(function (sel) {
        sel.addEventListener("change", function () {
          var tgt = sel.getAttribute("data-mode") === "dark" ? model.semD : model.semL;
          tgt[s] = sel.value;
          if (sel.getAttribute("data-mode") === mode) root.style.setProperty(s, "var(" + sel.value + ")");
          dirty = true; updateContrast(); status(); markCoupled(r, s);
          r.querySelector(".tc-swatch").style.background = "var(" + s + ")";
        });
      });
    });

    var seg = document.querySelectorAll(".ph-seg button");
    seg.forEach(function (b) {
      b.addEventListener("click", function () {
        mode = b.getAttribute("data-set");
        seg.forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
        applyActive();
      });
    });

    document.querySelectorAll("[data-act]").forEach(function (el) {
      var act = el.getAttribute("data-act");
      if (act === "defaults") el.addEventListener("click", function () {
        model = { prims: clone(D.prims), semL: clone(D.semLight), semD: clone(D.semDark) }; dirty = false; applyActive();
      });
      if (act === "export") el.addEventListener("click", function () {
        var out = JSON.stringify({ version: 2, primitives: model.prims, semantic: { light: model.semL, dark: model.semD } }, null, 2);
        var a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([out], { type: "application/json" }));
        a.download = "rrw-theme.json"; document.body.appendChild(a); a.click();
        setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 0);
      });
      if (act === "import") el.addEventListener("change", function () {
        var f = el.files[0]; if (!f) return; var r = new FileReader();
        r.onload = function () {
          try {
            var j = JSON.parse(r.result);
            if (j.primitives && j.semantic) {
              model = { prims: clone(j.primitives), semL: clone(j.semantic.light), semD: clone(j.semantic.dark) };
              dirty = true; applyActive();
            } else { alert("JSON needs { primitives, semantic: { light, dark } }."); }
          } catch (e) { alert("Bad JSON: " + e); }
          el.value = "";
        };
        r.readAsText(f);
      });
    });

    // ---- Part C: click a preview element -> reflect its token + primitive + co-users ----
    var partA = document.querySelector(".tc-part-a");
    var cBody = document.querySelector("[data-c-body]");
    var selectedTi = null;

    // token -> [{el, f}] across every registered facet (drives "also uses")
    var tokenUsers = {};
    (D.targets || []).forEach(function (t) {
      t.facets.forEach(function (f) { (tokenUsers[f.token] = tokenUsers[f.token] || []).push({ el: t.el, f: f.f }); });
    });

    function esc(s) { return String(s).replace(/[&<>]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]; }); }
    function propLabel(p) { return p === "bg" ? "background" : p === "fg" ? "text colour" : "border colour"; }

    // follow the active-theme map from a semantic token to its primitive
    function resolvePrimChain(token) {
      var m = semMap(), chain = [], seen = {}, cur = m[token];
      while (cur != null && chain.length < 24) {
        chain.push(cur);
        if (model.prims[cur] != null) return { chain: chain, prim: cur, hex: model.prims[cur] };
        if (seen[cur]) break;
        seen[cur] = 1; cur = m[cur];
      }
      return { chain: chain, prim: null, hex: null };
    }

    function renderC(ti) {
      var t = D.targets[ti];
      var html = '<p class="tc-c-el">' + esc(t.el) + "</p>"
        + '<p class="tc-c-sub">' + t.facets.length + " colour facet" + (t.facets.length > 1 ? "s" : "")
        + " · editing <strong>" + mode + "</strong> · click another element to change</p>";
      t.facets.forEach(function (f) {
        var r = resolvePrimChain(f.token);
        var users = (tokenUsers[f.token] || []).filter(function (u) { return !(u.el === t.el && u.f === f.f); });
        var via = r.chain.length > 1
          ? '<span class="tc-c-chain"> (via ' + r.chain.slice(0, -1).map(function (c) { return "<code>" + esc(c) + "</code>"; }).join(" → ") + ")</span>"
          : "";
        html += '<div class="tc-facet">'
          + '<div class="tc-facet-h"><span class="tc-c-swatch" style="background: var(' + f.token + ')"></span>'
          + '<span class="tc-facet-name">' + esc(f.f) + '</span> <span class="tc-facet-prop">' + propLabel(f.prop) + "</span></div>"
          + '<dl class="tc-c-row">'
          + "<dt>token</dt><dd><code>" + esc(f.token) + "</code></dd>"
          + "<dt>primitive</dt><dd>"
          + (r.prim ? "<code>" + esc(r.prim) + '</code><span class="tc-c-hex">' + esc(r.hex) + "</span>" + via
                    : '<span class="tc-c-none">unresolved</span>')
          + "</dd>"
          + "<dt>also uses</dt><dd>"
          + (users.length
              ? '<ul class="tc-c-users">' + users.map(function (u) { return "<li>" + esc(u.el) + " · " + esc(u.f) + "</li>"; }).join("") + "</ul>"
              : '<span class="tc-c-none">nothing else</span>')
          + "</dd></dl></div>";
      });
      cBody.innerHTML = html;
    }

    function renderSelected() { if (selectedTi != null && cBody) renderC(selectedTi); }

    function selectTarget(ti, node) {
      if (partA) partA.querySelectorAll(".tc-picked").forEach(function (n) { n.classList.remove("tc-picked"); });
      node.classList.add("tc-picked");
      selectedTi = ti;
      renderC(ti);
    }

    (D.targets || []).forEach(function (t, ti) {
      if (!partA) return;
      partA.querySelectorAll(t.sel).forEach(function (node) {
        node.classList.add("tc-pickable");
        node.addEventListener("click", function (ev) { ev.preventDefault(); ev.stopPropagation(); selectTarget(ti, node); });
      });
    });

    applyActive();
  })();
  </script>"""

part_a = (
    '  <div class="tc-part tc-part-a">\n'
    '    <h2 class="tc-part-h">Part A — Preview <span class="tc-part-note">(screen elements; colour-picking to come)</span></h2>\n'
    + hc.component_gallery()
    + "\n  </div>"
)
part_b = (
    '  <div class="tc-part tc-part-b">\n'
    '    <h2 class="tc-part-h">Part B — Tokens</h2>\n'
    + seeds_section + "\n"
    + prim_section + "\n"
    + contrast_section + "\n"
    + sem_section
    + "\n  </div>"
)
part_c = (
    '  <div class="tc-part tc-part-c">\n'
    '    <h2 class="tc-part-h">Part C — Selection <span class="tc-part-note">(click a preview element)</span></h2>\n'
    '    <div class="tc-c-body" data-c-body>\n'
    '      <p class="tc-c-placeholder">Click any coloured element in Part A to see which semantic token '
    "paints it, which primitive that token resolves to, and what else the token covers.</p>\n"
    "    </div>\n"
    "  </div>"
)

body = (
    toolbar
    + '\n\n  <div class="tc-cols">\n'
    + '  <div class="tc-left">\n'
    + part_a + "\n"
    + part_b + "\n"
    + "  </div>\n"
    + part_c
    + "\n  </div>\n\n"
    + data_script + "\n"
    + editor_js + "\n"
)

html = hc.page(
    "Review Robin — two-tier theme customizer",
    "tools/theme_customizer.gen.py",
    base_css,
    editor_css,
    body,
)
OUT.write_text(html, encoding="utf-8")
print(f"Wrote {OUT.relative_to(ROOT)} ({len(html)} bytes, {len(prims)} primitives, "
      f"{len(SEED_ORDER)} seeds, {sum(len(t) for _, t in clusters)} semantic remaps)")

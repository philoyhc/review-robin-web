#!/usr/bin/env python3
"""Generate tools/theme_customizer.html — a standalone theme *designer*.

Plan A ("First") of guide/theme_customizer.md, slice 1 (manual editor). Lifts
base.html's real palette + component gallery (shared via _harness_common) and
makes every colour token editable, repainting the whole gallery live. Design a
light + dark palette here, then Export JSON — a coding agent ports its flat
`tokens` map 1:1 into base.html's :root / :root[data-theme="dark"] blocks.

Controls: Light/Dark (edit each theme separately) · Load defaults / Re-read
base.html… (File-picker) · Save as… / a named-save library (localStorage) /
Delete · Export JSON / Import JSON.

Later slices (per the plan): contrast (AA) badges, then seeds + OKLCH
derivation. Regenerate after any base.html change:
  python3 tools/theme_customizer.gen.py
Not production code; not wired into the app.
"""
import json
import pathlib

import _harness_common as hc

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = ROOT / "app/web/templates/base.html"
OUT = ROOT / "tools/theme_customizer.html"

base_css = hc.lift_base_style(BASE.read_text(encoding="utf-8"))
order = [n for n, _ in hc.parse_light_tokens(base_css)]  # :root declaration order
theme = hc.parse_theme_tokens(base_css)                  # {"light": {...}, "dark": {...}}


def chip(n):
    """One editable token chip (color-picker + hex + name), initialised to the
    light value; the JS re-syncs inputs to the active theme's model on toggle."""
    return (
        f'        <div class="tc-chip" data-token="{n}">'
        f'<input type="color" class="tc-color" value="{theme["light"].get(n, "#000000")}" aria-label="{n} colour">'
        f'<input type="text" class="tc-hex" value="{theme["light"].get(n, "")}" spellcheck="false" aria-label="{n} hex">'
        f'<span class="tc-name">{n}</span></div>'
    )


def chip_grid(names):
    return '<div class="tc-grid">\n' + "\n".join(chip(n) for n in names) + "\n      </div>"


# Tokens that colour body text, links, and the page / card / muted surfaces —
# hoisted into the first content zone (the "Text, links & background" section)
# so they sit with the components they drive, instead of the flat grid below.
TEXT_ZONE_TOKENS = [
    "--bg-page", "--bg-card", "--bg-muted",
    "--text-primary", "--text-secondary", "--text-muted",
    "--accent-blue",  # the link colour (a { color: var(--accent-blue) })
]
rest_tokens = [n for n in order if n not in set(TEXT_ZONE_TOKENS)]

# Seeds — shift a whole colour family in OKLCH from one control (slice 3). Each
# seed's "anchor" token displays the family's current colour; moving it applies
# the same OKLCH delta to every member, preserving the palette's tuned
# relationships (no base.html re-tune needed — the shift is *relative*).
FAMILIES = {
    "blue": {"label": "Blue · primary", "anchor": "--accent-blue", "members": [
        "--accent-blue", "--accent-blue-bg", "--accent-blue-bg-soft",
        "--accent-blue-bg-faint", "--accent-blue-light", "--accent-blue-dark",
        "--accent-blue-marker", "--accent-blue-strong"]},
    "green": {"label": "Green · success", "anchor": "--accent-green", "members": [
        "--accent-green", "--accent-green-bg", "--accent-green-marker",
        "--accent-green-text", "--accent-green-bg-faint"]},
    "amber": {"label": "Amber · Alert", "anchor": "--accent-amber", "members": [
        "--accent-amber", "--accent-amber-bg", "--accent-amber-bg-mid",
        "--accent-amber-dark", "--accent-amber-border"]},
    "red": {"label": "Red · destructive", "anchor": "--accent-red", "members": [
        "--accent-red", "--accent-red-bg", "--accent-red-soft",
        "--accent-red-strong", "--accent-red-text",
        "--danger-bg", "--danger-border", "--danger-text"]},
    "violet": {"label": "Violet", "anchor": "--accent-violet-text", "members": [
        "--accent-violet-bg", "--accent-violet-text"]},
    "sky": {"label": "Sky · config", "anchor": "--accent-sky-text", "members": [
        "--accent-sky-bg", "--accent-sky-text"]},
}
seed_swatches = "\n".join(
    f'        <label class="tc-seed" data-family="{k}">'
    f'<input type="color" class="tc-seed-color" value="{theme["light"].get(f["anchor"], "#000000")}" aria-label="{f["label"]} seed">'
    f'<span>{f["label"]}</span></label>'
    for k, f in FAMILIES.items()
)
seeds_section = f"""    <section class="ph-section">
      <h2 class="ph-h">Seeds — shift a whole colour family (hue / lightness / chroma, OKLCH) from one control. The per-token grid below still overrides individual tokens.</h2>
      <div class="tc-seed-row">
{seed_swatches}
      </div>
    </section>"""

# Contrast (AA) — representative foreground/background pairs. WCAG AA for normal
# text is 4.5:1; the tool shows the live ratio + pass/fail per pair, per the
# ACTIVE theme, updating as tokens change. (Slice 2.)
PAIRS = [
    ("Body text", "--text-primary", "--bg-page"),
    ("Card text", "--text-primary", "--bg-card"),
    ("Secondary / page", "--text-secondary", "--bg-page"),
    ("Secondary / card", "--text-secondary", "--bg-card"),
    ("Muted / card", "--text-muted", "--bg-card"),
    ("Link", "--accent-blue", "--bg-page"),
    ("Primary button", "--text-on-accent", "--accent-blue"),
    ("Alert button", "--text-on-amber", "--accent-amber-dark"),
    ("Destructive (outline)", "--accent-red", "--bg-page"),
    ("Pill · error", "--accent-red-text", "--accent-red-bg"),
    ("Pill · warning", "--accent-amber-dark", "--accent-amber-bg"),
    ("Pill · info", "--accent-blue-strong", "--accent-blue-bg"),
    ("Pill · success", "--accent-green-text", "--accent-green-bg"),
    ("Pill · super", "--accent-violet-text", "--accent-violet-bg"),
    ("Config value (sky)", "--accent-sky-text", "--accent-sky-bg"),
    ("Soft error", "--danger-text", "--danger-bg"),
]
contrast_rows = "\n".join(
    f'        <div class="tc-cx" data-fg="{fg}" data-bg="{bg}" data-min="4.5">'
    f'<span class="tc-cx-sample" style="background: var({bg}); color: var({fg})">Aa — {label}</span>'
    f'<span class="tc-cx-ratio">—</span><span class="tc-cx-badge">—</span></div>'
    for label, fg, bg in PAIRS
)
contrast_section = f"""    <section class="ph-section">
      <h2 class="ph-h">Contrast (AA) — live WCAG ratio per bg/text pair, ACTIVE theme (target 4.5:1)</h2>
      <div class="tc-cx-grid">
{contrast_rows}
      </div>
    </section>"""

editor_css = r"""
    .tc-controls { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .tc-controls button, .tc-controls label.tc-file {
      font: inherit; font-size: 0.8em; cursor: pointer; padding: 3px 10px;
      border-radius: 6px; border: 1px solid var(--border-default);
      background: var(--bg-page); color: var(--text-primary);
    }
    .tc-controls input[type=file] { display: none; }
    .tc-controls select { font: inherit; font-size: 0.8em; padding: 3px 6px;
      border: 1px solid var(--border-default); border-radius: 6px;
      background: var(--bg-page); color: var(--text-primary); }
    .tc-sep { width: 1px; height: 20px; background: var(--border-default); }
    .tc-status { color: var(--text-secondary); font-size: 0.8rem; }
    .tc-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 8px; }
    .tc-zone-tokens { margin-top: 18px; padding-top: 14px; border-top: 1px dashed var(--border-subtle); }
    .tc-chip { display: flex; align-items: center; gap: 8px;
      border: 1px solid var(--border-subtle); border-radius: 8px; padding: 6px 8px; }
    .tc-color { width: 34px; height: 26px; padding: 0; border: 1px solid var(--border-default);
      border-radius: 4px; background: none; cursor: pointer; flex: none; }
    .tc-seed-row { display: flex; flex-wrap: wrap; gap: 14px; }
    .tc-seed { display: inline-flex; align-items: center; gap: 6px; cursor: pointer;
      font-size: 0.85rem; }
    .tc-seed-color { width: 30px; height: 26px; padding: 0;
      border: 1px solid var(--border-default); border-radius: 6px;
      background: none; cursor: pointer; }
    .tc-hex { width: 76px; font-family: ui-monospace, monospace; font-size: 0.72rem;
      padding: 2px 4px; }
    .tc-name { font-family: ui-monospace, monospace; font-size: 0.68rem;
      color: var(--text-secondary); word-break: break-all; }
    .tc-cx-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 8px; }
    .tc-cx { display: flex; align-items: center; gap: 8px; }
    .tc-cx-sample { flex: 1; padding: 4px 10px; border-radius: 6px;
      border: 1px solid var(--border-subtle); font-size: 0.8rem; white-space: nowrap;
      overflow: hidden; text-overflow: ellipsis; }
    .tc-cx-ratio { font-family: ui-monospace, monospace; font-size: 0.72rem;
      color: var(--text-secondary); min-width: 58px; text-align: right; }
    .tc-cx-badge { font-size: 0.66rem; font-weight: 600; padding: 1px 8px;
      border-radius: 9999px; min-width: 34px; text-align: center; }
    .tc-cx-badge.pass { background: var(--accent-green-bg); color: var(--accent-green-text); }
    .tc-cx-badge.fail { background: var(--accent-red-bg); color: var(--accent-red-text); }
"""

toolbar = """  <div class="ph-toolbar">
    <strong>Theme customizer</strong>
    <span class="ph-seg" role="group" aria-label="Theme">
      <button data-set="light" aria-pressed="true">Light</button>
      <button data-set="dark" aria-pressed="false">Dark</button>
    </span>
    <span class="tc-controls">
      <button data-act="defaults">Load defaults</button>
      <label class="tc-file">Re-read base.html…<input type="file" accept=".html,text/html" data-act="reread"></label>
      <span class="tc-sep"></span>
      <button data-act="save">Save as…</button>
      <select data-act="library" aria-label="Saved themes"><option value="">— saved —</option></select>
      <button data-act="delete">Delete</button>
      <span class="tc-sep"></span>
      <button data-act="export">Export JSON</button>
      <label class="tc-file">Import JSON…<input type="file" accept=".json,application/json" data-act="import"></label>
    </span>
    <span class="tc-status" data-status>Editing <strong>light</strong> · no changes</span>
  </div>"""

# First content zone: text / links / background. The sample markup (shared with
# the preview) sits with the very tokens that colour it, per the zone-by-zone
# reorg — text / link / bg tokens live here, not in the flat grid below.
text_zone = f"""    <section class="ph-section">
      <h2 class="ph-h">Text, links &amp; background — the tokens here colour body text, links, and the page / card / muted surfaces. Edit the ACTIVE theme.</h2>
{hc.TEXT_LINKS_SAMPLE}
      <div class="tc-zone-tokens">
        {chip_grid(TEXT_ZONE_TOKENS)}
      </div>
    </section>"""

# Remaining tokens — everything not yet hoisted into a dedicated zone.
editor_section = f"""    <section class="ph-section">
      <h2 class="ph-h">Other colour tokens ({len(rest_tokens)}) — text / link / background tokens now live in the first zone; edit the rest here. Switch Light/Dark to edit the other palette.</h2>
      <div class="tc-grid">
{chr(10).join(chip(n) for n in rest_tokens)}
      </div>
    </section>"""

# The gallery sections minus `text` (hoisted into text_zone above), in order.
gallery_rest = "\n\n".join(
    html for key, html in hc.component_sections() if key != "text"
)

defaults_script = (
    "  <script>window.RRW_DEFAULTS = " + json.dumps(theme) + ";"
    " window.RRW_FAMILIES = " + json.dumps(FAMILIES) + ";</script>"
)

editor_js = r"""  <script>
    (function () {
      var root = document.documentElement;
      var DEFAULTS = window.RRW_DEFAULTS;      // { light: {..}, dark: {..} }
      var FAMILIES = window.RRW_FAMILIES;      // { fam: { anchor, members } }
      var model = clone(DEFAULTS);
      var mode = "light";
      var dirty = false;
      var LIB_KEY = "rrw-theme-designs";

      function clone(o) { return JSON.parse(JSON.stringify(o)); }
      function chips() { return document.querySelectorAll(".tc-chip"); }
      function norm6(v) {
        return /^#[0-9a-fA-F]{3}$/.test(v)
          ? "#" + v[1] + v[1] + v[2] + v[2] + v[3] + v[3] : v;
      }
      function hexRgb(h) {
        h = h.replace("#", "");
        if (h.length === 3) h = h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
        return [parseInt(h.slice(0,2),16), parseInt(h.slice(2,4),16), parseInt(h.slice(4,6),16)];
      }
      function relLum(h) {
        var c = hexRgb(h).map(function (v) {
          v /= 255; return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4);
        });
        return 0.2126*c[0] + 0.7152*c[1] + 0.0722*c[2];
      }
      function contrast(fg, bg) {
        var a = relLum(fg)+0.05, b = relLum(bg)+0.05;
        return a > b ? a/b : b/a;
      }
      function updateContrast() {
        document.querySelectorAll(".tc-cx").forEach(function (row) {
          var fg = model[mode][row.getAttribute("data-fg")];
          var bg = model[mode][row.getAttribute("data-bg")];
          if (!fg || !bg) return;
          var r = contrast(fg, bg), min = parseFloat(row.getAttribute("data-min"));
          row.querySelector(".tc-cx-ratio").textContent = r.toFixed(2) + ":1";
          var badge = row.querySelector(".tc-cx-badge"), pass = r >= min;
          badge.textContent = pass ? "AA" : "AA ✗";
          badge.className = "tc-cx-badge " + (pass ? "pass" : "fail");
        });
      }

      // --- OKLCH ↔ sRGB (Björn Ottosson) for the seed family-shift ---
      function srgb2lin(c) { c /= 255; return c <= 0.04045 ? c/12.92 : Math.pow((c+0.055)/1.055, 2.4); }
      function lin2srgb(c) {
        c = c <= 0.0031308 ? c*12.92 : 1.055*Math.pow(c, 1/2.4) - 0.055;
        return Math.round(Math.min(1, Math.max(0, c)) * 255);
      }
      function rgb2oklch(hex) {
        hex = norm6(hex);
        var r = srgb2lin(parseInt(hex.slice(1,3),16)),
            g = srgb2lin(parseInt(hex.slice(3,5),16)),
            b = srgb2lin(parseInt(hex.slice(5,7),16));
        var l = Math.cbrt(0.4122214708*r + 0.5363325363*g + 0.0514459929*b),
            m = Math.cbrt(0.2119034982*r + 0.6806995451*g + 0.1073969566*b),
            s = Math.cbrt(0.0883024619*r + 0.2817188376*g + 0.6299787005*b);
        var L = 0.2104542553*l + 0.7936177850*m - 0.0040720468*s,
            A = 1.9779984951*l - 2.4285922050*m + 0.4505937099*s,
            B = 0.0259040371*l + 0.7827717662*m - 0.8086757660*s;
        var H = Math.atan2(B, A) * 180/Math.PI; if (H < 0) H += 360;
        return { L: L, C: Math.sqrt(A*A + B*B), H: H };
      }
      function oklch2rgb(o) {
        var h = o.H * Math.PI/180, A = o.C*Math.cos(h), B = o.C*Math.sin(h), L = o.L;
        var l = L + 0.3963377774*A + 0.2158037573*B,
            m = L - 0.1055613458*A - 0.0638541728*B,
            s = L - 0.0894841775*A - 1.2914855480*B;
        l = l*l*l; m = m*m*m; s = s*s*s;
        var r = 4.0767416621*l - 3.3077115913*m + 0.2309699292*s,
            g = -1.2684380046*l + 2.6097574011*m - 0.3413193965*s,
            b = -0.0041960863*l - 0.7034186147*m + 1.7076147010*s;
        return "#" + [r, g, b].map(function (v) {
          return ("0" + lin2srgb(v).toString(16)).slice(-2);
        }).join("");
      }
      function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

      // Shift a whole family by the OKLCH delta between the seed's old and new
      // value — preserves each member's relationship to the anchor (a bg stays
      // a pale tint, text stays dark), just re-hued / re-lightened together.
      function shiftFamily(fam, newHex) {
        var f = FAMILIES[fam], old = rgb2oklch(model[mode][f.anchor]),
            nw = rgb2oklch(newHex);
        var dL = nw.L - old.L, dC = nw.C - old.C, dH = nw.H - old.H;
        f.members.forEach(function (t) {
          var hex;
          if (t === f.anchor) {
            hex = newHex;  // the seed IS the anchor (WYSIWYG)
          } else {
            var o = rgb2oklch(model[mode][t]);
            // Taper the lightness / chroma delta near black & white so already-
            // extreme members (pale bg tints, dark text) don't clip; hue rotates
            // fully so the whole family re-hues together.
            var room = 1 - Math.abs(2 * o.L - 1);
            hex = oklch2rgb({
              L: clamp(o.L + dL * room, 0, 1),
              C: Math.max(0, o.C + dC * room),
              H: ((o.H + dH) % 360 + 360) % 360
            });
          }
          model[mode][t] = hex; root.style.setProperty(t, hex);
        });
        dirty = true;
        refreshInputs(); refreshSeeds(); updateContrast(); status();
      }
      function refreshSeeds() {
        document.querySelectorAll(".tc-seed").forEach(function (el) {
          var f = FAMILIES[el.getAttribute("data-family")];
          var c6 = norm6(model[mode][f.anchor]);
          if (/^#[0-9a-fA-F]{6}$/.test(c6)) el.querySelector(".tc-seed-color").value = c6;
        });
      }
      function refreshInputs() {
        chips().forEach(function (c) {
          var t = c.getAttribute("data-token"), v = model[mode][t];
          if (v == null) return;
          c.querySelector(".tc-hex").value = v;
          var c6 = norm6(v);
          if (/^#[0-9a-fA-F]{6}$/.test(c6)) c.querySelector(".tc-color").value = c6;
        });
      }
      function status() {
        var el = document.querySelector("[data-status]");
        if (el) el.innerHTML = "Editing <strong>" + mode + "</strong> · "
          + (dirty ? "unsaved changes" : "no changes");
      }
      function applyActive() {
        if (mode === "dark") root.setAttribute("data-theme", "dark");
        else root.removeAttribute("data-theme");
        var m = model[mode];
        Object.keys(m).forEach(function (t) { root.style.setProperty(t, m[t]); });
        refreshInputs(); refreshSeeds(); status(); updateContrast();
      }
      function setToken(t, v) {
        model[mode][t] = v; root.style.setProperty(t, v); dirty = true;
        refreshSeeds(); status(); updateContrast();
      }

      // --- localStorage save library ---
      function loadLib() {
        try { return JSON.parse(localStorage.getItem(LIB_KEY) || "{}"); }
        catch (e) { return {}; }
      }
      function saveLib(l) {
        try { localStorage.setItem(LIB_KEY, JSON.stringify(l)); } catch (e) {}
      }
      function refreshLibrary(sel) {
        var l = loadLib(), cur = sel.value;
        sel.innerHTML = '<option value="">— saved —</option>';
        Object.keys(l).sort().forEach(function (n) {
          var o = document.createElement("option"); o.value = n; o.textContent = n;
          sel.appendChild(o);
        });
        sel.value = cur;
      }

      function download(name, text) {
        var blob = new Blob([text], { type: "application/json" });
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob); a.download = name;
        document.body.appendChild(a); a.click();
        setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 0);
      }

      // Parse a base.html file's :root blocks in the browser. Anchor on the
      // <style> TAG at line start (same trap as the Python generator: prose
      // mentions of "<style>" in head comments would otherwise be grabbed).
      function parseBaseHtml(text) {
        var m = text.match(/^[ \t]*<style>[ \t]*\n([\s\S]*?)<\/style>/m);
        var css = m ? m[1] : "";
        function block(re) {
          var b = css.match(re), d = {};
          if (b) {
            var rx = /(--[a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8});/g, mm;
            while ((mm = rx.exec(b[1]))) d[mm[1]] = mm[2];
          }
          return d;
        }
        return {
          light: block(/:root\s*\{([\s\S]*?)\}/),
          dark: block(/:root\[data-theme="dark"\]\s*\{([\s\S]*?)\}/)
        };
      }

      // --- wire the token chips ---
      chips().forEach(function (c) {
        var t = c.getAttribute("data-token");
        var color = c.querySelector(".tc-color"), hex = c.querySelector(".tc-hex");
        color.addEventListener("input", function () {
          hex.value = color.value; setToken(t, color.value);
        });
        hex.addEventListener("change", function () {
          var v = hex.value.trim();
          if (/^#[0-9a-fA-F]{3,8}$/.test(v)) {
            setToken(t, v);
            var c6 = norm6(v);
            if (/^#[0-9a-fA-F]{6}$/.test(c6)) color.value = c6;
          } else { hex.value = model[mode][t]; }
        });
      });

      // --- seed controls (family shift) ---
      document.querySelectorAll(".tc-seed").forEach(function (el) {
        var fam = el.getAttribute("data-family");
        el.querySelector(".tc-seed-color").addEventListener("input", function () {
          shiftFamily(fam, this.value);
        });
      });

      // --- toolbar ---
      var seg = document.querySelectorAll(".ph-seg button");
      seg.forEach(function (b) {
        b.addEventListener("click", function () {
          mode = b.getAttribute("data-set");
          seg.forEach(function (x) {
            x.setAttribute("aria-pressed", x === b ? "true" : "false");
          });
          applyActive();
        });
      });

      var lib = document.querySelector('[data-act="library"]');
      document.querySelectorAll("[data-act]").forEach(function (el) {
        var act = el.getAttribute("data-act");
        if (act === "defaults") el.addEventListener("click", function () {
          model = clone(DEFAULTS); dirty = false; applyActive();
        });
        if (act === "reread") el.addEventListener("change", function () {
          var f = el.files[0]; if (!f) return;
          var r = new FileReader();
          r.onload = function () {
            try {
              var p = parseBaseHtml(r.result);
              if (Object.keys(p.light).length) {
                DEFAULTS = p; model = clone(p); dirty = false; applyActive();
              } else { alert("No :root tokens found in that file."); }
            } catch (e) { alert("Couldn't parse base.html: " + e); }
            el.value = "";
          };
          r.readAsText(f);
        });
        if (act === "save") el.addEventListener("click", function () {
          var n = prompt("Save theme as:"); if (!n) return;
          var l = loadLib(); l[n] = clone(model); saveLib(l);
          refreshLibrary(lib); lib.value = n; dirty = false; status();
        });
        if (act === "library") el.addEventListener("change", function () {
          var n = el.value; if (!n) return;
          var l = loadLib();
          if (l[n]) { model = clone(l[n]); dirty = false; applyActive(); }
        });
        if (act === "delete") el.addEventListener("click", function () {
          var n = lib.value; if (!n) return;
          if (!confirm('Delete saved theme "' + n + '"?')) return;
          var l = loadLib(); delete l[n]; saveLib(l); refreshLibrary(lib);
        });
        if (act === "export") el.addEventListener("click", function () {
          download("rrw-theme.json",
            JSON.stringify({ version: 1, tokens: model }, null, 2));
        });
        if (act === "import") el.addEventListener("change", function () {
          var f = el.files[0]; if (!f) return;
          var r = new FileReader();
          r.onload = function () {
            try {
              var j = JSON.parse(r.result), t = j.tokens || j;
              if (t.light && t.dark) { model = clone(t); dirty = true; applyActive(); }
              else { alert("JSON needs { tokens: { light, dark } }."); }
            } catch (e) { alert("Bad JSON: " + e); }
            el.value = "";
          };
          r.readAsText(f);
        });
      });

      refreshLibrary(lib);
      applyActive();
    })();
  </script>"""

body = (
    toolbar
    + '\n\n  <div class="ph-body">\n'
    + seeds_section
    + "\n"
    + text_zone
    + "\n"
    + gallery_rest
    + "\n"
    + contrast_section
    + "\n"
    + editor_section
    + "\n  </div>\n\n"
    + defaults_script
    + "\n"
    + editor_js
    + "\n"
)

html = hc.page(
    "Review Robin — theme customizer",
    "tools/theme_customizer.gen.py",
    base_css,
    editor_css,
    body,
)
OUT.write_text(html, encoding="utf-8")
print(f"Wrote {OUT.relative_to(ROOT)} ({len(html)} bytes, {len(order)} tokens)")

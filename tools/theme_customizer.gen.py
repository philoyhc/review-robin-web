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

# Editor grid — one chip per token, initialised to the light value (light is the
# opening mode); the JS re-syncs inputs to the active theme's model on toggle.
chips = "\n".join(
    f'        <div class="tc-chip" data-token="{n}">'
    f'<span class="tc-sw" style="background: var({n})"></span>'
    f'<input type="color" class="tc-color" value="{theme["light"].get(n, "#000000")}" aria-label="{n} colour">'
    f'<input type="text" class="tc-hex" value="{theme["light"].get(n, "")}" spellcheck="false" aria-label="{n} hex">'
    f'<span class="tc-name">{n}</span></div>'
    for n in order
)

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
    .tc-chip { display: flex; align-items: center; gap: 8px;
      border: 1px solid var(--border-subtle); border-radius: 8px; padding: 6px 8px; }
    .tc-sw { width: 22px; height: 22px; border-radius: 4px;
      border: 1px solid var(--border-default); flex: none; }
    .tc-color { width: 30px; height: 24px; padding: 0; border: none;
      background: none; cursor: pointer; flex: none; }
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

editor_section = f"""    <section class="ph-section">
      <h2 class="ph-h">Colour tokens ({len(order)}) — edit the ACTIVE theme; the gallery repaints live. Switch Light/Dark to edit the other palette.</h2>
      <div class="tc-grid">
{chips}
      </div>
    </section>"""

defaults_script = "  <script>window.RRW_DEFAULTS = " + json.dumps(theme) + ";</script>"

editor_js = r"""  <script>
    (function () {
      var root = document.documentElement;
      var DEFAULTS = window.RRW_DEFAULTS;      // { light: {..}, dark: {..} }
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
        chips().forEach(function (c) {
          var t = c.getAttribute("data-token"), v = model[mode][t];
          if (v == null) return;
          c.querySelector(".tc-hex").value = v;
          var c6 = norm6(v);
          if (/^#[0-9a-fA-F]{6}$/.test(c6)) c.querySelector(".tc-color").value = c6;
        });
        status();
        updateContrast();
      }
      function setToken(t, v) {
        model[mode][t] = v; root.style.setProperty(t, v); dirty = true;
        status(); updateContrast();
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
    + hc.component_gallery()
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

#!/usr/bin/env python3
"""Generate tools/theme_preview.html — a standalone theme-preview harness.

A faithful, read-only *preview* of base.html's real light/dark palette: lifts
its `<style>` + tokens and renders a component gallery + colour-token swatch
grid. Open the output in a browser; the toolbar flips `data-theme` on <html> to
compare Light / Dark live. To *edit* a palette instead, use
tools/theme_customizer.gen.py.

Regenerate after any base.html style change:  python3 tools/theme_preview.gen.py
Not production code; not wired into the app.
"""
import pathlib

import _harness_common as hc

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = ROOT / "app/web/templates/base.html"
OUT = ROOT / "tools/theme_preview.html"

base_css = hc.lift_base_style(BASE.read_text(encoding="utf-8"))
colour_tokens = hc.parse_light_tokens(base_css)

swatches = "\n".join(
    f'        <div class="ph-chip"><div class="sw" style="background: var({n});"></div>'
    f'<div class="lbl">{n}<br>light {v}</div></div>'
    for n, v in colour_tokens
)

body = f"""  <div class="ph-toolbar">
    <strong>Dark-mode preview</strong>
    <span class="ph-seg" role="group" aria-label="Theme">
      <button data-set="light" aria-pressed="true">Light</button>
      <button data-set="dark" aria-pressed="false">Dark</button>
    </span>
    <span class="ph-note">Faithful live preview of base.html's real light / dark palette. Design tool only — not wired into the app.</span>
  </div>

  <div class="ph-body">
{hc.component_gallery()}
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

html = hc.page(
    "Review Robin — dark-mode preview",
    "tools/theme_preview.gen.py",
    base_css,
    "",  # no extra theme CSS
    body,
)
OUT.write_text(html, encoding="utf-8")
print(f"Wrote {OUT.relative_to(ROOT)} ({len(html)} bytes, {len(colour_tokens)} tokens)")

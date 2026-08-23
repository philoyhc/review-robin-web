#!/usr/bin/env python3
"""Generate tools/theme_preview.html — a standalone, read-only theme preview.

A faithful preview of base.html's real **two-tier** palette: lifts its
`<style>`, renders the component gallery, the Tier-1 primitive swatches
(grouped by hue family), and the Tier-2 semantic tokens by cluster (each with
its light / dark primitive + resolved value). Open the output in a browser; the
toolbar flips `data-theme` on <html> to compare Light / Dark live. To *edit* a
palette, use tools/theme_customizer.gen.py.

Data-driven: the primitives, hue families, and clusters are read from base.html
itself, so this works for any tokens.css of the same shape.

Regenerate after any base.html style change:  python3 tools/theme_preview.gen.py
Not production code; not wired into the app.
"""
import pathlib

import _harness_common as hc

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = ROOT / "app/web/templates/base.html"
OUT = ROOT / "tools/theme_preview.html"

base_css = hc.lift_base_style(BASE.read_text(encoding="utf-8"))
prims = hc.parse_primitives(base_css)            # [(name, hex)]
prim_val = dict(prims)
sem = hc.parse_semantic(base_css)                # {"light": [(sem, prim)], "dark": [...]}
sem_light, sem_dark = dict(sem["light"]), dict(sem["dark"])
clusters = [(n, t) for n, t in hc.parse_clusters(base_css) if t]  # drop 0-token headers

HUE_ORDER = ["neutral", "blue", "sky", "green", "amber", "red", "violet"]


def pretty(token):
    return token.lstrip("-").replace("-", " ")


# --- Tier 1 primitive swatches, grouped by hue family ---
prim_by_hue = {h: [] for h in HUE_ORDER}
for name, val in prims:
    prim_by_hue.setdefault(hc.hue_family(val), []).append((name, val))
prim_sections = []
for hue in HUE_ORDER:
    rows = prim_by_hue.get(hue) or []
    if not rows:
        continue
    chips = "\n".join(
        f'        <div class="pv-chip"><div class="pv-sw" style="background: {v};"></div>'
        f'<div class="pv-lbl"><code>{n}</code><span>{v}</span></div></div>'
        for n, v in rows
    )
    prim_sections.append(
        f'      <div class="pv-hue"><h3 class="pv-hue-h">{hue} ({len(rows)})</h3>'
        f'\n      <div class="pv-chips">\n{chips}\n      </div></div>'
    )

# --- Tier 2 semantic tokens, by cluster (light/dark primitive + resolved hex) ---
sem_sections = []
for cname, toks in clusters:
    rows = "\n".join(
        f'        <tr><td class="pv-name">{pretty(t)}<code>{t}</code></td>'
        f'<td><span class="pv-dot" style="background: var({t});"></span>'
        f'<code>{sem_light.get(t, "?")}</code> <span class="pv-hex">{prim_val.get(sem_light.get(t), "")}</span></td>'
        f'<td><code>{sem_dark.get(t, "?")}</code> <span class="pv-hex">{prim_val.get(sem_dark.get(t), "")}</span></td></tr>'
        for t in toks
    )
    sem_sections.append(
        f'      <details class="pv-cluster" open><summary>{cname} · {len(toks)}</summary>\n'
        f'      <table class="pv-sem"><thead><tr><th>Semantic token</th>'
        f'<th>Light → primitive</th><th>Dark → primitive</th></tr></thead>\n'
        f'      <tbody>\n{rows}\n      </tbody></table></details>'
    )

EXTRA_CSS = """
    .pv-body { padding: 0 20px 60px; max-width: 1100px; }
    .pv-section { margin: 0 0 36px; }
    .pv-section > h2 { font-size: 0.8rem; letter-spacing: 0.08em; text-transform: uppercase;
      color: var(--text-subtle); border-bottom: 1px solid var(--border-subtle); padding-bottom: 6px; }
    .pv-hue { margin: 14px 0; }
    .pv-hue-h { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em;
      color: var(--text-dim); margin: 0 0 6px; }
    .pv-chips { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; }
    .pv-chip { display: flex; align-items: center; gap: 8px; border: 1px solid var(--border-subtle);
      border-radius: 8px; padding: 5px 7px; }
    .pv-sw { width: 30px; height: 26px; border-radius: 4px; flex: none; border: 1px solid var(--border-subtle); }
    .pv-lbl { display: flex; flex-direction: column; min-width: 0; }
    .pv-lbl code { font-size: 0.68rem; color: var(--text-body); word-break: break-all; }
    .pv-lbl span { font-family: ui-monospace, monospace; font-size: 0.64rem; color: var(--text-dim); }
    .pv-cluster { margin: 8px 0; border: 1px solid var(--border-subtle); border-radius: 8px; padding: 4px 12px; }
    .pv-cluster summary { cursor: pointer; font-weight: 600; font-size: 0.85rem; padding: 4px 0; }
    table.pv-sem { width: 100%; border-collapse: collapse; font-size: 0.78rem; }
    table.pv-sem th { text-align: left; color: var(--text-dim); font-weight: 600;
      border-bottom: 1px solid var(--border-subtle); padding: 4px 6px; }
    table.pv-sem td { padding: 4px 6px; border-bottom: 1px solid var(--border-subtle); vertical-align: top; }
    .pv-name { display: flex; flex-direction: column; }
    .pv-name code { font-size: 0.66rem; color: var(--text-dim); }
    .pv-sem code { font-family: ui-monospace, monospace; font-size: 0.72rem; }
    .pv-hex { font-family: ui-monospace, monospace; font-size: 0.68rem; color: var(--text-dim); }
    .pv-dot { display: inline-block; width: 11px; height: 11px; border-radius: 3px; vertical-align: middle;
      margin-right: 4px; border: 1px solid var(--border-subtle); }
"""

body = f"""  <div class="ph-toolbar">
    <strong>Two-tier theme preview</strong>
    <span class="ph-seg" role="group" aria-label="Theme">
      <button data-set="light" aria-pressed="true">Light</button>
      <button data-set="dark" aria-pressed="false">Dark</button>
    </span>
    <span class="ph-note">Read-only preview of base.html's real two-tier palette
      ({len(prims)} primitives · {sum(len(t) for _, t in clusters)} semantic).
      Design tool only — not wired into the app. To edit, use theme_customizer.</span>
  </div>

  <div class="pv-body">
{hc.component_gallery()}
    <section class="pv-section">
      <h2>Tier 1 — primitives ({len(prims)}), by hue · swatch = raw value</h2>
{chr(10).join(prim_sections)}
    </section>
    <section class="pv-section">
      <h2>Tier 2 — semantic tokens by cluster · dot = ACTIVE theme; columns = light / dark primitive</h2>
{chr(10).join(sem_sections)}
    </section>
  </div>

  <script>
    (function () {{
      var root = document.documentElement;
      var btns = document.querySelectorAll(".ph-seg button");
      function apply(mode) {{
        if (mode === "dark") root.setAttribute("data-theme", "dark");
        else root.removeAttribute("data-theme");
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
    "Review Robin — two-tier theme preview",
    "tools/theme_preview.gen.py",
    base_css,
    EXTRA_CSS,
    body,
)
OUT.write_text(html, encoding="utf-8")
print(f"Wrote {OUT.relative_to(ROOT)} ({len(html)} bytes, {len(prims)} primitives, "
      f"{sum(len(t) for _, t in clusters)} semantic across {len(clusters)} clusters)")

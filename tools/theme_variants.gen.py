#!/usr/bin/env python3
"""Generate customizer-loadable theme variants for the 19C input-boundary item.

Each variant is a complete `{version, primitives, semantic:{light,dark}}`
document — the shape `tools/theme_customizer.html`'s **Import JSON** expects.
Import replaces the whole model, so every file carries the full palette read
live from `app/web/templates/base.html`, with only the named deltas applied.

    python3 tools/theme_variants.gen.py          # write + verify
    python3 tools/theme_variants.gen.py --check  # verify only

Output lands next to `theme_customizer.html` as
`tools/theme_variant_<name>.json`, so the files sit beside the tool that
loads them.

Why the border variants override a primitive rather than adding one:
`applyActive()` in the customizer writes CSS variables for `D.primOrder` — the
**build-time** primitive list baked into the HTML — not for whatever keys an
imported file happens to carry. A primitive name the generator did not know
about is stored in the model and never reaches the DOM, so a semantic pointed
at it resolves to an undefined `var()` and the border disappears. All 79
primitives are already referenced, so there is no free slot to borrow either.
Overriding whichever primitive `--border-default` resolves to is therefore the
only way to preview an off-palette border value, and it costs whatever else
maps to that primitive. The report names those co-users per file rather than
stating them here, because the border has already moved once — 19C Item 8
repointed it from `--gray-soft` / `--slate-deep` to `--slate-dim`, and a fixed
list would now be wrong.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _harness_common as hc  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
BASE = REPO / "app" / "web" / "templates" / "base.html"


# ---------------------------------------------------------------- colour maths
def _lin(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_value: str) -> float:
    h = hex_value.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _hls(hex_value: str):
    import colorsys
    h = hex_value.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(r, g, b)


def at_ratio(seed: str, background: str, target: float) -> str:
    """The seed's hue + saturation, lightness moved to hit `target` contrast.

    Searched over the 8-bit output rather than solved analytically: rounding to
    a hex is what actually ships, so the nearest *representable* colour is the
    honest answer. Steps move the ratio by ~0.04, so an exact hit is not always
    available — the verification table prints what each file really lands on.
    """
    import colorsys
    hue, _, sat = _hls(seed)
    best = None
    for i in range(10001):
        rgb = tuple(round(c * 255) for c in colorsys.hls_to_rgb(hue, i / 10000, sat))
        delta = abs(contrast("#%02x%02x%02x" % rgb, background) - target)
        if best is None or delta < best[0]:
            best = (delta, "#%02x%02x%02x" % rgb)
    return best[1]


# ---------------------------------------------------------------- base model
LIGHT_BG = "#ffffff"   # --surface-page, light
DARK_BG = "#0f141b"    # --surface-page, dark


def load_model() -> dict:
    css = hc.lift_base_style(BASE.read_text())
    return {
        "primitives": dict(hc.parse_primitives(css)),
        "semantic": {
            "light": dict(hc.parse_semantic(css)["light"]),
            "dark": dict(hc.parse_semantic(css)["dark"]),
        },
    }


def resolve(model: dict, token: str, theme: str) -> str | None:
    """Follow the semantic chain to a primitive hex, as the customizer does."""
    prims, sem, seen, cur = model["primitives"], model["semantic"][theme], set(), token
    for _ in range(24):
        if cur in prims:
            return prims[cur]
        if cur not in sem or cur in seen:
            return None
        seen.add(cur)
        cur = sem[cur]
    return None


def page_bg(model: dict, theme: str) -> str:
    return resolve(model, "--surface-page", theme)


def border_primitive(model: dict, theme: str) -> str:
    """The primitive `--border-default` currently resolves to in `theme`.

    Resolved rather than hardcoded: the border has already moved once (19C
    Item 8 repointed it to `--slate-dim`), and a generator that names the old
    primitive keeps writing files whose contents no longer match their names —
    which is exactly what happened, silently, on that change.
    """
    sem, seen, cur = model["semantic"][theme], set(), "--border-default"
    for _ in range(24):
        if cur in model["primitives"]:
            return cur
        if cur not in sem or cur in seen:
            raise SystemExit(f"--border-default does not resolve in {theme}")
        seen.add(cur)
        cur = sem[cur]
    raise SystemExit(f"--border-default cycles in {theme}")


def co_users(model: dict, primitive: str, theme: str) -> list[str]:
    """Semantics other than the border that land on the same primitive.

    They move with any override, so the report names them rather than leaving
    a reader to discover the side effect in the preview.
    """
    return sorted(
        s for s, target in model["semantic"][theme].items()
        if target == primitive and s != "--border-default"
    )


def border_variant(target: float) -> dict:
    """Move whichever primitive the border resolves to so `target` is its floor.

    Since 19C Item 8 both themes resolve `--border-default` to the **same**
    primitive, so there is one value to move and it cannot hit a per-theme
    target twice — solving light then dark just lets the second overwrite the
    first, which is how the first version of this function came to write files
    whose names promised a ratio only one theme reached. When the themes share
    a primitive the search therefore targets `min(light, dark)`: `target`
    becomes a floor both themes clear, and the report prints what each
    actually lands on. A palette that maps the two themes separately still
    gets an independent solve per theme.
    """
    model = load_model()
    prims = {theme: border_primitive(model, theme) for theme in ("light", "dark")}
    if prims["light"] != prims["dark"]:
        for theme, prim in prims.items():
            model["primitives"][prim] = at_ratio(
                model["primitives"][prim], page_bg(model, theme), target
            )
        return model

    import colorsys
    prim = prims["light"]
    backgrounds = [page_bg(model, theme) for theme in ("light", "dark")]
    hue, _, sat = _hls(model["primitives"][prim])
    best = None
    for i in range(10001):
        rgb = tuple(round(c * 255) for c in colorsys.hls_to_rgb(hue, i / 10000, sat))
        candidate = "#%02x%02x%02x" % rgb
        floor = min(contrast(candidate, bg) for bg in backgrounds)
        delta = abs(floor - target)
        if best is None or delta < best[0]:
            best = (delta, candidate)
    model["primitives"][prim] = best[1]
    return model


def palette_only_variant() -> dict:
    """No new colour at all — `--border-default` repoints to `--slate-dim`.

    The one option that needs zero primitive edits, so `--marker-neutral` and
    every other consumer of the old primitives stay exactly where they are.
    `--slate-dim` is also `--text-dim` in dark, so border and dim text share a
    value there; that is the thing to look at when judging this one.
    """
    model = load_model()
    model["semantic"]["light"]["--border-default"] = "--slate-dim"
    model["semantic"]["dark"]["--border-default"] = "--slate-dim"
    return model


# --------------------------------------------------------------- beyond border
# The fill options cannot render in the shipped customizer: `base.html` has no
# input-surface token, so an imported `--surface-input` is defined as a CSS
# variable (`applyActive` sets every key in the semantic map, build-time or not)
# and then consumed by nothing. The workaround is a **variant page** —
# `theme_customizer.html` with a trailing <style> that wires those hooks up.
# Later rules of equal specificity win, and the customizer's inline
# `style.setProperty` beats both, so a JSON that omits a hook leaves it at
# today's value.
#
# Caveat worth knowing before you judge these: the hook tokens are not in the
# build-time `D.semLight`, so they do NOT appear in Part B's Semantic-remaps
# list and Part C cannot resolve them for its contrast badges. They paint
# correctly; they are just not editable in the UI. Edit the JSON and re-import.
HOOK_CSS = """
    <style>
      /* tools/theme_variants.gen.py — hooks for the beyond-the-border options.
         Each defaults to today's value, so the stock JSONs look unchanged. */
      :root { --surface-input: var(--surface-page); --surface-card-fill: var(--surface-page); }
      body.ui-v2 input[type="text"], body.ui-v2 input[type="datetime-local"],
      body.ui-v2 input[type="number"], body.ui-v2 input[type="email"],
      body.ui-v2 textarea, body.ui-v2 select { background: var(--surface-input); }
      body.ui-v2 .card { background: var(--surface-card-fill); }
    </style>
"""

CUSTOMIZER = "theme_customizer.html"
VARIANT_PAGE = "theme_customizer_beyond.html"


def write_variant_page() -> str:
    src = (HERE / CUSTOMIZER).read_text(encoding="utf-8")
    if "</body>" not in src:
        raise SystemExit(f"{CUSTOMIZER}: no </body> to insert before")
    out = src.replace("</body>", HOOK_CSS + "  </body>", 1)
    (HERE / VARIANT_PAGE).write_text(out, encoding="utf-8")
    return VARIANT_PAGE


def input_fill_variant() -> dict:
    """The original 19C proposal: lift the input fill off the page surface.

    Uses the nearest existing primitives — there is nothing better available,
    which is the point: light has no off-white with real separation.
    """
    model = load_model()
    for theme, prim in (("light", "--gray-mist"), ("dark", "--ink-deep")):
        model["semantic"][theme]["--surface-input"] = prim
    return model


def card_lift_variant() -> dict:
    """Leave inputs alone; give the card the surface it was named for.

    `--surface-card` already differs from `--surface-page` in dark and is
    identical in light, so this separates the pair in one theme only.
    """
    model = load_model()
    for theme in ("light", "dark"):
        model["semantic"][theme]["--surface-card-fill"] = "--surface-card"
    return model


def fill_and_border_variant() -> dict:
    """Both levers at once — lifted input fill plus the 3.5:1 border."""
    model = border_variant(3.5)
    for theme, prim in (("light", "--gray-mist"), ("dark", "--ink-deep")):
        model["semantic"][theme]["--surface-input"] = prim
    return model


# The five border-* variants that lived here are **retired** (19C Item 8 chose
# `--slate-dim` and shipped it). They are not merely redundant: with both themes
# resolving `--border-default` to one primitive, `max_shared_floor()` shows the
# best floor any single value can reach on that hue is 4.291:1, and `--slate-dim`
# is at 4.286:1 — 0.005 off the ceiling. There is no better shared value to
# explore, and a *better* number needs two per-theme primitives, which this
# generator cannot express (it overrides primitives; it cannot add them). Their
# machinery stays because `beyond-fill-plus-border` still uses it, and because a
# palette that maps the two themes separately would make them meaningful again.
VARIANTS = [
    # Beyond the border — need theme_customizer_beyond.html, not the stock page.
    ("beyond-input-fill", "Input fill lifted off the page surface (the original 19C proposal)", input_fill_variant),
    ("beyond-card-lift", "Card takes --surface-card; inputs unchanged", card_lift_variant),
    ("beyond-fill-plus-border", "Lifted input fill AND the 3.5:1 border together", fill_and_border_variant),
]

BEYOND = {"beyond-input-fill", "beyond-card-lift", "beyond-fill-plus-border"}


def max_shared_floor(model: dict) -> tuple[float, str]:
    """Best `min(light, dark)` contrast one shared border primitive can reach.

    Darkening a single value raises its contrast against the light page and
    lowers it against the dark one, so the achievable floor peaks where those
    two curves cross. Above that crossing no shared value exists, whatever
    target is asked for — which is why a request for 4.5 quietly returned the
    nearest colour instead, and why the border variants are retired.
    """
    import colorsys
    prim = border_primitive(model, "light")
    backgrounds = [page_bg(model, theme) for theme in ("light", "dark")]
    hue, _, sat = _hls(model["primitives"][prim])
    best = (0.0, "")
    for i in range(10001):
        rgb = tuple(round(c * 255) for c in colorsys.hls_to_rgb(hue, i / 10000, sat))
        candidate = "#%02x%02x%02x" % rgb
        floor = min(contrast(candidate, bg) for bg in backgrounds)
        if floor > best[0]:
            best = (floor, candidate)
    return best


def verify(name: str, model: dict) -> list[str]:
    rows = []
    for theme, bg in (("light", LIGHT_BG), ("dark", DARK_BG)):
        border = resolve(model, "--border-default", theme)
        page = resolve(model, "--surface-page", theme)
        assert page == bg, f"{name}/{theme}: --surface-page moved to {page}"
        assert border, f"{name}/{theme}: --border-default does not resolve"
        rows.append(f"    {theme:5s} border {border}  vs page {page}  "
                    f"{contrast(border, page):.3f}:1")
    return rows


def main() -> int:
    check_only = "--check" in sys.argv
    baseline = load_model()
    print("BASELINE (base.html as it stands)")
    print("\n".join(verify("baseline", baseline)))
    if border_primitive(baseline, "light") == border_primitive(baseline, "dark"):
        ceiling, at = max_shared_floor(baseline)
        print(f"    both themes share {border_primitive(baseline, 'light')}; the best "
              f"floor any single value reaches on that hue is {ceiling:.3f}:1 at {at}")
    print()
    for name, blurb, build in VARIANTS:
        model = build()
        model = {"version": 2, "primitives": model["primitives"],
                 "semantic": model["semantic"]}
        print(f"{name} — {blurb}")
        print("\n".join(verify(name, model)))
        deltas = {k: v for k, v in model["primitives"].items()
                  if baseline["primitives"][k] != v}
        if deltas:
            print(f"    primitive overrides: {deltas}")
            for prim in deltas:
                for theme in ("light", "dark"):
                    others = co_users(baseline, prim, theme)
                    if others:
                        print(f"      {prim} in {theme} also paints "
                              f"{', '.join(others)}")
        remaps = {k: v for k, v in model["semantic"]["light"].items()
                  if baseline["semantic"]["light"].get(k) != v}
        if remaps:
            print(f"    semantic remaps (light): {remaps}")
        if name in BEYOND:
            print(f"    load in {VARIANT_PAGE}, not {CUSTOMIZER}")
            for theme in ("light", "dark"):
                fill = resolve(model, "--surface-input", theme) or resolve(model, "--surface-page", theme)
                card = resolve(model, "--surface-card-fill", theme) or resolve(model, "--surface-page", theme)
                print(f"    {theme:5s} input fill {fill} vs card {card}  "
                      f"{contrast(fill, card):.3f}:1")
        if not check_only:
            path = HERE / f"theme_variant_{name}.json"
            path.write_text(json.dumps(model, indent=2) + "\n")
            print(f"    -> {path.relative_to(REPO)}")
        print()
    if not check_only:
        print(f"variant page for the beyond-* files -> tools/{write_variant_page()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

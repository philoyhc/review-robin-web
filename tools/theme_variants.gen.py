#!/usr/bin/env python3
"""Border-contrast analysis for the palette, and the machinery to build
customizer-loadable theme variants when a question needs one.

**No variants are live** (2026-09-06). `VARIANTS` is empty, so a run is a
**report**: it reads `app/web/templates/base.html`, prints the shipped
border's contrast in both themes, and — while both themes share one border
primitive — the best floor any single value could reach on that hue. That
ceiling is what settled 19C Item 8, and it is worth re-reading whenever the
palette moves.

    python3 tools/theme_variants.gen.py          # report (+ write, if any)
    python3 tools/theme_variants.gen.py --check  # report only

To reopen a question, append to `VARIANTS`. Each entry builds a complete
`{version, primitives, semantic:{light,dark}}` document — the shape
`tools/theme_customizer.html`'s **Import JSON** expects. Import replaces the
whole model, so a file carries the full palette read live from `base.html`
with only the named deltas applied, and lands beside the customizer as
`tools/theme_variant_<name>.json`.

Why a variant overrides a primitive rather than adding one:
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


CUSTOMIZER = "theme_customizer.html"

# The five border-* variants that lived here are **retired** (19C Item 8 chose
# `--slate-dim` and shipped it). They are not merely redundant: with both themes
# resolving `--border-default` to one primitive, `max_shared_floor()` shows the
# best floor any single value can reach on that hue is 4.291:1, and `--slate-dim`
# is at 4.286:1 — 0.005 off the ceiling. There is no better shared value to
# explore, and a *better* number needs two per-theme primitives, which this
# generator cannot express (it overrides primitives; it cannot add them).
#
# The three beyond-* variants that followed them are **retired too**
# (2026-09-06). They explored giving inputs and cards their own fill; the route
# lost on the numbers (1.238:1 light / 1.145:1 dark, against the 4.286:1 the
# shipped border reaches), and previewing it needed a second 2.6 MB copy of the
# customizer carrying two tokens `base.html` deliberately does not have. That
# copy read as a facility rather than as a closed experiment, so it and its
# three JSONs are gone. `border_variant()` and `palette_only_variant()` below
# stay: they are the machinery, and a palette that maps the two themes
# separately would make a border variant meaningful again.
VARIANTS: list[tuple[str, str, object]] = []


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
        if not check_only:
            path = HERE / f"theme_variant_{name}.json"
            path.write_text(json.dumps(model, indent=2) + "\n")
            print(f"    -> {path.relative_to(REPO)}")
        print()
    if not VARIANTS:
        print(f"No variants defined — report only. Append to VARIANTS to build "
              f"one, and load it in tools/{CUSTOMIZER}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

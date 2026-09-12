"""Every foreground/background token pair in the palette, measured.

Segment 19K Item 7. ``docs/known_limitations.md`` had carried, since
Segment 14A PR 5 (2026-05-18), an Accessibility entry saying "the
``--text-muted`` colour token fails WCAG AA contrast". The token was
real when that was written; 19C Item 6 renamed the flat scheme into
today's two tiers and ``--text-muted`` became ``--text-dim``. The entry
was never updated, so the one live user-facing fault in that file spent
four months naming a token no grep could find — and the fault itself
went unfixed the whole time, at a measured **2.31:1** against the
darkest light surface, roughly half what AA asks.

Item 7 collapsed the two muted text tiers into one. ``--text-dim`` is
retired; its 20 text uses now take ``--text-subtle``, and its 5 live
decorative uses (three 3px dividers, two gradient stops in a resize
grip) take ``--decor-muted``, a new Borders & focus token holding the
*same* primitives ``--text-dim`` held, so nothing decorative moved a
pixel. Two further uses were deleted rather than moved: ``.btn-cta
.disabled`` painted ``--text-dim`` as a fill, and every one of the 34
templates extending ``base.html`` carries ``ui-v2``, whose own
``.btn-cta.disabled`` rule overrode it on every page.

**The scope widened twice, each time because the narrower version was
shown to be lying by omission.** Checking the one token under repair
found ``--text-link`` failing at 4.22 in dark. Widening to the Text
cluster against ``--surface-*`` found nothing more — and was still
wrong, because ``--nav-home-bg`` is not a surface token: muted text on
the Session Home anchor measured **3.90** before this item and 4.04
after the first fix, a failure the cluster-versus-surfaces sweep could
not see. So the check is now over **every pair the palette actually
forms**, gathered three ways (below), and ``--slate`` went to
``#616874`` rather than ``#667080`` so the floor holds against all of
them with margin rather than against the enumerated ones by 0.06.

**Pairs are gathered, not listed.** A hand-kept list of pairs is the
same mistake one level up — it passes while the palette grows past it.
Three gathering passes: rules that set a ``color`` and a ``background``
in one block; ``--x-fg`` / ``--x-bg`` tokens paired by name; and every
text token against every surface, since which surface a label lands on
is a template's choice. Plus one deliberately hand-kept source,
``ON_FILL``, for the two foregrounds whose fill no convention predicts
— four sources, 73 pairs, 146 theme-resolved pairings today. The
hand-kept one is guarded: the coverage test fails if a ``--text-on-*``
token exists that it does not name.

**The ratios are computed, not pinned.** A test asserting
``--slate == "#616874"`` would pass forever while someone repoints
``--text-subtle`` at a different primitive, which is the move this item
itself made twice. ``test_the_ratio_matches_published_values`` pins the
arithmetic instead.

**Eleven pairs still fail and are named, not excused.** They are
pre-existing, they are all buttons, pill tints and selected states
rather than body text, and each is pinned at the value it was recorded
at — so a fix must delete its entry and a regression fails the suite.
Fixing them is a design decision per family (see
``docs/known_limitations.md``), not a follow-on to this item.

**Scope, stated so it can be argued with.** WCAG 1.4.3 governs *text*;
a divider and a gradient stop are not text and carry no ratio floor,
which is why ``--decor-muted`` exists as a separate token rather than
as an exception inside this check. What is guarded is that it never
becomes a text colour again — retiring ``--text-dim`` is worth nothing
if the same value returns under a new name.

**What this cannot see.** A pair only forms here if one rule sets both
halves, or the token names match, or the background is a surface. Text
inheriting a background from a distant ancestor is invisible to all
three, and no static reading of the sheet will find it — that is what
the dev slot is for.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from ._base_css import BASE_HTML, css, rules, token_maps

# ``tools/`` is not a package on the default path; ``test_close_check.py``
# reaches into it the same way.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import _harness_common as harness  # noqa: E402

#: WCAG 2.1 SC 1.4.3. Normal text is 4.5:1; large text (>=18.66px, or
#: >=14pt bold) is 3:1. Muted labels render at ``--fs-tiny`` (0.75rem)
#: and button labels at 0.95em, so the stricter bar is the one that
#: binds throughout and the looser one is never claimed below.
AA_NORMAL = 4.5

#: The muted text token, after Item 7 collapsed ``--text-dim`` into it.
MUTED_TEXT = "--text-subtle"

#: Decoration, not text. Same primitives ``--text-dim`` resolved to, so
#: the five surviving decorative uses render exactly as before.
DECORATION = "--decor-muted"

#: The fill each ``--text-on-*`` token belongs to. The one hand-kept
#: list here, and it exists because these two pairings are derivable no
#: other way: the names do not match (``--text-on-amber`` /
#: ``--btn-alert-bg``) and no single rule sets both halves, so all
#: three gathering passes miss them. Pairing them with surfaces
#: instead, as an earlier draft did, measures white-on-white and calls
#: it a failure. ``test_the_sweep_finds_the_palette_it_claims_to``
#: asserts every ``--text-on-*`` token in the palette appears here, so
#: a new one cannot be added and quietly go unchecked.
ON_FILL = {
    "--text-on-accent": "--btn-primary-bg",
    "--text-on-amber": "--btn-alert-bg",
}

#: Pairs that do not clear AA normal, each mapped to the ratio it
#: measured on 2026-09-12 at 19K.7. Every one is pre-existing; none is
#: body text. They fall into three families, and each family is one
#: decision rather than one fix:
#:
#: - **White on a mid-tone accent fill** (6): the dark primary button
#:   and its hover, the light primary and alert hovers, and the dark
#:   selected state. The dark fill is ``--blue-glow``, the reserved
#:   "you can act on this" shade, so moving it moves ``--selected-bg``,
#:   ``--focus-ring`` and seven more dark tokens together.
#: - **Saturated text on its own pale tint** (5): the green
#:   ``#059669`` on ``#d1fae5`` shared by the ready lifecycle pill, the
#:   reviewee role chip and the success pill, and the red ``#dc2626``
#:   on ``#fee2e2`` shared by the expired pill and the destructive
#:   button's hover. Deepening the text or paling the tint is a palette
#:   decision across every status family at once.
#:
#: A floor rather than an equality in both directions: a regression
#: fails, and so does a fix, because a fix should delete the entry
#: rather than leave a stale number behind it.
KNOWN_SHORTFALLS = {
    ("dark", "--btn-primary-fg", "--btn-primary-bg-hover"): 2.54,
    ("light", "--btn-alert-fg", "--btn-alert-bg-hover"): 3.19,
    ("light", "--lifecycle-ready-fg", "--lifecycle-ready-bg"): 3.32,
    ("light", "--role-reviewee-fg", "--role-reviewee-bg"): 3.32,
    ("light", "--status-success-accent", "--status-success-bg"): 3.32,
    ("dark", "--btn-primary-fg", "--btn-primary-bg"): 3.33,
    ("dark", "--selected-fg", "--selected-bg"): 3.33,
    ("dark", "--text-on-accent", "--btn-primary-bg"): 3.33,
    ("light", "--btn-primary-fg", "--btn-primary-bg-hover"): 3.68,
    ("light", "--btn-destructive-fg", "--btn-destructive-bg-hover"): 3.95,
    ("light", "--lifecycle-expired-fg", "--lifecycle-expired-bg"): 3.95,
}

#: Tolerance on a recorded shortfall before it counts as movement.
#: Two hundredths: enough to absorb nothing at all, since both sides
#: are exact hexes and the arithmetic is deterministic, and small
#: enough that any real repoint trips it.
DRIFT = 0.02

def _srgb(channel: int) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(value: str) -> float:
    """WCAG 2.1 relative luminance of a ``#rrggbb`` string."""
    h = value.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _srgb(r) + 0.7152 * _srgb(g) + 0.0722 * _srgb(b)


def contrast(a: str, b: str) -> float:
    """WCAG 2.1 contrast ratio between two ``#rrggbb`` strings."""
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _literals(tokens: dict[str, str], prefix: str) -> dict[str, str]:
    return {
        name: value
        for name, value in tokens.items()
        if name.startswith(prefix) and value.startswith("#")
    }


def collect_pairs() -> dict[tuple[str, str], str]:
    """Every foreground/background token pair the palette forms.

    Delegated to ``tools/_harness_common.collect_contrast_pairs`` rather
    than defined here, because the theme customizer's Contrast panel
    renders a row per pair from the same call. The panel is where a
    person *inspects* the audit; this file is what *enforces* it, and two
    definitions would let the panel under-report while the suite stayed
    green — which is the shape of the defect this whole item is about.
    ``test_the_customizer_panel_lists_every_audited_pair`` closes the loop
    from the other end.

    The four sources and why each exists are documented on
    ``collect_contrast_pairs``.
    """
    return harness.collect_contrast_pairs(harness.lift_base_style(BASE_HTML.read_text(encoding="utf-8")))


def measured() -> list[tuple[float, str, str, str, str]]:
    """``(ratio, theme, fg, bg, provenance)`` for every resolvable pairing."""
    tokens = token_maps(css())
    out = []
    for (fg, bg), provenance in collect_pairs().items():
        for theme in ("light", "dark"):
            a, b = tokens[theme].get(fg, ""), tokens[theme].get(bg, "")
            if a.startswith("#") and b.startswith("#"):
                out.append((contrast(a, b), theme, fg, bg, provenance))
    return out


def test_the_ratio_matches_published_values() -> None:
    """Pins the arithmetic, since every other test here trusts it.

    Black on white is WCAG's own worked example at 21:1, and a colour
    on itself is 1:1. The third pair is this repo's: ``spec/
    color_tokens.md`` records ``--border-default`` at 4.29 light and
    4.31 dark, measured independently at 19C Item 8 and reproduced
    here four segments later.
    """
    assert round(contrast("#000000", "#ffffff"), 2) == 21.0
    assert round(contrast("#6b7280", "#6b7280"), 2) == 1.0
    assert round(contrast("#6f7b8e", "#ffffff"), 2) == 4.29
    assert round(contrast("#6f7b8e", "#0f141b"), 2) == 4.31


def test_the_sweep_finds_the_palette_it_claims_to() -> None:
    """Guards the guards.

    Every assertion below is "for each pair, ...", and a collector
    returning nothing satisfies all of them. 19K.6 lost a mutation to
    exactly this, so the coverage floor is its own named test rather
    than a line inside the check it protects. The floors are the
    counts on 2026-09-12, less a little room to add a token without
    editing a test.
    """
    pairs, rows = collect_pairs(), measured()

    assert len(pairs) >= 70, f"only {len(pairs)} pairs collected"
    assert len(rows) >= 140, f"only {len(rows)} pairings resolved"

    tokens = token_maps(css())
    on_fill = {n for n in tokens["light"] if n.startswith("--text-on-")}
    assert on_fill <= set(ON_FILL), (
        f"--text-on-* tokens with no fill recorded in ON_FILL: {sorted(on_fill - set(ON_FILL))}"
    )
    for name, fill in ON_FILL.items():
        assert (name, fill) in pairs, f"{name} on {fill} was not collected"

    # All four sources alive. The rule pass is the one that found the
    # failure a cluster-versus-cluster sweep could not see, so its death
    # is called out by name rather than folded into a count.
    kinds = {p.split(":", 1)[0] for p in pairs.values()}
    assert "rule" in kinds, (
        "no pair came from a CSS rule — the source that caught --nav-home-bg is dead"
    )
    assert {"name", "surface", "fill"} <= kinds, f"sources missing: {sorted({'name', 'surface', 'fill'} - kinds)}"


def test_every_pair_clears_aa_but_for_the_recorded_shortfalls() -> None:
    """The rule, over the whole palette.

    Anything failing that is not in ``KNOWN_SHORTFALLS`` is new, and
    the message carries where it came from so it can be judged rather
    than merely added to the list.
    """
    failures = [
        f"{ratio:5.2f}  {theme:5} {fg} on {bg}   [{provenance}]"
        for ratio, theme, fg, bg, provenance in sorted(measured())
        if ratio < AA_NORMAL and (theme, fg, bg) not in KNOWN_SHORTFALLS
    ]

    assert not failures, (
        "token pairs under AA normal (4.5:1) and not recorded:\n  "
        + "\n  ".join(failures)
        + "\nEither fix the pair or add it to KNOWN_SHORTFALLS with its "
        "measured ratio and a reason in docs/known_limitations.md."
    )


def test_the_recorded_shortfalls_are_still_what_was_recorded() -> None:
    """Neither worse nor quietly fixed.

    A shortfall that improved past AA should lose its entry here and
    its line in ``docs/known_limitations.md`` together; leaving a
    stale number behind is how the entry this item repaired became
    wrong in the first place.
    """
    now = {(theme, fg, bg): ratio for ratio, theme, fg, bg, _ in measured()}

    missing = sorted(k for k in KNOWN_SHORTFALLS if k not in now)
    assert not missing, f"recorded shortfalls no longer pair at all: {missing}"

    moved, fixed = [], []
    for key, recorded in KNOWN_SHORTFALLS.items():
        ratio = now[key]
        if ratio >= AA_NORMAL:
            fixed.append(f"{key[1]} on {key[2]} ({key[0]}) now {ratio:.2f}")
        elif abs(ratio - recorded) > DRIFT:
            moved.append(f"{key[1]} on {key[2]} ({key[0]}) {recorded} -> {ratio:.2f}")

    assert not fixed, (
        "these now clear AA — delete their KNOWN_SHORTFALLS entries and their "
        "docs/known_limitations.md lines:\n  " + "\n  ".join(fixed)
    )
    assert not moved, (
        "recorded shortfalls moved; re-record them with today's values:\n  "
        + "\n  ".join(moved)
    )


def test_the_retired_token_is_gone_from_every_template() -> None:
    """``--text-dim`` is retired, not merely unused.

    Checked across the templates rather than in ``base.html`` alone:
    two operator pages carried their own uses, and a token that is
    undefined but still referenced renders as an inherited colour with
    no error anywhere — the silent failure mode this item is about.
    """
    root = Path(__file__).resolve().parents[2] / "app/web/templates"
    offenders = [
        f"{path.relative_to(root)}:{n}"
        for path in sorted(root.rglob("*.html"))
        for n, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1)
        if "--text-dim" in line
    ]

    assert offenders == [], "--text-dim was retired at 19K.7:\n  " + "\n  ".join(offenders)


def test_decoration_never_paints_text() -> None:
    """The token that keeps the failing value keeps it away from text.

    ``--decor-muted`` holds exactly what ``--text-dim`` held — 2.31:1
    against the darkest light surface — which is fine for a 3px divider
    and is the original defect for a label. Without this, Item 7 is one
    ``color:`` declaration away from being undone. The lookbehind is
    load-bearing: ``border-color`` ends in ``color`` and is a boundary,
    not text.
    """
    declaration = re.compile(r"(?<![-\w])color\s*:\s*var\(" + DECORATION + r"\)")

    offenders = sorted(
        selector for selector, body in rules(css()) if declaration.search(body)
    )

    assert offenders == [], (
        f"{DECORATION} is decoration, not text — these paint text with it:\n  "
        + "\n  ".join(offenders)
    )


def test_decoration_holds_the_values_the_retired_token_had() -> None:
    """Nothing decorative moved a pixel.

    The five surviving uses were repointed, not restyled, and this is
    what says so: the light and dark values are the ones ``--text-dim``
    resolved to before the collapse. A future decision to lighten or
    darken a divider is welcome and should edit this test with it.
    """
    tokens = token_maps(css())

    assert tokens["light"][DECORATION] == "#9ca3af"  # was --text-dim -> --gray
    assert tokens["dark"][DECORATION] == "#6f7b8e"  # was --text-dim -> --slate-dim


def test_the_muted_token_absorbed_the_retired_one() -> None:
    """The collapse happened, rather than the uses merely vanishing.

    ``test_the_retired_token_is_gone_from_every_template`` passes just
    as well if someone deletes the labels instead of repointing them.
    This is the other half: the surviving muted token is the one doing
    the work, on both the chrome ``base.html`` owns and the two
    operator pages that carried their own uses.
    """
    root = Path(__file__).resolve().parents[2] / "app/web/templates"
    counts = {
        path.name: path.read_text(encoding="utf-8").count(f"color: var({MUTED_TEXT})")
        for path in sorted(root.rglob("*.html"))
    }

    # The counts as the collapse left them: 30 + 16, 5 + 3, 0 + 1. Floors
    # rather than equalities so that new muted text is not a failure, but
    # deleting a label instead of repointing it is.
    assert counts["base.html"] >= 46, counts["base.html"]
    assert counts["instruments_index.html"] >= 8, counts["instruments_index.html"]
    assert counts["session_observers.html"] >= 1, counts["session_observers.html"]


def test_the_customizer_panel_lists_every_audited_pair() -> None:
    """The inspection surface and the enforced set are the same set.

    `tools/theme_customizer.html` is where a person reads this audit, and
    it is generated. Before 19K.7 its Contrast panel carried a hand-kept
    list of **12** pairs — which had drifted to include `--text-dim`,
    retired by this item, and omitted the `--nav-home-bg` pair that was
    failing AA. Both halves of that are the same defect: a list nobody
    re-derives.

    So the panel now renders a row per pair from the same
    `collect_contrast_pairs` this file enforces, and this test asserts the
    *generated output* carries them — not the generator's source, which
    would pass while the committed page was stale. Nothing else in the
    repo tests generator-versus-output drift.
    """
    page = (
        Path(__file__).resolve().parents[2] / "tools/theme_customizer.html"
    ).read_text(encoding="utf-8")

    rendered = set(re.findall(r'class="tc-cx" data-fg="(--[a-z0-9-]+)" data-bg="(--[a-z0-9-]+)"', page))
    audited = set(collect_pairs())

    assert rendered == audited, (
        "the customizer's Contrast panel is out of step with the audit — "
        "run `python3 tools/theme_customizer.gen.py`.\n"
        f"  missing from the page: {sorted(audited - rendered)}\n"
        f"  on the page but not audited: {sorted(rendered - audited)}"
    )


def test_the_customizer_panel_can_show_a_shortfall() -> None:
    """The red outline has something to attach to, and a hook to drive it.

    Asserts the mechanism, and says so: there is no JS runtime in this
    suite, so this cannot prove the outline paints. What it can prove is
    that the class the script toggles is defined in the stylesheet and
    that every recorded shortfall has a row to be toggled on — which is
    where a silent failure would otherwise sit, the panel rendering 73
    rows and flagging none of them.
    """
    page = (
        Path(__file__).resolve().parents[2] / "tools/theme_customizer.html"
    ).read_text(encoding="utf-8")

    assert ".tc-cx-ratio.below-aa" in page, "the sub-AA outline rule is gone"
    assert 'classList.toggle("below-aa"' in page, "nothing toggles the sub-AA class"

    rendered = set(re.findall(r'data-fg="(--[a-z0-9-]+)" data-bg="(--[a-z0-9-]+)"', page))
    unrowed = sorted((fg, bg) for _, fg, bg in KNOWN_SHORTFALLS if (fg, bg) not in rendered)
    assert not unrowed, f"recorded shortfalls with no row to flag: {unrowed}"

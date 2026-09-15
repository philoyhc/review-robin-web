#!/usr/bin/env python3
"""Prove a CSS refactor changed no computed style, on the real pages.

The test suite cannot do this. It has no layout engine and no JS
runtime, so CSS *reach* — which rule actually wins on which element —
is invisible to it. Segment 19P lost two declarations that way in two
separate slices: `.is-locked` (a stray click during an edit threw away
a half-typed row) and `.filter-actions`' `margin-top` (buttons flush
against the search box). One took a cold read to find, the other the
dev slot.

So: render the affected pages on both sides of a change, read the
computed styles Chromium actually resolves, and diff them. A refactor
that claims to change nothing has to produce zero differences; one that
means to change something has to produce exactly the differences it intended.

    # on the base commit
    python3 tools/css_parity_check.py --out /tmp/before
    # ...apply the change...
    python3 tools/css_parity_check.py --out /tmp/after
    python3 tools/css_parity_check.py --diff /tmp/before /tmp/after

**Not part of CI, and adds no repo dependency.** It needs `node` with
`playwright` resolvable and a Chromium binary. Neither is a repo
dependency and neither is assumed: set

    RRW_NODE_ROOT=<dir containing node_modules/playwright>
    RRW_CHROMIUM=<path to the browser>   # default /opt/pw-browsers/chromium

ESM resolves imports from the importing file's own directory, so the
extractor is written into `RRW_NODE_ROOT` rather than a temp dir — get
that wrong and node reports `ERR_MODULE_NOT_FOUND`, which is what the
error path below explains. If anything is missing it says so and exits
non-zero rather than pretending to have checked.

Which selectors and properties it samples is deliberately a constant
below, not a flag: the point is that both sides sample identically.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: Selectors sampled on every page. Extend when a refactor touches a
#: different family — and re-record BOTH sides afterwards, never one.
SELECTORS = [
    ".filter-row",
    ".filter-row > label",
    ".filter-row select",
    '.filter-row input[type="text"]',
    ".filter-actions",
    ".filter-card form",
    ".operator-actions-card form",
    ".toolbar-right form",
]

#: Every property the sampled rules declare, plus the geometry that
#: would move if one of them stopped applying.
PROPERTIES = [
    "display", "flexDirection", "gap", "rowGap", "columnGap",
    "alignItems", "justifyContent", "flexWrap", "marginTop",
    "marginRight", "marginBottom", "marginLeft", "flexGrow",
    "flexShrink", "flexBasis", "width", "boxSizing", "fontSize", "color",
]

_EXTRACT_JS = """
import { chromium } from 'playwright';
import { readdirSync, writeFileSync } from 'fs';
const [dir, outFile, selJson, propJson] = process.argv.slice(2);
const SELECTORS = JSON.parse(selJson), PROPS = JSON.parse(propJson);
const browser = await chromium.launch({
  executablePath: process.env.RRW_CHROMIUM || undefined });
const page = await browser.newPage({ viewport: { width: 1280, height: 1600 } });
const out = {};
for (const f of readdirSync(dir).filter(f => f.endsWith('.html')).sort()) {
  await page.goto('file://' + dir + '/' + f);
  out[f] = await page.evaluate(([SELECTORS, PROPS]) => {
    const rows = [];
    for (const sel of SELECTORS) {
      document.querySelectorAll(sel).forEach((el, i) => {
        const cs = getComputedStyle(el);
        const r = { sel, i, cls: el.className || '(none)' };
        for (const k of PROPS) r[k] = cs[k];
        const bb = el.getBoundingClientRect();
        r.box = Math.round(bb.width) + 'x' + Math.round(bb.height);
        rows.push(r);
      });
    }
    return rows;
  }, [SELECTORS, PROPS]);
}
writeFileSync(outFile, JSON.stringify(out, null, 1));
await browser.close();
"""


def _render_pages(into: Path) -> list[str]:
    """Render the pages via the suite's own fixtures.

    `tests/integration/test_css_parity_dump.py` is skipped unless
    `RRW_PARITY_DUMP` is set; it is a test so it can use the real
    `client` / `db` fixtures, which is what makes these the actual
    template output rather than an approximation. It asserts that every
    page rendered, so a route gate cannot quietly shrink the sample.
    """
    env = dict(os.environ, RRW_PARITY_DUMP=str(into))
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q",
         "tests/integration/test_css_parity_dump.py"],
        cwd=REPO, env=env, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout[-3000:], file=sys.stderr)
        # Exit 2, not 1: `close_check.py`'s convention, which this file
        # follows — 0 pass, 1 differences found, 2 could not check.
        raise SystemExit(2)
    return sorted(p.stem for p in into.glob("*.html"))


def record(out: Path) -> int:
    if shutil.which("node") is None:
        print("node not found; this tool needs node + playwright.",
              file=sys.stderr)
        return 2
    node_root = Path(os.environ.get("RRW_NODE_ROOT", REPO)).resolve()
    if not (node_root / "node_modules" / "playwright").is_dir():
        print(f"no node_modules/playwright under {node_root}.\n"
              "Set RRW_NODE_ROOT to a directory that has it "
              "(`npm i playwright` there). ESM resolves from the "
              "importing file's directory, so it cannot be elsewhere.",
              file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    script = node_root / ".rrw_css_parity_extract.mjs"
    with tempfile.TemporaryDirectory() as tmp:
        _render_pages(Path(tmp))  # raises SystemExit(2) if any page missed
        script.write_text(_EXTRACT_JS, encoding="utf-8")
        env = dict(os.environ)
        env.setdefault("RRW_CHROMIUM", "/opt/pw-browsers/chromium")
        try:
            proc = subprocess.run(
                ["node", str(script), tmp, str(out / "styles.json"),
                 json.dumps(SELECTORS), json.dumps(PROPERTIES)],
                cwd=node_root, env=env, capture_output=True, text=True,
            )
        finally:
            script.unlink(missing_ok=True)
        if proc.returncode != 0:
            print(proc.stderr.strip()[:2000], file=sys.stderr)
            return 2
    data = json.loads((out / "styles.json").read_text())
    per_page = {k: len(v) for k, v in sorted(data.items())}
    n = sum(per_page.values())

    # F3: without these the tool prints "0 differences" over nothing and
    # exits 0 — the exact "reported success having checked nothing" its
    # own docstring promises not to do.
    if not per_page:
        print("no pages rendered; nothing was sampled", file=sys.stderr)
        return 2
    if n == 0:
        print("every page sampled zero elements; the selectors match "
              "nothing, so a diff would be meaningless", file=sys.stderr)
        return 2

    # F5: HTTP 200 does not mean the shape was on the page. Assignments
    # renders fine and contributes zero filter-strip elements, because
    # its strip is state-gated. A page that samples nothing is not an
    # error, but it must not be counted as covered.
    empty = [k for k, v in per_page.items() if v == 0]
    for page, count in per_page.items():
        print(f"  {page:24s} {count:3d}")
    if empty:
        print(f"  ! {len(empty)} page(s) sampled NOTHING and are not "
              f"covered by any comparison: {', '.join(empty)}",
              file=sys.stderr)

    # The snapshot records what it sampled, so `diff` can refuse to
    # compare two runs that asked different questions.
    (out / "manifest.json").write_text(json.dumps(
        {"selectors": SELECTORS, "properties": PROPERTIES}, indent=1))
    print(f"recorded {n} elements across {len(per_page) - len(empty)} "
          f"covered page(s) of {len(per_page)} rendered -> {out}")
    return 0


def diff(before: Path, after: Path) -> int:
    a = json.loads((before / "styles.json").read_text())
    b = json.loads((after / "styles.json").read_text())

    # F14: two runs that sampled different selectors or properties are
    # not comparable, and `for k in r1` would silently skip whatever the
    # older side never recorded. The docstring warned a human about
    # this; enforcing it is better than warning.
    manifests = []
    for side in (before, after):
        path = side / "manifest.json"
        manifests.append(json.loads(path.read_text()) if path.exists() else None)
    if manifests[0] != manifests[1]:
        print("the two snapshots sampled different selectors or "
              "properties, so they are not comparable; re-record BOTH "
              "sides", file=sys.stderr)
        return 2

    if a.keys() != b.keys():
        print(f"page sets differ: {sorted(a)} vs {sorted(b)}", file=sys.stderr)
        return 2
    total = diffs = 0
    for page in a:
        if len(a[page]) != len(b[page]):
            print(f"{page}: element count changed "
                  f"{len(a[page])} -> {len(b[page])}")
            diffs += 1
            continue
        for r1, r2 in zip(a[page], b[page]):
            total += 1
            for k in r1:
                if r1[k] != r2[k]:
                    diffs += 1
                    print(f"DIFF {page} {r1['sel']}[{r1['i']}] "
                          f"cls={r1['cls']!r} {k}: {r1[k]!r} -> {r2[k]!r}")
    # F3 again, on the reading side.
    if total == 0:
        print("compared 0 elements; the snapshots are empty, so this is "
              "not evidence of anything", file=sys.stderr)
        return 2
    print(f"\n{total} elements x {len(PROPERTIES)} properties across "
          f"{len(a)} pages -> {diffs} difference(s)")
    return 1 if diffs else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, help="record a snapshot here")
    p.add_argument("--diff", nargs=2, type=Path,
                   metavar=("BEFORE", "AFTER"))
    args = p.parse_args()
    if args.diff:
        return diff(*args.diff)
    if args.out:
        return record(args.out)
    p.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

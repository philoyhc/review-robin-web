"""``--archived`` — the honoured-commitments baseline over every
archived plan.

Not a peer of the close check but a **driver over it**: this module
calls five of ``_manifest``'s functions (``find_manifests``,
``_section``, ``parse_bullets``, ``window``, ``honoured``) and adds
only the loop and the totals. Segment 19J Item 3 named three jobs in
one file; measuring the split showed two of them are independent and
this one is not, which is why it is 60 lines rather than 600.

Always exits 0 — it reports a baseline, it does not gate.
"""

from __future__ import annotations

from ._manifest import (
    _section,
    find_manifests,
    honoured,
    parse_bullets,
    window,
)
from . import _shared


def manifest_levels(found: dict) -> list[tuple[int, int, int | None]]:
    """Every `Doc impact` level in a plan, as (line, depth, item).

    The same level set `check_manifest` closes on, and the reason this
    function exists: `archived_report` used to take the segment manifest
    **or the first item's** and stop. A segment-level manifest spans the
    whole plan, so those plans were read whole; an item-shaped plan was
    read at one of its items. Measured 2026-09-11 over the 98 archived
    plans, that hid **37 of the 42 item manifests** — `19I` was judged on
    1 of its 13 — and every one of the 112 committed paths it hid was
    honoured, so the sweep understated the practice it exists to measure
    (147/162, 91% -> 259/274, 95%).

    A plan carrying both shapes is a C1 failure, adjudicated at its own
    close; here the segment manifest wins, as it did before.
    """
    if found["segment"] is not None:
        return [(found["segment"], 2, None)]
    return (
        [(item["doc"], 3, number) for number, item in found["items"].items()
         if item["doc"] is not None]
        # A stray `### Doc impact` sits outside any `## Item n` block —
        # 11E has one under `## Follow-on` — so it has no item number and
        # takes the manifest heading's own window.
        + [(line, 3, None) for line in found["stray"]]
    )


def archived_report(stream) -> None:
    plans = sorted((_shared.REPO / "guide" / "archive").glob("segment_*.md"))
    total_paths = total_honoured = 0
    fully = considered = no_manifest = missing = 0
    noted_paths = noted_plans = 0

    print(f"ARCHIVED PLANS ({len(plans)})", file=stream)
    for plan in plans:
        found = find_manifests(plan.read_text())
        levels = manifest_levels(found)
        plan_paths = plan_hits = plan_missing = 0
        noted_here: list[str] = []
        earliest = None
        for line, depth, item in levels:
            body = _section(found["lines"], line, depth)
            bullets = parse_bullets(found["lines"], *body)
            paths = list(dict.fromkeys(
                path for bullet in bullets
                for path in bullet["paths"] if not bullet["waived"]
            ))
            # Counted for the footer, kept out of the honour ratio: a
            # `guide/` commitment is not verified (see `GUIDE_PATH` in
            # `_manifest.py`), and folding unverifiable paths into a
            # percentage would make the percentage mean less, not more.
            # Deduplicated per plan rather than per level, which is what
            # the footer counted before it read more than one level.
            # Extended one at a time, not by a comprehension: a
            # comprehension's `if path not in noted_here` is evaluated
            # against the list as it stood *before* `+=` extends it, so a
            # path named twice inside one level slips through. That cost
            # one duplicate in the real corpus (64 against a measured 63)
            # — small enough to wave away, which is the reason to check.
            for bullet in bullets:
                for path in bullet["guide_paths"]:
                    if path not in noted_here:
                        noted_here.append(path)
            if not paths:
                continue
            # Each item level takes its *own* window, opening at the later
            # of the manifest heading and that item's `## Item <n>`. Passing
            # `item=None` here would import 19A.2's false pass into the
            # sweep: every item would inherit the first one's start, and a
            # path another item had edited would read as honoured.
            start, end, start_date, _ = window(plan, depth, item)
            if start_date and (earliest is None or start_date < earliest):
                earliest = start_date
            # Missing paths are C2's business, not C3's — keep them out of
            # the honour denominator so the two code paths divide the work
            # the same way, and report them on their own.
            live = [path for path in paths if (_shared.REPO / path).exists()]
            plan_missing += len(paths) - len(live)
            plan_hits += sum(
                1 for path in live if start and honoured(path, start, end)
            )
            plan_paths += len(live)

        if noted_here:
            noted_paths += len(noted_here)
            noted_plans += 1
        if not plan_paths and not plan_missing:
            no_manifest += 1
            continue

        considered += 1
        total_paths += plan_paths
        total_honoured += plan_hits
        missing += plan_missing
        if plan_paths and plan_hits == plan_paths:
            fully += 1
        flags = []
        if plan_hits != plan_paths:
            flags.append(f"{plan_paths - plan_hits} unhonoured")
        if plan_missing:
            flags.append(f"{plan_missing} missing")
        if len(levels) > 1:
            flags.append(f"{len(levels)} manifests")
        flag = f"  <- {', '.join(flags)}" if flags else ""
        print(
            f"  {plan.name:58s} {plan_hits:3d}/{plan_paths:<3d} "
            f"{earliest or '(no window)'}{flag}",
            file=stream,
        )

    if noted_paths:
        print(
            f"\n  {noted_paths} guide/ commitment(s) across {noted_plans} plan(s) "
            "counted, not verified\n"
            "  (excluded from the ratio below, which is therefore unchanged "
            "— see `GUIDE_PATH` in `_manifest.py`)",
            file=stream,
        )

    share = f"{100 * total_honoured / total_paths:.0f}%" if total_paths else "n/a"
    print(
        f"\n  {total_honoured}/{total_paths} live committed paths honoured ({share}); "
        f"{fully} of {considered} plans fully honoured; "
        f"{missing} committed path(s) no longer exist; "
        f"{no_manifest} plans with no manifest",
        file=stream,
    )



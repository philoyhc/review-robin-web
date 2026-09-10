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


def archived_report(stream) -> None:
    plans = sorted((_shared.REPO / "guide" / "archive").glob("segment_*.md"))
    total_paths = total_honoured = 0
    fully = considered = no_manifest = missing = 0

    print(f"ARCHIVED PLANS ({len(plans)})", file=stream)
    for plan in plans:
        found = find_manifests(plan.read_text())
        if found["segment"] is None and not found["stray"] and not any(
            i["doc"] is not None for i in found["items"].values()
        ):
            no_manifest += 1
            continue
        depth = 2 if found["segment"] is not None else 3
        line = found["segment"] if depth == 2 else next(
            (i["doc"] for i in found["items"].values() if i["doc"] is not None),
            found["stray"][0] if found["stray"] else None,
        )
        body = _section(found["lines"], line, depth)
        bullets = parse_bullets(found["lines"], *body)
        paths = [p for bullet in bullets for p in bullet["paths"] if not bullet["waived"]]
        paths = list(dict.fromkeys(paths))
        if not paths:
            no_manifest += 1
            continue

        start, end, start_date = window(plan, depth)
        considered += 1
        # Missing paths are C2's business, not C3's — keep them out of the
        # honour denominator so the two code paths divide the work the same
        # way, and report them on their own.
        live = [path for path in paths if (_shared.REPO / path).is_file()]
        missing += len(paths) - len(live)
        hits = sum(1 for path in live if start and honoured(path, start, end))
        total_paths += len(live)
        total_honoured += hits
        if live and hits == len(live):
            fully += 1
        flags = []
        if hits != len(live):
            flags.append(f"{len(live) - hits} unhonoured")
        if len(paths) != len(live):
            flags.append(f"{len(paths) - len(live)} missing")
        flag = f"  <- {', '.join(flags)}" if flags else ""
        print(
            f"  {plan.name:58s} {hits:3d}/{len(live):<3d} "
            f"{start_date or '(no window)'}{flag}",
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



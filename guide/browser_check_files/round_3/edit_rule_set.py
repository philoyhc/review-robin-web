"""Round 3 browser checks: hand-edit one session's stored assignment rule.

No page can store either shape any more; an old row or a direct database
edit can, and that is what these checks need. Run from the repository
root against the local SQLite database, with the dev server running or
not:

    python guide/browser_check_files/round_3/edit_rule_set.py <code> disable
    python guide/browser_check_files/round_3/edit_rule_set.py <code> unloadable

``disable`` turns off every rule in Who is being reviewed (Link 2);
``unloadable`` replaces the rules with one the engine can't load.
"""

from __future__ import annotations

import json
import sqlite3
import sys


def main(code: str, mode: str) -> None:
    con = sqlite3.connect("review_robin_web.db")
    rows = con.execute(
        "SELECT DISTINCT r.id, r.rules_json FROM session_rule_sets r "
        "JOIN instruments i ON i.rule_set_id = r.id "
        "JOIN sessions s ON s.id = i.session_id WHERE s.code = ?",
        (code,),
    ).fetchall()
    if not rows:
        sys.exit(f"no stored rule set on a session coded {code!r}")
    for rule_set_id, raw in rows:
        rules = json.loads(raw or "[]")
        if mode == "disable":
            for entry in rules:
                if entry.get("id") == "link2":
                    for child in entry.get("rules", []):
                        child["enabled"] = False
        elif mode == "unloadable":
            rules = [{"kind": "no-such-rule"}]
        else:
            sys.exit("mode is disable or unloadable")
        con.execute(
            "UPDATE session_rule_sets SET rules_json = ? WHERE id = ?",
            (json.dumps(rules), rule_set_id),
        )
    con.commit()
    print(f"{mode}: {len(rows)} rule set(s) on {code}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])

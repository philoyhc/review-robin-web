# New-project practices setup

A drop-in checklist for the first day of a new repository. Everything here
is generalised from the Review Robin Web practice audit of 2026-09-04
(`docs/practice-audit-2026-09-04.md`), where each item was established by
running a deliberate violation and watching what happened — not by reasoning
about what a config file ought to do.

The theme: **each of these costs under an hour at project start and gets
progressively more awkward to retrofit.** RRW added them at ~4,500 commits;
every one would have been cheaper at commit 10.

Copy this file into the new repo, work through Part 1, delete the parts that
do not apply, and keep it as the record of what was decided.

---

## Part 1 — Do these on day one

### 1. Write the merge policy down (10 minutes)

Not branch protection. A paragraph.

Every project develops a rule about when it is acceptable to merge ahead of
a slow check. That rule is usually sound and almost never written down, so
it survives exactly as long as the person holding it. Write it into
`CONTRIBUTING.md` on day one, while it is still a decision rather than a
habit.

```markdown
## When to wait for CI

`main` carries no branch protection, so nothing mechanically blocks a
merge — the gate is your judgement. Stratify by what the diff touches.

**Wait for `<slow job>` to report green** when the diff touches
`<paths where that job is the only coverage>`. It is the only check
that covers `<the gap — e.g. a test/production dialect split>`, and
`<what happens downstream if a failure gets through>`.

**Merging ahead of it is fine** for changes that cannot reach
`<the risk>`: documentation, and dev-only tooling under `<path>`. The
fast job (`<lint + unit tests>`) still applies to anything containing
executable code.
```

**Why not just turn on branch protection?** Because you should measure
first. The RRW audit expected to recommend it and withdrew the
recommendation: 9 of the last 23 merges *had* gone in ahead of the slow job,
but every one of them was documentation or dev-only tooling — zero app code,
zero models, zero migrations — while every database-touching PR whose CI run could
be retrieved (3 of 4) had waited.
Protection would have added friction to ~95% of PRs to formalise a rule
already being followed. Add it when you have a second contributor, or when
you measure the policy being broken; not reflexively.

**Related, and worth checking on day one:** does your deploy pipeline
*depend* on CI, or merely run after it? In RRW the deploy job needs the
migration job but not the test job, so a red test suite does not stop a
deploy. That is a one-line fix at pipeline-creation time and an archaeology
project later.

### 2. Decide how agent config is tracked (2 minutes)

If you use an agent harness that reads config from a dotdir (`.claude/`,
`.cursor/`, `.github/copilot-instructions.md`, …), decide **now** which parts
are shared and which are local, and encode it:

```gitignore
# Harness config is local, EXCEPT the checked-in agent definitions.
.claude/*
!.claude/agents/
```

The failure mode this prevents is silent. RRW ignored `.claude/` wholesale
while keeping one agent file tracked as a historical exception; adding a
second agent file produced **no output at all** from `git status`, and it
would have been committed nowhere. A negation pattern makes the tracked
subtree the rule instead of an exception. Note that `.claude/` alone cannot
be negated into — git will not descend into an excluded directory, so the
`.claude/*` form is required.

### 3. One agent-instruction file, and keep it an index (ongoing)

- **One file, not twins.** If your tooling wants several names
  (`CLAUDE.md`, `AGENTS.md`, …), symlink them. RRW keeps two byte-identical
  files in sync by hand, with a comment in both saying no automation enforces
  it — a second unenforced convention created to serve the first.
- **Aim for an index, not an encyclopaedia.** Current practitioner guidance
  is roughly 100 lines pointing at deeper documents, on the grounds that
  instruction compliance degrades as the file grows. RRW's sits at 266 lines,
  of which about 12 bullets are genuinely normative; the rest is orientation
  that would serve better as links.
- **Watch for the same rule stated three times.** In RRW one convention
  appeared 3×, another 4×, and two adjacent sections restated the same three
  instructions back to back — including one claim ("lint is not yet in CI")
  that had been false for months in *both* copies. Duplication is where
  staleness hides, because fixing one copy feels like fixing the rule.

### 4. A fresh-context diff reviewer, from the first PR (30 minutes)

Tests catch behavioural regressions. They do not catch requirement gaps, spec
misreadings, silent scope creep, or a diff that quietly contradicts the
document describing it. On a solo project nothing else does either.

Retrofitting this means its first run is against a large surface it has no
history with. Started at PR #1, every pass is one small diff against one
small spec.

Drop this in as `.claude/agents/diff-reviewer.md` (adapt the frontmatter to
your harness):

```markdown
---
name: diff-reviewer
description: Reads a PR diff cold, with no prior context, and checks it against the specs. Use before merging, to catch requirement gaps and convention drift the test suite structurally cannot.
tools: Read, Grep, Glob, Bash
---
You review one diff with no prior context about why it was written.
Assume the tests pass — they do, and they are not what you are for.
You never edit: report, don't fix.

Read the diff (`git diff main...HEAD`). Then, for each changed area:

1. Identify which spec document governs it. Read that section. Report
   anything the diff does that the spec does not describe, and anything
   the spec requires that the diff omits.
2. Report claims in the commit message or PR body that the diff does not
   support — "also updates X" when X is untouched, "per spec Y" when Y
   says something else.
3. Report scope the diff carries beyond its stated purpose: unrelated
   fixes, drive-by renames, changes to files the stated purpose does not
   reach.
4. Report inconsistency with sibling modules — a module importing across
   a boundary its neighbours respect, a function returning a shape unlike
   its siblings, a hand-rolled thing the codebase has a helper for.
5. Where the diff changes a user-visible string, enum, or role name,
   check whether a spec document still states the old value.

Report each finding as: `file:line`, what you expected from the spec,
what the diff does, and your confidence. Report nothing if nothing is
wrong — a clean pass is a useful result, and inventing findings to look
thorough makes you worse than no reviewer.

You will not catch rendering, layout, or in-browser behaviour. Those
need a running deployment, not a reader. Say so rather than guessing.
```

**Be honest about its ceiling.** In RRW's last 30 fix commits, ~50% were
browser-only defects (a 4px misalignment, a keypress toggling a card, a
caption that was selectable) that no diff reader could catch — those need a
running deployment. ~20% were documentation corrections this would catch,
and ~30% were logic bugs where a second reader helps. The strongest evidence
for it is a P0 that a one-off external review pass found and 2,697 tests did
not: duplicate user rows from case-variant emails. The fix shipped with 265
lines of new tests, which existed only because a fresh reader thought of the
case. Tests encode what you thought of.

---

## Part 2 — The first time you have a convention worth enforcing

### 5. Turn the convention into a failing test, not a paragraph

The pattern, in one sentence: **derive the check's expectation from the code
constant it documents, so the check cannot go stale.**

RRW had a mapping from internal enum values to user-facing labels. One entry
changed on 2026-06-01. Three months later, three specification documents
still stated the old label — and the drift had survived a deliberate,
whole-folder documentation hygiene sweep that re-read those exact files.
Nothing failed, because nothing was checking. A vigilant reader missed a
three-month-old, single-word contradiction, which is what vigilance is
structurally bad at.

The generalised shape:

```python
"""Guard the documentation conventions that only prose enforces.

The rule lives in code, so drift fails a test rather than waiting to be
noticed.
"""

from __future__ import annotations

import re
from pathlib import Path

from myapp.constants import DISPLAY_LABELS  # the single source of truth

REPO = Path(__file__).resolve().parents[2]

# Live prose only — archived docs are a historical record, not a contract.
LIVE_DOCS = sorted(
    p for p in (REPO / "docs").rglob("*.md") if "archive" not in p.parts
)

# Deliberate historical references opt out; a document that is a historical
# record throughout opts out wholesale.
LINE_ESCAPE = "<!-- convention-ok -->"
FILE_ESCAPE = "<!-- convention-ok: file -->"

TABLE_ROW = re.compile(r"^\|\s*`(\w+)`\s*\|\s*\*{0,2}([A-Za-z]+)\*{0,2}\s*\|")


def test_docs_match_the_mapping() -> None:
    wrong: list[str] = []
    for doc in LIVE_DOCS:
        text = doc.read_text()
        if FILE_ESCAPE in text:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if LINE_ESCAPE in line:
                continue
            match = TABLE_ROW.match(line)
            if not match:
                continue
            key, documented = match.group(1), match.group(2)
            if key in DISPLAY_LABELS and documented != DISPLAY_LABELS[key]:
                wrong.append(
                    f"{doc.relative_to(REPO)}:{number}: `{key}` documented "
                    f"as {documented!r}, mapping says {DISPLAY_LABELS[key]!r}"
                )
    assert not wrong, (
        "documentation drift:\n  " + "\n  ".join(wrong)
        + "\nDISPLAY_LABELS is the source of truth; correct the prose, not "
        "the mapping — unless the mapping itself is what changed."
    )
```

Four design rules, each learned by getting it wrong first:

1. **Derive, never hardcode.** A check with the expected values typed into
   it is a second thing to keep in sync — the problem, restated.
2. **Give it an escape hatch, at two levels.** A line-level marker for a
   deliberate historical reference ("renamed from X in PR #N"), *and* a
   file-level marker for a document that is a historical record throughout.
   RRW shipped only the line-level one, and the very next document — an audit
   quoting the old vocabulary by the paragraph, including inside a fenced
   code block where a per-line marker cannot go — could not be marked at all.
3. **The failure message must name the remedy.** Not just what is wrong: what
   to do, including that the escape hatch exists and what it looks like.
   Otherwise the first person to hit it on a legitimate historical reference
   will "correct" it into a wrong one.
4. **Mutation-test the check.** Reintroduce each violation and confirm it
   fails again, naming the right file and line. A green check that cannot go
   red is worse than none, because it buys confidence it has not earned.

Scope it to live prose. Archived documents are a record of what was true
then; enforcing today's contract over them is noise that will get the check
disabled.

---

## Part 3 — Deliberately not recommended

Recorded because each looks obviously worth doing and is not.

- **A checker for a convention nobody wrote down.** RRW's author believed the
  documentation used British spelling. It is not stated anywhere in the
  repository, the documentation uses both forms throughout, and the agent
  instruction file uses both spellings within itself. A checker would also
  need a permanently growing allowlist, because `color`, `gray`, `catalog`
  and `normalize` are token names, primitive family names and function names
  in that codebase. **Write the convention down first — one line — and only
  then consider mechanising it.** A check for an unstated preference gets
  tuned forever and then ignored, and a check that gets ignored is worse than
  no check.
- **Branch protection, added reflexively.** See item 1. Measure whether the
  policy is actually being broken, and by what kind of change.
- **Restating a mechanised rule in the always-loaded instruction file.** Once
  a check enforces something, a paragraph describing the check is
  duplication with extra steps. A one-line pointer to the test is enough; put
  the real guidance in the failure message, where it appears exactly when
  someone needs it.
- **Test-coverage expansion as a first move.** RRW's suite is ~2,700 tests
  and catches behavioural regressions well. Its gaps are not coverage gaps —
  they are classes of defect that no test can catch, which is why items 4 and
  5 exist instead.

---

## Setup checklist

- [ ] Merge policy paragraph in `CONTRIBUTING.md` (item 1)
- [ ] Deploy pipeline *depends on* the test job, not merely ordered after it (item 1)
- [ ] Agent-config tracking encoded in `.gitignore`, both directions verified with `git check-ignore` (item 2)
- [ ] One agent-instruction file, symlinked if several names are needed (item 3)
- [ ] Fresh-context diff reviewer added before the first PR (item 4)
- [ ] First convention-as-test written the first time a code constant is described in prose (item 5)
- [ ] Nothing from Part 3 added without measuring first

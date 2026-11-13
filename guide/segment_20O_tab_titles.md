# Segment 20O — Browser tab titles as *Page · Review Robin*

**Opened:** 2026-11-13 · **Theme:** one tab-title pattern across Cordware's apps · **Related:** `guide/segment_20N_lobbies.md`, `spec/visual_style_rrw.md`

## Opportunity

Cordware's apps title their browser tabs four different ways. Apply Desk, Residential Operations, Support Logs and Utilities write *Page · App*. Review Robin writes *Page — Review Robin Web* on 18 templates. Its session pages write *Page — Session name* and its admin pages *Page — Admin*, both with no app name at all. And it calls itself *Review Robin Web*, where the landing page and the switcher say *Review Robin*. Someone with tabs open on two apps cannot tell from the tab which app a page belongs to.

The author (2026-11-13) ruled **one pattern, *Page · App***, with Review Robin's side as its own segment.

## Decision

1. **`base.html` owns the suffix.** Its `<title>` becomes `{% block title %}{% endblock %} · Review Robin`. A page names only itself, and no page can leave the app name out.
2. **The page part keeps its own context.** A session page reads *Instruments — Peer Review 2026 · Review Robin*, and an admin page *Accounts Management — Admin · Review Robin*. The `—` stays inside the page part; ` · ` separates only the app name.
3. **A page with no title of its own** reads *Review Robin*. `error.html`, which does not extend `base.html`, reads *404 — Not found · Review Robin*.
4. **The app's name in the tab is *Review Robin***, as on the landing page. The FastAPI title (`app/main.py`, seen only at `/docs`) stays *Review Robin Web*.

**Rejected: rewriting each template's block in place.** It keeps 36 suffixes that can drift apart again, which is how the three patterns arose.

## Semantics

- **An empty block** gives *Review Robin*, never a title that starts with ` · `. The base tests for an empty block.
- **Tests asserting a `<title>`** (8 files) take the new form; the doc gates read no titles.

## Judgment calls — decided

- **`·` is the separator** because four of the five apps already use it, and the author named the pattern so.

## Blast radius (measured)

Taken 2026-11-13 at `984307e17`.

| What | Count | Command |
|---|---|---|
| Templates with a title block | 36 | `grep -rl '{% block title %}' app/web/templates \| wc -l` |
| Of them ending *Review Robin Web* | 18 | `grep -rh '{% block title %}' app/web/templates \| grep -c 'Review Robin Web'` |
| Tests asserting a `<title>` | 8 files | `grep -rln '<title>' tests` |
| Specs naming *Review Robin Web* | 9 live files | `grep -rln "Review Robin Web" spec docs` |

## PR ladder

1. **Plan** (this file), its README row and its `guide/todo_master.md` entry. Prose only.
2. **The build.** `base.html`'s suffix and empty-block fallback; every title block reduced to its page part; `error.html`; tests. Must not touch the FastAPI title or any H1.
3. **Close**: `spec-writer` over the Doc impact specs; archive.

## Definition of done

- Every Review Robin page's `<title>` ends ` · Review Robin`. A test renders one operator page, one session page, one participant page, one admin page and the error page.
- No template's title block contains *Review Robin*.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 20O` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- None.

## Out of scope

- **The other apps** already follow the pattern. The host's own page (titled *Cordware*) and Utilities' landing title (*Cordware Utilities*) shipped in #3864.
- **H1s and breadcrumbs** are unchanged.

## Doc impact

- `spec/visual_style_rrw.md` — the tab title's pattern, *Page · Review Robin*, including the participant pages' and the error page's (no longer ` — Review Robin Web`).
- `spec/sessions_overview.md` — the lobby's tab title.
- `spec/email_template_editor.md` — the page's tab title, `Email Template — {session name} · Review Robin`.

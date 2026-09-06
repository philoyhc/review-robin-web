"""Which `/guide` sections a viewer sees — Segment 19E.

The Guide is one page carrying material for four audiences. This module
owns the mapping from section to audience and the decision about which
audiences a given viewer belongs to; the template owns the copy.

**The filter runs today and resolves to "everything".** Rung 2 lands the
seam with :func:`visible_audiences` returning every audience for every
viewer; rung 7 replaces that body with a real resolver and changes
nothing else. Keeping the code path live from the start means it is
exercised by every rung's tests rather than arriving untested at the end
— a seam that is built but never executed rots unobserved
(`guide/segment_19E_operator_onboarding.md` → `## Status`).

Rung 7's work is the resolver, not this shape. Role membership is not a
property of ``AuthenticatedUser``: ``is_sys_admin`` / ``is_super_admin``
are, but reviewer / observer / reviewee is a function of a person's rows
in some session's roster, resolved per-session by
``require_reviewee_in_session`` and its siblings. No workspace-level
"does this person hold any such row anywhere" query exists yet.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.auth.identity import AuthenticatedUser

OPERATOR = "operator"
REVIEWER = "reviewer"
OBSERVER = "observer"
REVIEWEE = "reviewee"

#: Every audience the Guide carries material for, in reading order.
AUDIENCES: tuple[str, ...] = (OPERATOR, REVIEWER, OBSERVER, REVIEWEE)


@dataclass(frozen=True)
class GuideSection:
    """One `/guide` card: its template key and who it is addressed to."""

    key: str
    audience: str


#: Section order is the page's reading order, and the keys are what the
#: template gates on. A section's audience is who it is *addressed to*,
#: not who is *permitted* to read it — an operator wanting to know what a
#: reviewer sees is served by the operator-facing "What your reviewers
#: experience" material, not by being shown the reviewer's own section.
SECTIONS: tuple[GuideSection, ...] = (
    GuideSection("what_it_does", OPERATOR),
    GuideSection("create_and_set_up", OPERATOR),
    GuideSection("prepare_and_launch", OPERATOR),
    GuideSection("give_access", OPERATOR),
    GuideSection("watch_progress", OPERATOR),
    GuideSection("close_and_share", OPERATOR),
    GuideSection("tips", OPERATOR),
    # Sits after the operator walkthrough and before the role-addressed
    # sections: it is the optional "see it working first" step, not part
    # of the sequence above it (19E rung 5).
    GuideSection("sample_session", OPERATOR),
    GuideSection("for_reviewers", REVIEWER),
    GuideSection("for_observers", OBSERVER),
    GuideSection("for_reviewees", REVIEWEE),
)
#: Two sections retired at 19E on the author's reading, not merged away
#: for tidiness. ``before_you_start`` told a reader how to reach and sign
#: in to the app — advice nobody reading it inside the app still needs;
#: its content moved to `/about`, where getting in is the question being
#: asked. ``getting_help`` was one sentence pointing at the Validate
#: page, which is a troubleshooting tip; it is now the last bullet of
#: ``tips`` rather than a card of its own.


def visible_audiences(user: AuthenticatedUser) -> frozenset[str]:
    """Audiences whose sections `user` should see.

    Every audience, until 19E rung 7. The parameter is unused on purpose:
    it is the signature rung 7 needs, wired now so the call site does not
    change when the body does.
    """
    del user  # rung 7 reads this; today every viewer sees everything
    return frozenset(AUDIENCES)


def visible_sections(user: AuthenticatedUser) -> frozenset[str]:
    """Section keys the template should render for `user`."""
    audiences = visible_audiences(user)
    return frozenset(s.key for s in SECTIONS if s.audience in audiences)

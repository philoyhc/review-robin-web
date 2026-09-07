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

from sqlalchemy.orm import Session

from app.db.models import User
from app.services import participants

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


def visible_audiences(db: Session, user: User) -> frozenset[str]:
    """Audiences whose sections `user` should see (19E rung 7).

    Two sources, unioned, because the roles are not exclusive — an
    operator is often also a reviewer on somebody else's session:

    - **Operator** from the workspace allowlist, using the same
      predicate ``require_operator`` gates on. Derived from that gate
      rather than restated, so a change to who counts as an operator
      cannot leave the Guide describing a different set of people from
      the one that can reach the pages it documents.
    - **Reviewer / observer / reviewee** from
      ``participants.roles_held_anywhere``, which applies the same rules
      as the three per-session gates.

    **A viewer holding nothing sees everything.** The fallback is
    deliberate and is the one judgement in this resolver. A signed-in
    person with no operator flag and no roster row anywhere is not a
    reviewer being spared the operator walkthrough — they are someone
    the app cannot classify, most often because they are about to be
    added to a roster and have arrived early. An empty Guide serves them
    nothing; the whole Guide serves them badly but not harmfully, since
    it is generic documentation carrying no session data. Given a choice
    between a page with nothing on it and a page with too much, too much
    is the recoverable error.

    This is not an access control. Nothing on `/guide` is privileged, and
    the per-section filter grants no one anything — it is an editorial
    decision about what to put in front of a reader. The gates in
    ``app/web/deps.py`` remain the only thing deciding access.
    """
    audiences: set[str] = set()
    # Mirrors ``require_operator``: sys-admin implies operator (F4).
    if user.is_operator or user.is_sys_admin:
        audiences.add(OPERATOR)
    audiences |= participants.roles_held_anywhere(db, user.email)

    if not audiences:
        return frozenset(AUDIENCES)
    return frozenset(audiences)


def visible_sections(db: Session, user: User) -> frozenset[str]:
    """Section keys the template should render for `user`."""
    audiences = visible_audiences(db, user)
    return frozenset(s.key for s in SECTIONS if s.audience in audiences)

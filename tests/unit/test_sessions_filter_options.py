"""Typeahead options for the Lobby and Archive filter boxes.

19O Item 7 entry 15. The helper mirrors the seven roster and operations
surfaces in `app/web/views/_filters.py` — tags first, then handles,
separate caps — with one deliberate divergence the tests below pin.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.web.views import SESSIONS_DATALIST_CAP, sessions_filter_options


def _s(name: str, code: str):
    return SimpleNamespace(name=name, code=code)


def test_tags_lead_then_names_and_codes() -> None:
    """Browsers filter a `<datalist>` in document order, so the partition
    values have to come first or a long session list buries them.

    Within the session half the order is a plain case-insensitive sort,
    which puts `Spring Review` above `spring-2026` — space sorts below
    hyphen. Asserting the reverse was this test's own first draft being
    wrong about its subject rather than the helper being wrong.
    """
    options = sessions_filter_options(
        [_s("Spring Review", "spring-2026")], ["Cohort B", "Cohort A"]
    )

    assert options == ["Cohort A", "Cohort B", "Spring Review", "spring-2026"]


def test_a_name_and_a_code_are_offered_separately() -> None:
    """**The divergence.** The roster boxes offer one `"Name (handle)"`
    label and exact-match the parenthesized handle when the operator
    picks it. Copying that here would ship a suggestion matching
    nothing: this filter compares *per column*, so
    `Spring Review (spring-2026)` would be tested against a name column
    holding `Spring Review` and a code column holding `spring-2026`, and
    hide every row.

    Two plain options, each matching the column it came from, is what a
    per-column filter can honour.
    """
    options = sessions_filter_options([_s("Spring Review", "spring-2026")], [])

    assert "Spring Review" in options
    assert "spring-2026" in options
    assert not any("(" in option for option in options)


def test_a_name_equal_to_its_code_collapses_to_one_option() -> None:
    """Two spellings of one identity, and here they coincide. Offering
    the same string twice would read as two sessions."""
    options = sessions_filter_options([_s("archive", "archive")], [])

    assert options == ["archive"]


def test_options_are_sorted_case_insensitively() -> None:
    """Otherwise every lower-case name sorts below every upper-case one,
    which reads as two lists rather than one."""
    options = sessions_filter_options(
        [_s("beta", "b-1"), _s("Alpha", "a-1")], []
    )

    assert options == ["a-1", "Alpha", "b-1", "beta"]


def test_blank_and_whitespace_only_values_are_dropped() -> None:
    """An empty `<option>` is an unpickable row in the operator's list."""
    options = sessions_filter_options([_s("  ", ""), _s("Real", "r-1")], [])

    assert options == ["r-1", "Real"]


def test_values_are_offered_trimmed() -> None:
    """The filter compares trimmed values, so an untrimmed suggestion
    would be a suggestion that does not match itself."""
    options = sessions_filter_options([_s("  Padded  ", " p-1 ")], [])

    assert options == ["p-1", "Padded"]


def test_the_cap_counts_sessions_not_strings() -> None:
    """The cap's subject, and the finding that made this test worth
    writing.

    A first version merged names and codes into one sorted list and
    sliced that. `len(options) == 200` was true then and is true under
    any other slicing, so the assertion could not tell the versions
    apart — the cold read caught it. What distinguishes them is *which*
    values survive.

    Here every name sorts above every code, so a string-wise cap offered
    150 names and 50 codes: the sessions past the 50th suggestible by
    one spelling of their identity and not the other.
    """
    rows = [_s(f"Session {i:04d}", f"zz-{i:04d}") for i in range(150)]

    options = sessions_filter_options(rows, [])

    names = [o for o in options if o.startswith("Session ")]
    codes = [o for o in options if o.startswith("zz-")]
    assert len(names) == 150
    assert len(codes) == 150, "a session kept its name and lost its code"


def test_a_capped_session_keeps_both_of_its_spellings() -> None:
    """The cap truncates the session list; it never halves a session."""
    rows = [_s(f"Session {i:04d}", f"code-{i:04d}") for i in range(300)]

    options = sessions_filter_options(rows, [])
    offered = set(options)

    assert len(options) == SESSIONS_DATALIST_CAP * 2
    for i in range(SESSIONS_DATALIST_CAP):
        assert f"Session {i:04d}" in offered
        assert f"code-{i:04d}" in offered
    assert f"Session {SESSIONS_DATALIST_CAP:04d}" not in offered
    assert f"code-{SESSIONS_DATALIST_CAP:04d}" not in offered


def test_which_sessions_survive_the_cap_does_not_follow_the_input_order() -> None:
    """The route hands rows over in whatever order the operator's table
    sort produced (`_lobby.py` applies the cookie sort before calling
    this). Without an explicit sort here, re-sorting the table would
    silently change *which* sessions the typeahead offers.

    The case that caught this: the cap test above feeds rows already in
    name order, so `sorted()` is a no-op in it and a mutant removing the
    sort survived. Here the input is reversed, so the two orders
    disagree about which session falls off the end.
    """
    rows = [_s(f"Session {i:04d}", f"code-{i:04d}") for i in range(201)]
    offered = set(sessions_filter_options(list(reversed(rows)), []))

    assert "Session 0000" in offered, "the cap followed the input order"
    assert "Session 0200" not in offered


def test_a_tag_equal_to_a_name_or_code_is_offered_once() -> None:
    """New with this helper's divergence, and found by the cold read.

    The seven roster surfaces cannot collide here: their handle half is
    `"Name (handle)"` and their tag half is bare, so the two shapes
    cannot be equal. Dropping the parenthesized form — necessary,
    because a per-column filter cannot match it — took that structural
    guard with it. Tags are lowercased on write and codes are commonly
    lowercase slugs, so the collision is reachable.
    """
    options = sessions_filter_options(
        [_s("cohort a", "c-1"), _s("Other", "cohort b")], ["cohort a", "cohort b"]
    )

    assert options.count("cohort a") == 1
    assert options.count("cohort b") == 1
    # The tag half still leads, and the session half loses the duplicate
    # rather than the tag half losing its place.
    assert options[:2] == ["cohort a", "cohort b"]


def test_the_tag_half_has_its_own_cap_so_sessions_cannot_crowd_it_out() -> None:
    """The reason `SEARCH_TAG_OPTIONS_CAP` is a separate constant. With
    one shared cap, 200 sessions would leave no room for any tag."""
    rows = [_s(f"Session {i:04d}", f"code-{i:04d}") for i in range(300)]

    options = sessions_filter_options(rows, ["Cohort A", "Cohort B"])

    assert options[:2] == ["Cohort A", "Cohort B"]
    assert len(options) == SESSIONS_DATALIST_CAP * 2 + 2

"""The Operator Lobby's and the Archive's view of their rows (segment AD2B
rung 6): sorting, the tag chips and the filter, all from the query string,
so a reload or a shared link keeps them.

- `sort` names a column (`SORTS`), `dir` is `asc` or `desc`; the default
  is Created, newest first. An unknown value is ignored, never echoed.
- each `tag` narrows to exercises carrying it; with `any=1` an exercise
  carrying any of them is shown instead (the *OR* chip).
- `q` keeps exercises whose name, code or a tag contains it, ignoring case.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from applydesk import locks, sample_data
from applydesk.sample_data import Exercise

#: The columns a table sorts by, as the query string names them.
SORTS = ("name", "code", "created_by", "created", "timezone", "status")
_OLDEST = datetime.min.replace(tzinfo=UTC)
_MAX_TAGS = 20  # chips a query may name; more are ignored


@dataclass(frozen=True)
class Query:
    sort: str = "created"
    descending: bool = True
    tags: tuple[str, ...] = field(default_factory=tuple)
    any_tag: bool = False
    text: str = ""

    @classmethod
    def parse(cls, params: Mapping[str, str], tags: list[str]) -> Query:
        """The query from `params` (a request's `query_params`, whose
        repeated `tag` values arrive in `tags`)."""
        sort = params.get("sort", "")
        if sort not in SORTS:
            return cls(
                tags=_tags(tags), any_tag=params.get("any") == "1", text=_text(params.get("q"))
            )
        return cls(
            sort=sort,
            descending=params.get("dir") == "desc",
            tags=_tags(tags),
            any_tag=params.get("any") == "1",
            text=_text(params.get("q")),
        )

    def href(
        self,
        base: str,
        *,
        sort: str | None = None,
        descending: bool | None = None,
        tags: tuple[str, ...] | None = None,
        text: str | None = None,
    ) -> str:
        """`base` with this query, the given parts changed."""
        q = Query(
            sort=self.sort if sort is None else sort,
            descending=self.descending if descending is None else descending,
            tags=self.tags if tags is None else tags,
            any_tag=self.any_tag,
            text=self.text if text is None else text,
        )
        pairs: list[tuple[str, str]] = []
        if (q.sort, q.descending) != ("created", True):
            pairs += [("sort", q.sort), ("dir", "desc" if q.descending else "asc")]
        pairs += [("tag", t) for t in q.tags]
        if q.any_tag and q.tags:
            pairs.append(("any", "1"))
        if q.text:
            pairs.append(("q", q.text))
        return base + ("?" + urlencode(pairs) if pairs else "")

    def any_href(self, base: str) -> str:
        """The *OR* chip's link: the chips match any tag, or all again."""
        return Query(self.sort, self.descending, self.tags, not self.any_tag, self.text).href(base)

    def sort_href(self, base: str, column: str) -> str:
        """The link a column's header follows: by it, ascending; again,
        the other way."""
        if self.sort == column:
            return self.href(base, descending=not self.descending)
        return self.href(base, sort=column, descending=column == "created")

    def tag_href(self, base: str, tag: str) -> str:
        """The link a tag chip follows: adds the tag, or takes it away."""
        if tag.casefold() in {t.casefold() for t in self.tags}:
            kept = tuple(t for t in self.tags if t.casefold() != tag.casefold())
            return self.href(base, tags=kept)
        return self.href(base, tags=(*self.tags, tag))

    def has_tag(self, tag: str) -> bool:
        return tag.casefold() in {t.casefold() for t in self.tags}

    def arrow(self, column: str) -> str:
        if self.sort != column:
            return "↕"
        return "↓" if self.descending else "↑"

    def aria_sort(self, column: str) -> str:
        if self.sort != column:
            return ""
        return "descending" if self.descending else "ascending"


def _tags(values: list[str]) -> tuple[str, ...]:
    seen: dict[str, str] = {}
    for v in values[:_MAX_TAGS]:
        v = v.strip()
        if v and len(v) <= 40 and v.casefold() not in seen:
            seen[v.casefold()] = v
    return tuple(seen.values())


def _text(value: str | None) -> str:
    return (value or "").strip()[:200]


def matches(e: Exercise, query: Query) -> bool:
    """Whether `e` passes the query's tags and filter."""
    carried = {t.casefold() for t in e.tags}
    wanted = [t.casefold() for t in query.tags]
    if wanted:
        hit = [w in carried for w in wanted]
        if not (any(hit) if query.any_tag else all(hit)):
            return False
    text = query.text.casefold()
    if text:
        words = [e.name, e.code, *e.tags]
        return any(text in w.casefold() for w in words)
    return True


def apply(
    exercises: Iterable[Exercise], query: Query, owners: Mapping[str, str]
) -> tuple[Exercise, ...]:
    """`exercises` the query keeps, in its order. Ties keep Created,
    newest first; an empty value sorts last whichever way."""
    kept = [e for e in sample_data.newest_first(exercises) if matches(e, query)]
    key = _KEYS[query.sort]
    filled = [(k, e) for e in kept if (k := key(e, owners)) is not None]
    empty = [e for e in kept if key(e, owners) is None]
    filled.sort(key=lambda pair: pair[0], reverse=query.descending)
    return tuple([e for _, e in filled] + empty)


def _offset(zone: str) -> tuple[float, str]:
    found = ZoneInfo(zone).utcoffset(datetime.now(UTC).replace(tzinfo=None))
    return (found.total_seconds() if found else 0.0, "")


def _created(e: Exercise) -> tuple[float, str] | None:
    at = sample_data.created_at(e)
    return (at.timestamp(), "") if at else None


def _words(value: str) -> tuple[float, str] | None:
    return (0.0, value.casefold()) if value else None


#: Each column's key: a (number, text) pair, so every key compares.
_KEYS: dict[str, Callable[[Exercise, Mapping[str, str]], tuple[float, str] | None]] = {
    "name": lambda e, _o: _words(e.name),
    "code": lambda e, _o: _words(e.code),
    "created_by": lambda e, o: _words(o.get(e.public_id, "")),
    "created": lambda e, _o: _created(e),
    "timezone": lambda e, _o: _offset(sample_data.timezone(e)),
    "status": lambda e, _o: (float(locks.STATUS_ORDER.index(locks.exercise_status(e))), ""),
}

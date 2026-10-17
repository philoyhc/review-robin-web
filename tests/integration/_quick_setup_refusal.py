"""Read a refused Quick Setup upload off the page it answers with.

A refusal on an existing session renders Session Home again at 422
(findings O7) rather than redirecting with the banner in the URL, so a
test reads the slot, reason and lines from the one visible
``quick-setup-{kind}-error-banner``."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

_BANNER = re.compile(
    r'id="quick-setup-(\w+)-error-banner"\s+data-quick-setup-reason="([\w-]*)"'
)
_LINE = re.compile(r"<li>(.*?)</li>", re.S)


@dataclass(frozen=True)
class Refusal:
    kind: str
    reason: str
    details: list[str]
    lead: str


def refusal(response) -> Refusal:
    """The refused slot, its reason token, the banner's lead sentence and
    the lines listed under it; asserts the 422 re-render."""
    assert response.status_code == 422, (response.status_code, response.text[:300])
    text = response.text
    found = list(_BANNER.finditer(text))
    assert len(found) == 1, f"expected one visible banner, found {len(found)}"
    match = found[0]
    body = text[match.end() : text.index('class="banner-actions"', match.end())]
    lead = re.search(r'<p class="banner-lead">(.*?)</p>', body, re.S)
    details_block = re.search(
        r"<ul data-quick-setup-error-details>(.*?)</ul>", body, re.S
    )
    return Refusal(
        kind=match.group(1),
        reason=match.group(2),
        details=[
            html.unescape(line)
            for line in _LINE.findall(details_block.group(1) if details_block else "")
        ],
        lead=html.unescape(lead.group(1)) if lead else "",
    )

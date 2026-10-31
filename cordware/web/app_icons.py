"""Each registered application's favicon, as the host's landing page
draws it before the application's name (author, 2026-10-31).

Copies, not the source: each application's own templates own its icon
(`app/web/templates/base.html`, `residentialapps/web/templates/residential/
base.html`, `utilityapps/templates/utilities/base.html`), and
`cordware/tests/test_landing.py` fails when a copy here drifts from them.
Inline SVG data URIs, every `#` escaped as `%23`."""

from __future__ import annotations

REVIEW_ROBIN = (
    "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🐦</text></svg>"
)
RESIDENTIAL_OPERATIONS = (
    "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='%23a21caf'/><path d='M7 16l9-8 9 8M10 13.5V24h12V13.5M14.5 24v-5h3v5' fill='none' stroke='%23fff' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'/></svg>"
)
SUPPORT_LOGS = (
    "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='%230f766e'/><rect x='9' y='7' width='14' height='18' rx='2' fill='none' stroke='%23fff' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'/><path d='M12.5 12h7M12.5 16h7M12.5 20h4' fill='none' stroke='%23fff' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'/></svg>"
)
UTILITIES = (
    "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='%23b45309'/><g transform='translate(7 7) scale(0.75)'><path d='M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z' fill='none' stroke='%23fff' stroke-width='3.2' stroke-linecap='round' stroke-linejoin='round'/></g></svg>"
)

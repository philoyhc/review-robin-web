"""Each registered application's favicon, as the host's landing page
draws it before the application's name (author, 2026-10-31).

Copies, not the source: each application's own templates own its icon
(`app/web/templates/base.html`, `residentialapps/web/templates/residential/
base.html`, `utilityapps/templates/utilities/base.html`), and
`cordware/tests/test_landing.py` fails when a copy here drifts from them.
Inline SVG data URIs, every `#` escaped as `%23`."""

from __future__ import annotations

REVIEW_ROBIN = (
    "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><defs><clipPath id='t'><rect width='32' height='32' rx='7'/></clipPath></defs><g clip-path='url(%23t)'><rect width='32' height='32' fill='%232563eb'/><path d='M0.00 27.61 0.09 28.38 0.30 29.12 0.64 29.81 1.09 30.44 1.64 30.98 2.28 31.42 2.98 31.74 3.84 31.95 4.50 32.00 28.05 31.97 29.12 31.70 30.09 31.18 30.91 30.44 31.52 29.52 31.84 28.70 31.98 27.94 32.00 23.98 31.83 23.97 31.82 23.82 31.34 23.50 29.90 22.01 28.53 20.38 27.29 18.67 25.85 16.25 24.15 12.53 23.25 10.80 22.19 9.19 20.95 7.74 19.48 6.51 18.66 5.99 17.76 5.55 16.76 5.22 15.74 5.02 14.71 4.95 13.69 5.01 12.17 5.37 11.48 5.65 10.76 6.05 10.11 6.50 9.38 7.14 8.72 7.87 7.88 8.98 7.48 9.34 6.76 9.70 4.68 10.23 3.47 10.69 2.59 11.30 2.14 11.84 2.08 12.06 2.07 12.24 2.99 12.69 4.04 12.99 5.91 13.37 7.13 13.84 7.71 14.27 8.18 14.78 8.63 15.49 8.98 16.29 9.20 17.52 9.13 18.79 8.91 19.80 7.71 24.06 7.47 25.38 7.39 26.49 7.43 27.83 7.62 29.15 7.96 30.41 8.43 31.53 8.45 31.73 6.70 31.78 5.93 31.72 4.75 31.30 3.80 30.82 2.73 30.07 1.80 29.17 1.03 28.11 0.54 27.16 0.18 25.99 0.03 24.79 0.00 12.49ZM14.24 8.46 14.66 8.82 14.98 9.35 14.99 9.94 14.82 10.48 14.44 10.92 13.93 11.18 13.36 11.22 12.81 11.06 12.42 10.71 12.12 10.17 12.05 9.57 12.21 9.09 12.66 8.56 13.09 8.34 13.66 8.28Z' fill='%23fff'/></g></svg>"
)
RESIDENTIAL_OPERATIONS = (
    "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><defs><clipPath id='t'><rect width='32' height='32' rx='7'/></clipPath></defs><g clip-path='url(%23t)'><rect width='32' height='32' fill='%23a21caf'/><path d='M15.5 6.5 L37 25 L33 25 L33 40 L7 40 L7 21.5 L3.5 21.5 Z' fill='%23fff' stroke='%23fff' stroke-width='1.6' stroke-linejoin='round'/><rect x='14' y='27' width='6.5' height='12' rx='1.5' fill='%23a21caf'/></g></svg>"
)
SUPPORT_LOGS = (
    "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><defs><clipPath id='t'><rect width='32' height='32' rx='7'/></clipPath></defs><g clip-path='url(%23t)'><rect width='32' height='32' fill='%230f766e'/><rect x='7' y='5.5' width='34' height='38' rx='3.5' fill='%23fff'/><rect x='11.5' y='12' width='24' height='2.8' rx='1.4' fill='%230f766e'/><rect x='11.5' y='18' width='24' height='2.8' rx='1.4' fill='%230f766e'/><rect x='11.5' y='24' width='14' height='2.8' rx='1.4' fill='%230f766e'/></g></svg>"
)
UTILITIES = (
    "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><defs><clipPath id='t'><rect width='32' height='32' rx='7'/></clipPath></defs><g clip-path='url(%23t)'><rect width='32' height='32' fill='%23b45309'/><g transform='translate(42.5 0.5) scale(-1.75 1.75)'><path d='M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z' fill='%23fff' stroke='%23fff' stroke-width='1.2' stroke-linejoin='round'/></g></g></svg>"
)

# Assumptions

A living record of the load-bearing assumptions — both domain
shape and visual conventions — that the app is built around.
Update this file when you introduce a new structure or named
style; reference these names in code reviews and PR descriptions
instead of describing them from scratch.

## Domain

### Hierarchy of structures

#### Session

Contains the same universe of Reviewers, Reviewees, Assignments,
1-6 Instruments and their associated Response Forms, Email,
deadline.

At any one time, operating under one assignment mode (FullMatrix,
Manual, RuleBased; note that FullMatrix should be absorbed as a
particular rule set).

Status: Draft, Ready (when populated sufficiently, within
deadline), Expired (when deadline has passed), Archived (data
collected has been downloaded and deleted).

Session can be edited when instruments are closed/paused; if there
are ongoing reviews, reviewers need to be notified.

Note: While Session is the top level structure, there should be a
way to put arbitrarily assign them to Groups. Sessions can be
duplicated (without the response data).

#### Instrument

Associated with one set of response questions (ratings, comments,
etc.) and their instructions.

Status: Draft, Receiving responses, Closed/Paused.

Closed/Paused defaults to keeping existing responses invisible to
reviewers, but visibility can be turned on.

Instrument can be edited when closed/paused; if there are ongoing
reviews, reviewers need to be notified.

Instrument automatically closes upon session deadline.

## UI

### Button styles

The app uses four canonical button styles. Each is described by
**affordance × treatment** (`primary`/`danger` × `solid`/`outline`):

| Name | Fill | Text | Stroke | Use for |
|---|---|---|---|---|
| **Primary** | blue (`#2563eb`) | white | blue (`#2563eb`) | Default action: form submit, navigation, "do the thing". |
| **Primary Outline** | white | blue (`#2563eb`) | blue (`#2563eb`) | Secondary action that lives next to a Primary, or a non-destructive sibling action. |
| **Danger** | red (`#b91c1c`) | white | red (`#b91c1c`) | Destructive confirm action — final step that actually deletes / wipes data. |
| **Danger Outline** | white | red (`#b91c1c`) | red (`#b91c1c`) | Destructive entry point that opens a confirmation step (e.g. a "Delete…" link that reveals the real Danger button). |

#### Where each style currently lives in CSS

The styles are realized through the `.btn` family in
`app/web/templates/base.html`:

- **Primary** — `.btn` (default, no modifier).
- **Primary Outline** — `.btn.secondary`.
- **Danger** — `.btn.danger-solid`. (The danger-zone confirm
  buttons in `session_detail.html` still use inline-style
  overrides on `.btn` for the same red fill — candidate to be
  migrated to `.btn.danger-solid` next time those forms are
  touched.)
- **Danger Outline** — `.btn.danger`.

#### CTA variant

`.btn-cta` is a layout-and-prominence variant of **Primary** used
for the four cards-page-level Run Session buttons and for the
Session Setup row buttons. It uses the same blue fill and white
text as Primary, but renders as a centered flex container so
multi-line labels stay vertically aligned in equal-height rows.
It is not a fifth style — it's "Primary, large and centered".

Buttons should not stack a `.btn-cta` modifier with `.danger`;
if a CTA is destructive, treat that as a new red-fill CTA variant
and add it explicitly to this taxonomy.

### Typography

- Root font size is set on `html` as a percentage so all
  `em` / `rem` measurements scale from one knob (currently `100%`,
  i.e. browser default ~16px). Tune via that single rule rather
  than hardcoding pixel values on individual elements.

### Layout

- Pages whose body splits into two parallel groupings use the
  `.page-grid` two-column pattern documented in
  `spec/operator_map.md` ("Page layout — two-column option").
- Pages whose body is a single linear flow keep the default
  single-column layout — no wrapper grid needed.

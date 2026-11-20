# Findings — Cordware Utilities in the corpus sweep (2026-11-20)

**Found by:** RRW's `guide/sweep_2026-11-20_corpus.md`, read S4, the first sweep to read the packages' prose (segment 23H) · **Read at:** RRW `6003c8084` (#4063) · **Open:** all rows.

Cordware Utilities's share of the sweep's findings, kept beside its own plans; RRW's are in RRW's `guide/findings_2026-11-20_corpus.md`. Nothing was edited by the sweep, and the fixes ship as Cordware Utilities's own work. A row is struck when done, with its PR, or marked declined with the reason. **Decides:** *spec* (the spec is wrong; an update fixes it), *author* (a choice for the author), *trim* (history to strip, keeping its reason); in `docs/` rows *doc* plays *spec*. Line numbers are at `6003c8084`.

## Per file

- **S1** `spec/utilities.md` (the "Retention" bullet) and `spec/email_check.md:204`: two bullets run together. Spec.
- **S2** `spec/utilities.md:6-8` cites the frozen v0.1 checker spec with no superseded note. Spec.
- **S3** `README.md:51`, `:54` say "(proposed)" for the checker and the egress probe; both are built. Doc.

The four `docs/` files are frozen handovers and specs, correctly treated as such; the limits, constants and routes in both specs match the code.

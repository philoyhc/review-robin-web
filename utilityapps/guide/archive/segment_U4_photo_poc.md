# Segment U4 — Utilities: photo upload proof of concept

**Opened:** 2026-11-12 · **Theme:** a participant photo uploaded, cropped to a fixed window, resized and kept in Postgres, with no Blob storage · **Related:** `guide/blob_storage_candidates.md` (candidate #5, hosted photos), `utilityapps/spec/utilities.md`, `guide/archive/segment_23A_interop_poc.md` (the last Utilities proof of concept), Cordware's `postgres-utilityapps-database.yml` (the database, readied 2026-11-12)

## Opportunity

Review Robin shows a reviewee's photo only as an external `profile_link`, and ApplyDesk's uploads wait on Blob storage, which needs IT (ApplyDesk gate G8). Photos are the one kind of upload that can be made safe without Blob: re-encoded by the server, the bytes kept are bytes the server wrote. Nothing has proved that path on Cordware yet: an upload, a crop the user controls, a resize, a row in Postgres and an authorized read. Utilities' own database, `utilityapps`, exists since 2026-11-12 and holds nothing.

## Decision

**A super-admin tool at `/utilities/photo-poc/`**, as the author laid it out (2026-11-12):

1. **Choose or drop** a photo, 5 MB at most.
2. It shows **against a fixed window**, whose shape is the saved photo's aspect ratio.
3. The user **zooms** it in or out and **drags** it within the window; the photo always covers the window.
4. **Save** keeps exactly what is inside the window. Every saved photo has the same aspect ratio and size.
5. Saved photos are **listed and shown back**, each served by an authorized route, and can be deleted.

**The server crops, not the browser.** The browser sends the original file and the window's rectangle in the image's own pixels; the server opens the file, checks the rectangle, crops, resizes and re-encodes. The browser's canvas could crop instead, but then the bytes kept would be the browser's, and the server would still have to decode and re-encode them to be safe. One authoritative path is simpler to test.

**Rejected:**
- **Blob storage**: not available without IT, and the point of the proof of concept is to need none.
- **Storing the original**: it carries what the crop removed and its metadata (EXIF, GPS). Only the re-encoded crop is kept.
- **A JavaScript cropping library**: the repository adds no framework; a small inline script with pointer events and a range input does it.

## Semantics

- **Upload limits.** 5 MB, checked in the browser for a quick answer and again by the server, which reads at most 5 MB + 1 byte. Accepted: whatever Pillow decodes as JPEG, PNG or WebP; anything else is refused with a message. ~~Pillow's decompression-bomb limit is set low~~ The service refuses beyond about 40 megapixels itself, from the header, before decoding (rung 3, Status).
- **Orientation.** The browser draws a photo with its EXIF orientation applied, so the window is described in the oriented image's pixels; the server applies `ImageOps.exif_transpose` before cropping, so both read the same picture.
- ~~**The rectangle.** Integers inside the image, with the window's aspect ratio to within one pixel of rounding~~ **The window** (`Frame`, from the rotate iteration): its center, width and the photo's turn, plain decimals; the height follows from 4:5. Every corner must lie over the photo to within a pixel, otherwise refused. The server never trusts the browser's window to be in bounds.
- **What is kept.** The crop resized to 480 × 600 px (the window is 4:5), RGB, JPEG at quality 85, no metadata. Expected size about 50–100 KB. One row per photo: a public ID (RRW's alphabet), who uploaded it, when, the bytes, their SHA-256, width and height.
- **Reading back.** `GET /utilities/photo-poc/photos/<id>.jpg` checks the same super-admin guard, sends `Cache-Control: private, no-store` and an `ETag`; a malformed or unknown ID is a 404.
- **Retention.** A proof of concept on the author's own test photos: each can be deleted, and the segment's close deletes the table's rows unless the author keeps them. Real participant photos need a retention rule first (PDPA).

## Judgment calls — decided

- **Testing locally** (author asked, 2026-11-12): the database falls back to a SQLite file, so the whole tool runs on `uvicorn` with fake auth as the super-admin at `/utilities/photo-poc/`; Postgres is exercised by CI's round-trip and on Azure.

- **Utilities' own Alembic history** (`utilityapps/alembic/`), not a table in RRW's: the database is Utilities', and the import boundary forbids sharing RRW's models.
- **The connection string** is read from `UTILITYAPPS_DATABASE_URL`, already set on the App Service as a Key Vault reference; locally a SQLite file, as RRW's default.
- **Pillow** is a new runtime dependency, added to `pyproject.toml` and `requirements.txt` together.

## Blast radius (measured)

Taken 2026-11-12 at `12cba9a`.

| What | Count | Command |
|---|---|---|
| Utilities' database code today | 0 files | `grep -rln "sqlalchemy" utilityapps --include=*.py \| wc -l` |
| Utilities' tools today | 3 (`email_check`, `diagnostics`, `interop_poc`) | `ls -d utilityapps/*/ \| grep -v -e docs -e guide -e spec -e tests -e templates -e __pycache__` |
| Pillow in the dependencies | 0 | `grep -c -i pillow pyproject.toml requirements.txt` |
| Cordware's release migration table | 1 row (`reviewrobin`) | Cordware `grep -n '"files"' .github/workflows/release.yml` |

## Status

**Closed 2026-11-13** (author: "can close it"), the Cordware rung moved out: rungs 1–5 merged (`#3822`–`#3826`), plus the iteration and refinement the author's local checks asked for. Cordware's rung is its own PR, cordware#212, held as a draft until the import that brings `utilityapps/alembic/`; until then the tool runs locally and nowhere on Azure.

Intended vs done:
- **Database, service, page, wiring** as planned. Utilities' history records itself in `utilityapps_alembic_version`, so CI round-trips it beside RRW's on one Postgres database.
- **The window became a frame, not a rectangle** (author's check: "add ability to rotate; make zoom and rotate usable with two finger touch"): the browser sends center, width and the photo's turn; the server cuts the corners' bounding box, turns it and crops, so a large photo is never turned whole. The zoom bar stands upright on the window's right, the rotate bar below it, snapping to −90°, 0° and 90° within 4° when dragged.
- **Safety, as built:** the service refuses beyond 40 Mpx from the header before decoding (Pillow's own guard fires only near 179 Mpx); EXIF orientation applied, color profiles converted to sRGB, metadata and inherited `info` dropped, transparency on white; writes take an `X-Photo-Poc: 1` header a cross-site form cannot send; every route, the image's included, is the super-admin's.
- **Reads:** one `diff-reviewer` read at rung 5, one on the iteration, one on the refinement, and Codex on each PR. They caught the stretched save near a quarter turn, an inherited JPEG comment, a phone's `MPO` JPEG refused, and keys that could not leave a snap point; all fixed. Accepted for the proof of concept: a 40 Mpx upload can take a few hundred MB while it is processed, and the image's `ETag` earns a `304` only from a client that sends `If-None-Match`, which `no-store` makes rare.
- **Not done here:** the release's migration and a check on Azure (Definition of done, lines 1 and 5) wait on cordware#212 and the import. **Retention:** nothing was saved on Azure; local test photos are the author's.

## PR ladder

1. **Plan** (this file).
2. **The database.** `utilityapps/db.py` (engine and session from `UTILITYAPPS_DATABASE_URL`), `utilityapps/alembic/` with the first migration (the `photo_poc_photos` table), and the Postgres round-trip of that history in CI beside RRW's. No page.
3. **The service.** Pillow; `utilityapps/photo_poc/service.py`: validate, orient, check the rectangle, crop, resize, encode, save, read, delete. Unit tests for each refusal, orientation, metadata stripped, the output size, and the bomb limit.
4. **The page, scaffold-first.** The drop box, the window, the zoom control and Save, inert; the saved-photos list on sample tiles.
5. **Wiring.** The cropping script, the upload, the list and the read-back route, delete; a browser test that drops a photo, zooms, saves and reads it back. Last build rung: `diff-reviewer` reads the cumulative diff.
6. ~~**Cordware.**~~ Moved to cordware#212, held for the import (closed without it, 2026-11-13).
7. **Close.**

## Definition of done

- A super-admin drops a photo of up to 5 MB, zooms and drags it in the window, saves, and sees it in the list at the fixed size and ratio (author's browser check, locally; on Azure after cordware#212).
- A non-image, an over-size file, a decompression bomb and an out-of-bounds window are each refused with a message (tests).
- Saved bytes carry no EXIF (test); a rotated phone photo saves upright (test and browser check).
- Anyone but the super-admin gets `403` on every route, the image route included (test).
- ~~`utilityapps` migrates in the release (Cordware run).~~ With cordware#212, after the import.
- `## Doc impact` section present and current
- `python3 tools/close_check.py U4` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- ~~The window's ratio and output size~~: portrait **4:5 at 480 × 600 px** (author, 2026-11-12).
- ~~JPEG or WebP~~: **JPEG** (author, 2026-11-12).

## Out of scope

- Using the photos anywhere else: Review Robin's `profile_link` and ApplyDesk's applicants decide that after the proof of concept.
- Documents and other uploads: they cannot be made safe by re-encoding and still need Blob with scanning (ApplyDesk G8).
- Moderation and quotas beyond the 5 MB limit.

## Doc impact

- `utilityapps/spec/utilities.md` — the photo tool's page and routes, and Utilities' database: the factory now opens one (rungs 2–5).
- `utilityapps/README.md` — the new modules, `alembic/` and this plan (rungs 1–5).
- `guide/blob_storage_candidates.md` — candidate #5 met without Blob, for photos only (at close).

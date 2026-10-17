"""A session code a header cannot hold still downloads (findings R2).

The filename went into ``Content-Disposition`` raw, so a code past
Latin-1 made every CSV and zip download answer 500.
"""

from __future__ import annotations

from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession

CODE = "日本-Café"


@pytest.mark.parametrize(
    "path, name",
    [
        ("export/reviewers.csv", f"{CODE}_reviewers.csv"),
        ("export/settings.csv", f"{CODE}_settings.csv"),
        ("export/bundle.zip", f"{CODE}_setup.zip"),
    ],
)
def test_a_non_latin_code_downloads_with_both_filenames(
    client: TestClient, db: Session, path: str, name: str
) -> None:
    resp = client.post(
        "/operator/sessions",
        data={"name": "Unicode", "code": CODE},
        follow_redirects=False,
    )
    assert resp.status_code == 303, resp.text
    session_id = db.execute(
        select(ReviewSession.id).where(ReviewSession.code == CODE)
    ).scalar_one()

    resp = client.get(f"/operator/sessions/{session_id}/{path}")

    assert resp.status_code == 200, resp.text
    header = resp.headers["content-disposition"]
    assert 'filename="__-Cafe_' in header
    assert f"filename*=UTF-8''{quote(name, safe='')}" in header

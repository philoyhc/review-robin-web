"""A free-text session code names every zip member, made safe as one
(findings O1, 2026-10-22; `spec/extract_data.md` "Zip member names").

A code like ``../../evil`` once put ``../../evil_reviewers.csv`` in every
bundle, which an unzip tool that trusts member names writes outside its
folder. Now a path separator, a character Windows refuses or a control
character becomes ``_`` and leading dots and spaces go; anything else,
non-Latin characters included, is kept.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession
from app.services.extracts.zip_bundle import _member_name


def _session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Zip names", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _members(client: TestClient, review_session: ReviewSession, path: str) -> list[str]:
    response = client.get(f"/operator/sessions/{review_session.public_id}/export/{path}")
    assert response.status_code == 200, response.text
    return zipfile.ZipFile(io.BytesIO(response.content)).namelist()


@pytest.mark.parametrize(
    ("name", "safe"),
    [
        ("../../evil_reviewers.csv", "_.._evil_reviewers.csv"),
        ("2026/Q1_reviewers.csv", "2026_Q1_reviewers.csv"),
        ("a\\b:c*d?e\"f<g>h|i_settings.csv", "a_b_c_d_e_f_g_h_i_settings.csv"),
        ("tab\there_responses.csv", "tab_here_responses.csv"),
        (" .hidden_reviewers.csv", "hidden_reviewers.csv"),
        ("课程 2026_reviewers.csv", "课程 2026_reviewers.csv"),
        ("PSY-101_reviewers.csv", "PSY-101_reviewers.csv"),
        ("nel\x85here_reviewers.csv", "nel_here_reviewers.csv"),
        ("\uff0e\uff0e\uff0fevil_reviewers.csv", "\uff0e\uff0e_evil_reviewers.csv"),
        ("a\u2215b\u2044c_reviewers.csv", "a_b_c_reviewers.csv"),
        ("abc\u202edcba_reviewers.csv", "abc_dcba_reviewers.csv"),
        ("..\ufe68..\ufe68evil_reviewers.csv", "_.._evil_reviewers.csv"),
        ("a\uff1ab\u29f8c_reviewers.csv", "a_b_c_reviewers.csv"),
        ("l\u200em\u200fn\u061co_reviewers.csv", "l_m_n_o_reviewers.csv"),
    ],
)
def test_a_member_name_is_made_safe(name: str, safe: str) -> None:
    assert _member_name(name) == safe


def test_a_traversing_code_stays_inside_every_bundle(
    client: TestClient, db: Session
) -> None:
    review_session = _session(client, db, "../../evil")
    for path in ("bundle.zip", "responses_bundle.zip", "by_instrument_bundle.zip"):
        names = _members(client, review_session, path)
        assert names, path
        for name in names:
            assert "/" not in name and "\\" not in name, (path, name)
            assert not name.startswith("."), (path, name)
            assert name.startswith("_.._evil_"), (path, name)


def test_a_plain_code_keeps_its_member_names(
    client: TestClient, db: Session
) -> None:
    review_session = _session(client, db, "PSY-101")
    assert sorted(_members(client, review_session, "bundle.zip")) == [
        "PSY-101_relationships.csv",
        "PSY-101_reviewees.csv",
        "PSY-101_reviewers.csv",
        "PSY-101_settings.csv",
    ]

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.db.models import Assignment, ReviewSession

from ._full_matrix import generate_via_page_button, mark_band1_touched_on_all_instruments, pin_full_matrix_on_all_instruments


def _roster(kind: str, n: int) -> bytes:
    if kind == "reviewers":
        return b"ReviewerName,ReviewerEmail\n" + b"".join(
            f"R{i},r{i}@example.edu\n".encode() for i in range(n)
        )
    return b"RevieweeName,RevieweeEmail\n" + b"".join(
        f"E{i},e{i}@example.edu\n".encode() for i in range(n)
    )


def _seeded(client, db, n, code):
    assert client.post(
        "/operator/sessions",
        data={"name": f"Pre{n}", "code": code, "description": "d"},
        follow_redirects=False,
    ).status_code == 303
    session = db.execute(select(ReviewSession).where(ReviewSession.code == code)).scalar_one()
    for kind in ("reviewers", "reviewees"):
        client.post(
            f"/operator/sessions/{session.id}/{kind}/import",
            files={"file": (f"{kind}.csv", _roster(kind, n), "text/csv")},
            follow_redirects=False,
        )
    mark_band1_touched_on_all_instruments(db, session.id)
    pin_full_matrix_on_all_instruments(db, session.id)
    generate_via_page_button(client, session.id)
    return session


def _count_queries(db, fn):
    total = 0

    def cb(conn, cursor, statement, params, context, many):
        nonlocal total
        total += 1

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", cb)
    try:
        fn()
    finally:
        event.remove(engine, "before_cursor_execute", cb)
    return total


def test_zz_measure(client: TestClient, db: Session) -> None:
    for n, code in [(25, "ZZ25"), (50, "ZZ50"), (100, "ZZ100"), (200, "ZZ200")]:
        session = _seeded(client, db, n, code)
        a_q = _count_queries(db, lambda: client.get(f"/operator/sessions/{session.id}/assignments"))
        i_q = _count_queries(db, lambda: client.get(f"/operator/sessions/{session.id}/invitations"))
        r_q = _count_queries(db, lambda: client.get(f"/operator/sessions/{session.id}/responses"))
        print(f"{n}x{n}: assignments={len(db.execute(select(Assignment).where(Assignment.session_id==session.id)).scalars().all())} A={a_q} I={i_q} R={r_q}")

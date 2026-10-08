"""`session.workflow_run_failed` must survive the request that writes it.

19O Item 7 entry 7. `audit.write_event` ends in `db.flush()`, not
`db.commit()`, and the Prepare failure path returns a redirect without
committing — so in production the connection closes and the row is
discarded. Every existing test asserting this event passes anyway,
because the default `db` fixture wraps the request in a SAVEPOINT the
test session shares.

This file uses the `committed_client` harness written for exactly that
class of bug: a real connection per request, and a *separate* session
to verify. See `tests/integration/conftest.py`, "Real-commit harness".
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.db.models import AuditEvent, ReviewSession


def _session_id(client: TestClient, engine: Engine, code: str) -> int:
    response = client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    with Session(bind=engine) as verify:
        return verify.execute(
            select(ReviewSession.id).where(ReviewSession.code == code)
        ).scalar_one()


def _events(engine: Engine, session_id: int, event_type: str) -> list[AuditEvent]:
    with Session(bind=engine) as verify:
        return list(
            verify.execute(
                select(AuditEvent)
                .where(AuditEvent.session_id == session_id)
                .where(AuditEvent.event_type == event_type)
            ).scalars()
        )


def test_a_failed_prepare_persists_its_audit_event(
    committed_client: TestClient, committed_engine: Engine
) -> None:
    """A Prepare that fails validation writes `workflow_run_failed`. The
    operator's redirect carries `super_status=failed`, so the *screen*
    is right either way — the audit trail is the only record that the
    run happened, and it is the one that was being dropped.
    """
    session_id = _session_id(committed_client, committed_engine, "fail-audit")
    # Reviewers but no reviewees: past the `is_editable` precondition,
    # so the run starts, and a blocking validation error stops it at the
    # `validate` step — the path that writes the event.
    committed_client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nRae,rae@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )

    response = committed_client.post(
        f"/operator/sessions/{session_id}/workflow/prepare",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert "super_status=failed" in response.headers["location"], (
        "Prepare did not fail; this test is not exercising the failure path: "
        f"{response.headers['location']}"
    )

    started = _events(committed_engine, session_id, "session.workflow_run_started")
    failed = _events(committed_engine, session_id, "session.workflow_run_failed")

    # The started event is the control. Both are written by the same
    # `write_event` in the same request, so if only one survives the
    # difference is the commit, not the write.
    assert started, "workflow_run_started did not persist either"
    assert failed, (
        "workflow_run_failed did not survive the request: "
        "`audit.write_event` flushes and the failure path returns without "
        "committing"
    )
    assert failed[0].detail["context"]["step"] == "validate"


def test_a_prepare_failing_at_generate_keeps_its_started_event(
    committed_client: TestClient, committed_engine: Engine, monkeypatch
) -> None:
    """Generate is one unit that rolls itself back on failure (19U Item 1),
    so a Prepare that fails there must have committed its
    `workflow_run_started` first, or the run would be audited as a
    failure with no start."""
    import app.services.assignments._generate as generate

    session_id = _session_id(committed_client, committed_engine, "fail-gen")

    def _boom(*_args, **_kwargs):
        raise ValueError("generate failed")

    monkeypatch.setattr(generate, "_load_reconcile_inputs", _boom)

    response = committed_client.post(
        f"/operator/sessions/{session_id}/workflow/prepare",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert "super_step=generate" in response.headers["location"]

    assert _events(committed_engine, session_id, "session.workflow_run_started")
    assert _events(committed_engine, session_id, "session.workflow_run_failed")


def test_a_prepare_failing_unexpectedly_records_its_failure(
    committed_client: TestClient, committed_engine: Engine, monkeypatch
) -> None:
    """An exception the route does not expect still answers 500, but the
    committed `workflow_run_started` gets its `workflow_run_failed`, and
    nothing the failed step flushed lands with it (findings Bc7)."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    import app.services.assignments._generate as generate

    session_id = _session_id(committed_client, committed_engine, "fail-odd")

    def _boom(*_args, **_kwargs):
        raise IntegrityError("INSERT", {}, Exception("duplicate"))

    monkeypatch.setattr(generate, "_load_reconcile_inputs", _boom)

    with pytest.raises(IntegrityError):
        committed_client.post(
            f"/operator/sessions/{session_id}/workflow/prepare",
            follow_redirects=False,
        )

    assert _events(committed_engine, session_id, "session.workflow_run_started")
    failed = _events(committed_engine, session_id, "session.workflow_run_failed")
    assert len(failed) == 1
    assert failed[0].detail["context"]["step"] == "generate"
    assert failed[0].detail["context"]["error_message"] == (
        "Unexpected error (IntegrityError)."
    )
    with Session(bind=committed_engine) as verify:
        assert verify.get(ReviewSession, session_id).status == "draft"


def test_activate_commits_its_started_event_before_the_warnings_detour(
    committed_client: TestClient, committed_engine: Engine, monkeypatch
) -> None:
    """The warnings detour pauses the run rather than failing it, but the
    click's `workflow_run_started` must still survive the request
    (findings Bc6)."""
    from types import SimpleNamespace

    import app.web.routes_operator._workflow as workflow

    session_id = _session_id(committed_client, committed_engine, "act-detour")
    with Session(bind=committed_engine) as setup:
        setup.get(ReviewSession, session_id).status = "validated"
        setup.commit()

    monkeypatch.setattr(workflow.validation, "validate_session_setup", lambda *_: [])
    monkeypatch.setattr(
        workflow.lifecycle,
        "build_readiness_report",
        lambda _issues: SimpleNamespace(
            can_activate=True, has_non_blocking_findings=True, errors=[]
        ),
    )

    response = committed_client.post(
        f"/operator/sessions/{session_id}/workflow/activate",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert "/validate" in response.headers["location"], (
        "Activate did not take the warnings detour: "
        f"{response.headers['location']}"
    )

    started = _events(committed_engine, session_id, "session.workflow_run_started")
    assert len(started) == 1
    assert started[0].detail["context"]["button"] == "activate_session"
    assert not _events(committed_engine, session_id, "session.workflow_run_failed")
    with Session(bind=committed_engine) as verify:
        assert verify.get(ReviewSession, session_id).status == "validated"

"""Sync: fetch -> validate -> store as a new snapshot.

A failed sync never deletes or overwrites the last good snapshot. The dashboard
keeps showing the last successful data and reports the failure alongside it.
"""

import logging

from sqlmodel import Session, select

from app.integrations.sources import DataSource, SourceError
from app.models.tables import DataIssue, OpsRecord, SyncRun, utcnow
from app.services.data_validation import SchemaError, validate_rows

log = logging.getLogger(__name__)


def run_sync(session: Session, source: DataSource) -> SyncRun:
    run = SyncRun(source=source.name)
    session.add(run)
    session.commit()
    session.refresh(run)

    try:
        rows = source.fetch_rows()
        result = validate_rows(rows)
        if not result.records:
            raise SchemaError("No valid rows after validation")
    except (SourceError, SchemaError) as exc:
        run.status = "failed"
        run.error_message = str(exc)
        run.finished_at = utcnow()
        session.add(run)
        session.commit()
        log.warning("sync %s failed: %s", run.id, exc)
        return run
    except Exception:  # unexpected: record it without leaking internals to the UI
        session.rollback()
        run.status = "failed"
        run.error_message = "Unexpected error during sync (see server logs)"
        run.finished_at = utcnow()
        session.add(run)
        session.commit()
        log.exception("sync %s crashed", run.id)
        return run

    for rec in result.records:
        session.add(OpsRecord(sync_run_id=run.id, **rec))
    for issue in result.issues:
        session.add(DataIssue(sync_run_id=run.id, source_row=issue.source_row, site_id=issue.site_id,
                              field=issue.field, severity=issue.severity, message=issue.message))
    run.status = "success"
    run.rows_read = result.rows_read
    run.rows_valid = len(result.records)
    run.rows_rejected = result.rows_rejected
    run.warnings = result.warnings
    run.finished_at = utcnow()
    session.add(run)
    session.commit()
    session.refresh(run)
    log.info("sync %s ok: %s valid, %s rejected", run.id, run.rows_valid, run.rows_rejected)
    return run


def current_run(session: Session) -> SyncRun | None:
    """The latest successful snapshot: what all analytics read from."""
    return session.exec(
        select(SyncRun).where(SyncRun.status == "success").order_by(SyncRun.id.desc())
    ).first()


def latest_attempt(session: Session) -> SyncRun | None:
    return session.exec(select(SyncRun).order_by(SyncRun.id.desc())).first()


def load_records(session: Session, run: SyncRun) -> list[OpsRecord]:
    return list(session.exec(
        select(OpsRecord).where(OpsRecord.sync_run_id == run.id).order_by(OpsRecord.day, OpsRecord.site_id)
    ))

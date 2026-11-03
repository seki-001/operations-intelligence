import json
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.db import get_session
from app.core.security import require_api_key
from app.integrations.sources import SourceError, build_source
from app.models.tables import DataIssue, Report, SyncRun, utcnow
from app.services import analytics
from app.services.ai_reporting import build_facts, build_provider, summarise
from app.services.sync import current_run, latest_attempt, load_records, run_sync

router = APIRouter(prefix="/api", dependencies=[Depends(require_api_key)])


def _run_out(run: SyncRun | None) -> dict | None:
    if run is None:
        return None
    return {
        "id": run.id, "source": run.source, "status": run.status,
        "started_at": _iso(run.started_at), "finished_at": _iso(run.finished_at),
        "rows_read": run.rows_read, "rows_valid": run.rows_valid,
        "rows_rejected": run.rows_rejected, "warnings": run.warnings, "error": run.error_message,
    }


def _iso(dt):
    if dt is None:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()


def _require_data(session: Session) -> SyncRun:
    run = current_run(session)
    if run is None:
        raise HTTPException(409, "No successful sync yet. Run a sync first.")
    return run


@router.post("/sync")
def trigger_sync(session: Session = Depends(get_session)):
    settings = get_settings()
    try:
        source = build_source(settings)
    except SourceError as exc:
        run = SyncRun(source=settings.data_source, status="failed", error_message=str(exc), finished_at=utcnow())
        session.add(run)
        session.commit()
        session.refresh(run)
        return {"attempt": _run_out(run), "current": _run_out(current_run(session))}
    run = run_sync(session, source)
    return {"attempt": _run_out(run), "current": _run_out(current_run(session))}


@router.get("/sync/status")
def sync_status(session: Session = Depends(get_session)):
    """`current` is the snapshot being displayed; `latest_attempt` may be a newer failure."""
    return {"current": _run_out(current_run(session)), "latest_attempt": _run_out(latest_attempt(session))}


@router.get("/overview")
def overview(period_days: int = Query(7, ge=1, le=90), session: Session = Depends(get_session)):
    run = _require_data(session)
    comparison = analytics.compare_periods(load_records(session, run), period_days)
    return {"snapshot": _run_out(run), **comparison}


@router.get("/trends")
def trends(metric: str = "energy_sold_kwh", site_id: str | None = None,
           session: Session = Depends(get_session)):
    run = _require_data(session)
    try:
        series = analytics.daily_trend(load_records(session, run), metric, site_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return {"metric": metric, "metrics_available": analytics.TREND_METRICS, "series": series}


@router.get("/data-quality")
def data_quality(session: Session = Depends(get_session)):
    run = _require_data(session)
    issues = session.exec(
        select(DataIssue).where(DataIssue.sync_run_id == run.id).order_by(DataIssue.severity, DataIssue.source_row)
    ).all()
    return {
        "snapshot": _run_out(run),
        "issues": [{"row": i.source_row, "site_id": i.site_id, "field": i.field,
                    "severity": i.severity, "message": i.message} for i in issues],
    }


class SummaryRequest(BaseModel):
    period_days: int = Field(7, ge=1, le=90)


@router.post("/reports/summary")
def create_summary(body: SummaryRequest, session: Session = Depends(get_session)):
    run = _require_data(session)
    comparison = analytics.compare_periods(load_records(session, run), body.period_days)
    facts = build_facts(comparison)
    summary = summarise(facts, build_provider(get_settings()))
    report = Report(
        sync_run_id=run.id, provider=summary.provider, model=summary.model,
        is_ai_generated=summary.is_ai_generated, period_label=facts["period"] or "",
        content_json=json.dumps({
            "observations": summary.observations, "hypotheses": summary.hypotheses,
            "suggested_checks": summary.suggested_checks, "fallback_reason": summary.fallback_reason,
            "unknown_fact_ids": summary.unknown_fact_ids,
        }),
        facts_json=json.dumps(facts), unverified_numbers_json=json.dumps(summary.unverified_numbers),
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return _report_out(report)


@router.get("/reports/latest")
def latest_report(session: Session = Depends(get_session)):
    report = session.exec(select(Report).order_by(Report.id.desc())).first()
    return _report_out(report) if report else None


class ReviewRequest(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    reviewer: str = Field(min_length=2, max_length=80)


@router.post("/reports/{report_id}/review")
def review_report(report_id: int, body: ReviewRequest, session: Session = Depends(get_session)):
    report = session.get(Report, report_id)
    if report is None:
        raise HTTPException(404, "Report not found")
    if report.review_status != "pending_review":
        raise HTTPException(409, f"Report already {report.review_status}")
    report.review_status = body.decision
    report.reviewed_by = body.reviewer.strip()
    report.reviewed_at = utcnow()
    session.add(report)
    session.commit()
    session.refresh(report)
    return _report_out(report)


def _report_out(r: Report) -> dict:
    return {
        "id": r.id, "created_at": _iso(r.created_at), "sync_run_id": r.sync_run_id,
        "provider": r.provider, "model": r.model, "is_ai_generated": r.is_ai_generated,
        "period": r.period_label, **json.loads(r.content_json),
        "facts": json.loads(r.facts_json)["facts"],
        "unverified_numbers": json.loads(r.unverified_numbers_json),
        "review_status": r.review_status, "reviewed_by": r.reviewed_by, "reviewed_at": _iso(r.reviewed_at),
    }

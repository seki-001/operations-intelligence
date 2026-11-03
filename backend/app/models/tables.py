"""Database tables. Every record is tied to the sync run that produced it, so the
dashboard always reads one consistent, validated snapshot."""

from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SyncRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source: str
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: Optional[datetime] = None
    status: str = "running"  # running | success | failed
    rows_read: int = 0
    rows_valid: int = 0
    rows_rejected: int = 0
    warnings: int = 0
    error_message: Optional[str] = None


class OpsRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sync_run_id: int = Field(foreign_key="syncrun.id", index=True)
    source_row: int
    day: date = Field(index=True)
    site_id: str = Field(index=True)
    site_name: str
    generation_kwh: float
    energy_sold_kwh: float
    active_customers: int
    new_connections: int
    billed_usd: float
    collected_usd: float
    uptime_pct: float
    outage_events: int


class DataIssue(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sync_run_id: int = Field(foreign_key="syncrun.id", index=True)
    source_row: int
    site_id: Optional[str] = None
    field: Optional[str] = None
    severity: str  # error (row rejected) | warning (row kept, flagged)
    message: str


class Report(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sync_run_id: int = Field(foreign_key="syncrun.id")
    created_at: datetime = Field(default_factory=utcnow)
    provider: str
    model: Optional[str] = None
    is_ai_generated: bool
    period_label: str
    content_json: str
    facts_json: str
    unverified_numbers_json: str = "[]"
    review_status: str = "pending_review"  # pending_review | approved | rejected
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

ROOT = Path(__file__).resolve().parents[2]
os.environ.update({
    "ENVIRONMENT": "test",
    "API_KEY": "test-key",
    "DATA_SOURCE": "csv",
    "CSV_PATH": str(ROOT / "data" / "synthetic_daily_ops.csv"),
    "AI_PROVIDER": "template",
})

from app.core import db  # noqa: E402
from app.core.config import get_settings  # noqa: E402

HEADER = ["date", "site_id", "site_name", "generation_kwh", "energy_sold_kwh", "active_customers",
          "new_connections", "billed_usd", "collected_usd", "uptime_pct", "outage_events"]


def row(day="2026-10-01", site="AAA", gen="100", sold="90", cust="50", new="1", billed="30",
        collected="27", uptime="99", outages="0"):
    return [day, site, site.title(), gen, sold, cust, new, billed, collected, uptime, outages]


@pytest.fixture(autouse=True)
def fresh_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    db.set_engine(eng)
    SQLModel.metadata.create_all(eng)
    yield eng
    db.set_engine(None)


@pytest.fixture
def client(engine):
    from app.main import app

    with TestClient(app, headers={"X-API-Key": "test-key"}) as c:
        yield c

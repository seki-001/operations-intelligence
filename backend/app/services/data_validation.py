"""Row-level validation for operational records.

Two severities:
  * error   -> the row is rejected and never reaches analytics
  * warning -> the row is kept but flagged for a human to check

Nothing is silently "fixed". Every rejection or flag is recorded with its sheet row number.
"""

from dataclasses import dataclass, field
from datetime import date, datetime

REQUIRED_COLUMNS = [
    "date", "site_id", "site_name", "generation_kwh", "energy_sold_kwh", "active_customers",
    "new_connections", "billed_usd", "collected_usd", "uptime_pct", "outage_events",
]
REQUIRED_VALUES = ["date", "site_id", "generation_kwh", "energy_sold_kwh", "active_customers",
                   "billed_usd", "collected_usd", "uptime_pct"]
OPTIONAL_COUNTS = ["new_connections", "outage_events"]  # blank -> 0, with a warning
FLOAT_FIELDS = ["generation_kwh", "energy_sold_kwh", "billed_usd", "collected_usd", "uptime_pct"]
INT_FIELDS = ["active_customers", "new_connections", "outage_events"]
DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y")


class SchemaError(Exception):
    """The sheet is missing expected columns; the whole sync must fail."""


@dataclass
class Issue:
    source_row: int
    severity: str
    message: str
    site_id: str | None = None
    field: str | None = None


@dataclass
class ValidationResult:
    records: list[dict] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    rows_read: int = 0

    @property
    def rows_rejected(self) -> int:
        return len({i.source_row for i in self.issues if i.severity == "error"})

    @property
    def warnings(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


def _parse_date(raw: str) -> date:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(raw)


def _parse_number(raw: str) -> float:
    cleaned = raw.replace(",", "").replace("$", "").replace("%", "").strip()
    return float(cleaned)


def validate_rows(rows: list[list[str]], today: date | None = None) -> ValidationResult:
    today = today or date.today()
    result = ValidationResult()
    if not rows:
        raise SchemaError("The source returned no rows (not even a header)")

    header = [h.strip().lower() for h in rows[0]]
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise SchemaError(f"Missing columns: {', '.join(missing)}")
    idx = {name: header.index(name) for name in REQUIRED_COLUMNS}

    seen: set[tuple[str, date]] = set()

    for offset, row in enumerate(rows[1:]):
        source_row = offset + 2  # 1-based, after the header: matches the sheet row number
        if not any(cell.strip() for cell in row):
            continue  # fully blank lines are ignored, not counted
        result.rows_read += 1

        def cell(name: str) -> str:
            i = idx[name]
            return row[i].strip() if i < len(row) else ""

        site_id = cell("site_id") or None
        row_errors: list[Issue] = []
        row_warnings: list[Issue] = []

        def err(msg: str, fld: str | None = None):
            row_errors.append(Issue(source_row, "error", msg, site_id, fld))

        def warn(msg: str, fld: str | None = None):
            row_warnings.append(Issue(source_row, "warning", msg, site_id, fld))

        for name in REQUIRED_VALUES:
            if not cell(name):
                err(f"Missing required value '{name}'", name)

        rec: dict = {"source_row": source_row, "site_id": site_id,
                     "site_name": cell("site_name") or (site_id or "")}

        if cell("date"):
            try:
                rec["day"] = _parse_date(cell("date"))
                if rec["day"] > today:
                    err(f"Date {rec['day'].isoformat()} is in the future", "date")
            except ValueError:
                err(f"Unrecognised date '{cell('date')}' (use YYYY-MM-DD)", "date")

        for name in FLOAT_FIELDS + INT_FIELDS:
            raw = cell(name)
            if not raw:
                if name in OPTIONAL_COUNTS:
                    rec[name] = 0
                    warn(f"'{name}' was blank; treated as 0", name)
                continue
            try:
                value = _parse_number(raw)
            except ValueError:
                err(f"'{name}' is not a number: '{raw}'", name)
                continue
            if value < 0:
                err(f"'{name}' cannot be negative ({raw})", name)
                continue
            if name in INT_FIELDS:
                if value != int(value):
                    err(f"'{name}' must be a whole number ({raw})", name)
                    continue
                value = int(value)
            rec[name] = value

        if "uptime_pct" in rec and rec["uptime_pct"] > 100:
            err(f"uptime_pct must be between 0 and 100 ({rec['uptime_pct']})", "uptime_pct")

        if not row_errors and rec.get("day") and site_id:
            key = (site_id, rec["day"])
            if key in seen:
                err(f"Duplicate entry for {site_id} on {rec['day'].isoformat()}; first entry kept", "date")
            else:
                seen.add(key)

        if not row_errors:
            if rec["energy_sold_kwh"] > rec["generation_kwh"]:
                warn("Energy sold exceeds generation for the day (check meter readings or storage carry-over)",
                     "energy_sold_kwh")
            if rec["billed_usd"] > 0 and rec["collected_usd"] > rec["billed_usd"] * 1.5:
                warn("Collections are over 150% of billing (arrears payment or data entry error?)",
                     "collected_usd")
            if rec["uptime_pct"] == 100 and rec.get("outage_events", 0) > 0:
                warn("100% uptime recorded alongside outage events", "outage_events")
            result.records.append(rec)

        result.issues.extend(row_errors + row_warnings)

    return result

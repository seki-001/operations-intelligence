from datetime import date

import pytest

from app.services.data_validation import SchemaError, validate_rows
from tests.conftest import HEADER, row

TODAY = date(2026, 11, 3)


def errors(result):
    return [i for i in result.issues if i.severity == "error"]


def test_valid_rows_pass_and_are_typed():
    result = validate_rows([HEADER, row(), row(site="BBB")], today=TODAY)
    assert len(result.records) == 2
    rec = result.records[0]
    assert rec["day"] == date(2026, 10, 1)
    assert rec["generation_kwh"] == 100.0
    assert rec["active_customers"] == 50 and isinstance(rec["active_customers"], int)
    assert result.issues == []


def test_missing_column_fails_whole_sync():
    with pytest.raises(SchemaError, match="uptime_pct"):
        validate_rows([[h for h in HEADER if h != "uptime_pct"]], today=TODAY)


def test_empty_source_fails():
    with pytest.raises(SchemaError):
        validate_rows([], today=TODAY)


@pytest.mark.parametrize("kwargs,field", [
    ({"billed": ""}, "billed_usd"),
    ({"gen": "-5"}, "generation_kwh"),
    ({"gen": "abc"}, "generation_kwh"),
    ({"uptime": "104"}, "uptime_pct"),
    ({"day": "31/02/2026"}, "date"),
    ({"day": "2026-12-25"}, "date"),          # future date
    ({"cust": "10.5"}, "active_customers"),   # customers must be whole
])
def test_bad_values_reject_the_row(kwargs, field):
    result = validate_rows([HEADER, row(**kwargs)], today=TODAY)
    assert result.records == []
    assert result.rows_rejected == 1
    assert errors(result)[0].field == field
    assert errors(result)[0].source_row == 2  # matches the spreadsheet row number


def test_duplicate_site_day_keeps_first_only():
    result = validate_rows([HEADER, row(gen="100"), row(gen="999")], today=TODAY)
    assert len(result.records) == 1
    assert result.records[0]["generation_kwh"] == 100.0
    assert "Duplicate" in errors(result)[0].message


def test_warnings_keep_the_row():
    result = validate_rows([HEADER, row(sold="120"), row(site="BBB", outages="")], today=TODAY)
    assert len(result.records) == 2
    assert result.warnings == 2
    assert result.records[1]["outage_events"] == 0


def test_formatted_numbers_and_alt_date_accepted():
    result = validate_rows([HEADER, row(day="01/10/2026", gen="1,200.5", billed="$30")], today=TODAY)
    assert result.records[0]["day"] == date(2026, 10, 1)
    assert result.records[0]["generation_kwh"] == 1200.5
    assert result.records[0]["billed_usd"] == 30.0


def test_blank_lines_ignored():
    result = validate_rows([HEADER, ["", "", ""], row()], today=TODAY)
    assert result.rows_read == 1 and len(result.records) == 1

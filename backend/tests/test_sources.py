import httpx
import pytest

from app.integrations.sources import SharedLinkSheetSource, SourceError

CSV = "date,site_id\n2026-10-01,AAA\n"


def source(status=200, body=CSV, content_type="text/csv"):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/spreadsheets/d/SHEET/export"
        assert request.url.params["format"] == "csv" and request.url.params["gid"] == "7"
        return httpx.Response(status, text=body, headers={"content-type": content_type})
    return SharedLinkSheetSource("SHEET", "7", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_reads_csv_export():
    assert source().fetch_rows() == [["date", "site_id"], ["2026-10-01", "AAA"]]


def test_private_sheet_gives_clear_message():
    # Google answers a non-public sheet with a sign-in HTML page, not an error code.
    with pytest.raises(SourceError, match="Anyone with the link"):
        source(body="<html>Sign in</html>", content_type="text/html; charset=utf-8").fetch_rows()


def test_missing_sheet():
    with pytest.raises(SourceError, match="not found"):
        source(status=404).fetch_rows()

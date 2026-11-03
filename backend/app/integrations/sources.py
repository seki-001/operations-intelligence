"""Data sources. Each returns raw rows (header first) as strings, exactly as a
spreadsheet would. Validation happens later, in one place, for every source."""

import csv
import json
from pathlib import Path
from typing import Protocol

from app.core.config import Settings

SHEETS_READONLY_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"


class SourceError(Exception):
    """Raised when a source cannot be read. The message is safe to show to users."""


class DataSource(Protocol):
    name: str

    def fetch_rows(self) -> list[list[str]]: ...


class CsvSource:
    name = "csv"

    def __init__(self, path: str):
        self.path = Path(path)

    def fetch_rows(self) -> list[list[str]]:
        if not self.path.exists():
            raise SourceError(f"CSV file not found: {self.path.name}")
        with self.path.open(newline="", encoding="utf-8") as f:
            return [row for row in csv.reader(f)]


class GoogleSheetsSource:
    """Read-only Google Sheets client using a service account.

    Uses the spreadsheets.readonly scope, so even a leaked credential cannot
    modify the sheet. Share the sheet with the service account as Viewer only.
    """

    name = "google_sheets"

    def __init__(self, sheet_id: str, sheet_range: str, credentials_info: dict, timeout: float = 20.0):
        self.sheet_id = sheet_id
        self.sheet_range = sheet_range
        self.credentials_info = credentials_info
        self.timeout = timeout

    def fetch_rows(self) -> list[list[str]]:
        # Imported lazily so the CSV path and tests do not need Google libraries configured.
        from google.auth.exceptions import GoogleAuthError
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account
        import requests

        try:
            creds = service_account.Credentials.from_service_account_info(
                self.credentials_info, scopes=[SHEETS_READONLY_SCOPE]
            )
            session = AuthorizedSession(creds)
            url = f"https://sheets.googleapis.com/v4/spreadsheets/{self.sheet_id}/values/{self.sheet_range}"
            resp = session.get(url, params={"valueRenderOption": "UNFORMATTED_VALUE",
                                            "dateTimeRenderOption": "FORMATTED_STRING"},
                               timeout=self.timeout)
        except (GoogleAuthError, ValueError) as exc:
            raise SourceError(f"Google credentials rejected: {type(exc).__name__}") from exc
        except requests.RequestException as exc:
            raise SourceError(f"Could not reach Google Sheets: {type(exc).__name__}") from exc

        if resp.status_code == 403:
            raise SourceError("Access denied. Share the sheet with the service account email (Viewer).")
        if resp.status_code == 404:
            raise SourceError("Sheet or range not found. Check GOOGLE_SHEET_ID and GOOGLE_SHEET_RANGE.")
        if resp.status_code != 200:
            raise SourceError(f"Google Sheets returned HTTP {resp.status_code}")

        values = resp.json().get("values", [])
        return [[str(cell) for cell in row] for row in values]


class SharedLinkSheetSource:
    """Reads a Google Sheet shared as "Anyone with the link can view", via its CSV export.

    No Google Cloud project or key is needed, but anyone with the link can read the sheet,
    so this mode is only suitable for non-sensitive data (e.g. this synthetic demo).
    Real deployments should use GoogleSheetsSource with a service account.
    """

    name = "google_sheets_link"

    def __init__(self, sheet_id: str, gid: str = "0", timeout: float = 20.0, client=None):
        self.url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export"
        self.params = {"format": "csv", "gid": gid}
        self.timeout = timeout
        self.client = client

    def fetch_rows(self) -> list[list[str]]:
        import httpx

        client = self.client or httpx.Client(timeout=self.timeout, follow_redirects=True)
        try:
            resp = client.get(self.url, params=self.params)
        except httpx.HTTPError as exc:
            raise SourceError(f"Could not reach Google Sheets: {type(exc).__name__}") from exc
        finally:
            if self.client is None:
                client.close()

        content_type = resp.headers.get("content-type", "")
        if resp.status_code in (401, 403) or "text/html" in content_type:
            raise SourceError("Sheet is not readable. Set sharing to 'Anyone with the link: Viewer'.")
        if resp.status_code == 404:
            raise SourceError("Sheet not found. Check GOOGLE_SHEET_ID and GOOGLE_SHEET_GID.")
        if resp.status_code != 200:
            raise SourceError(f"Google Sheets returned HTTP {resp.status_code}")
        return [row for row in csv.reader(resp.text.splitlines())]


def build_source(settings: Settings) -> DataSource:
    if settings.data_source == "csv":
        return CsvSource(settings.csv_path)

    if settings.data_source == "google_sheets_link":
        if not settings.google_sheet_id:
            raise SourceError("GOOGLE_SHEET_ID is not set")
        return SharedLinkSheetSource(settings.google_sheet_id, settings.google_sheet_gid)

    if not settings.google_sheet_id:
        raise SourceError("GOOGLE_SHEET_ID is not set")
    if settings.google_service_account_json:
        try:
            info = json.loads(settings.google_service_account_json)
        except json.JSONDecodeError as exc:
            raise SourceError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON") from exc
    elif settings.google_service_account_file:
        path = Path(settings.google_service_account_file)
        if not path.exists():
            raise SourceError("Service account file not found")
        info = json.loads(path.read_text())
    else:
        raise SourceError("No Google service account credentials configured")
    return GoogleSheetsSource(settings.google_sheet_id, settings.google_sheet_range, info)

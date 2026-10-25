"""Google Sheets transport. Only the fixed Google API host receives credentials."""
import secrets
from urllib.parse import quote

from ..core.errors import ApiError

BASE = "https://sheets.googleapis.com/v4/spreadsheets/"
OWNER_TAB = "_TimeLog_owner"


class GoogleSheet:
    def __init__(self, spreadsheet_id, credentials_file):
        # Optional deployment dependency; unit tests inject a fake gateway.
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
        credentials = service_account.Credentials.from_service_account_file(
            credentials_file, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        self.session = AuthorizedSession(credentials)
        self.base = BASE + spreadsheet_id

    def request(self, method, suffix="", **kwargs):
        response = self.session.request(method, self.base + suffix, timeout=45,
                                        allow_redirects=False, **kwargs)
        if not 200 <= response.status_code < 300:
            # Never log credentials, the private sheet URL, or Google's response body.
            raise ApiError(f"Google Sheets request failed ({response.status_code})")
        return response.json()

    def values(self, range_):
        return self.request("GET", "/values/" + quote(range_, safe=""),
                            params={"valueRenderOption": "UNFORMATTED_VALUE"}).get("values", [])

    def ensure_owner(self, owner, headers):
        meta = self.request("GET", params={"fields": "sheets.properties"})
        sheets = {s["properties"]["title"]: s["properties"] for s in meta["sheets"]}
        if OWNER_TAB in sheets:
            marker = self.values(f"'{OWNER_TAB}'!A1")
            if marker != [[owner]] or "TimeLog" not in sheets:
                raise ApiError("این شیت متعلق به این حساب نیست؛ هیچ داده‌ای نوشته نشد")
            return False
        if "TimeLog" in sheets:
            raise ApiError("شیت TimeLog بدون نشان مالکیت موجود است؛ بازنویسی نشد")
        used = {s["sheetId"] for s in sheets.values()}
        ids = []
        while len(ids) < 2:
            value = secrets.randbelow(2**30)
            if value not in used and value not in ids:
                ids.append(value)
        requests = [
            {"addSheet": {"properties": {"sheetId": ids[0], "title": OWNER_TAB, "hidden": True}}},
            {"addSheet": {"properties": {"sheetId": ids[1], "title": "TimeLog", "rightToLeft": True,
                                         "gridProperties": {"frozenRowCount": 1, "columnCount": 15}}}},
            {"updateCells": {"start": {"sheetId": ids[0], "rowIndex": 0, "columnIndex": 0},
                             "rows": [{"values": [{"userEnteredValue": {"stringValue": owner}}]}],
                             "fields": "userEnteredValue"}},
            {"updateCells": {"start": {"sheetId": ids[1], "rowIndex": 0, "columnIndex": 0},
                             "rows": [{"values": [{"userEnteredValue": {"stringValue": h}} for h in headers]}],
                             "fields": "userEnteredValue"}},
        ]
        # Claim + headers are one atomic request; simultaneous claims cannot mix owners.
        self.request("POST", ":batchUpdate", json={"requests": requests})
        return True

    def read_rows(self):
        return self.values("'TimeLog'!A:O")

    def write(self, updates, last_row):
        meta = self.request("GET", params={"fields": "sheets.properties"})
        props = next(s["properties"] for s in meta["sheets"] if s["properties"]["title"] == "TimeLog")
        count = props["gridProperties"]["rowCount"]
        if last_row > count:
            self.request("POST", ":batchUpdate", json={"requests": [{"appendDimension": {
                "sheetId": props["sheetId"], "dimension": "ROWS", "length": last_row - count}}]})
        for offset in range(0, len(updates), 200):
            self.request("POST", "/values:batchUpdate", json={"valueInputOption": "RAW",
                                                            "data": updates[offset:offset + 200]})

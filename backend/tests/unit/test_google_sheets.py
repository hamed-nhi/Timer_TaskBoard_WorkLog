"""Check transport payloads without credentials or external writes."""
from app.services.google_sheets import GoogleSheet
from app.services.personal_backup import HEADERS
from app.core.errors import ApiError
import pytest


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        body = next(self.responses)
        class Response:
            status_code = 200
            def json(self):
                return body
        return Response()


def gateway(responses):
    sheet = object.__new__(GoogleSheet)
    sheet.base = "https://sheets.googleapis.com/v4/spreadsheets/test-id"
    sheet.session = Session(responses)
    return sheet


def test_new_owner_and_headers_are_claimed_atomically():
    sheet = gateway([{"sheets": [{"properties": {"title": "Sheet1", "sheetId": 0}}]}, {}])
    assert sheet.ensure_owner("instance:alice", HEADERS)
    requests = sheet.session.calls[1][2]["json"]["requests"]
    assert len(requests) == 4
    assert requests[2]["updateCells"]["rows"][0]["values"][0]["userEnteredValue"]["stringValue"] == "instance:alice"
    assert requests[1]["addSheet"]["properties"]["title"] == "TimeLog"
    assert all(c[2]["allow_redirects"] is False and c[2]["timeout"] == 45 for c in sheet.session.calls)


def test_existing_foreign_workbook_is_read_only():
    sheet = gateway([{"sheets": [{"properties": {"title": "_TimeLog_owner"}},
                                  {"properties": {"title": "TimeLog"}}]}, {"values": [["bob"]]}])
    with pytest.raises(ApiError):
        sheet.ensure_owner("alice", HEADERS)
    assert all(c[0] == "GET" for c in sheet.session.calls)


def test_sheet_values_are_raw_and_grid_grows_before_writing():
    sheet = gateway([{"sheets": [{"properties": {"title": "TimeLog", "sheetId": 12,
                                                 "gridProperties": {"rowCount": 2}}}]}, {}, {}])
    updates = [{"range": "'TimeLog'!A3:O3", "values": [["=not-a-formula"]]}]
    sheet.write(updates, 3)
    assert sheet.session.calls[1][2]["json"]["requests"][0]["appendDimension"]["length"] == 1
    body = sheet.session.calls[2][2]["json"]
    assert body == {"valueInputOption": "RAW", "data": updates}

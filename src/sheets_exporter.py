"""
Google Sheets exporter.
Writes scraped leads to a Google Spreadsheet using a service-account credential.
"""

import json
import logging
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class SheetsExporter:
    """Exports a list of lead dicts to a Google Spreadsheet tab."""

    def __init__(
        self,
        spreadsheet_id: str,
        tab_name: str = "Leads",
        service_account_json: str = "",
        service_account_file: Optional[str] = None,
    ):
        self.spreadsheet_id = spreadsheet_id
        self.tab_name = tab_name
        self._creds = self._build_creds(
            service_account_json, service_account_file)

    # ------------------------------------------------------------------
    # Credential helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_creds(
        json_str: str, json_file: Optional[str]
    ) -> Credentials:
        if json_str:
            info = json.loads(json_str)
        elif json_file:
            with open(json_file, "r", encoding="utf-8") as fh:
                info = json.load(fh)
        else:
            raise ValueError(
                "Either service_account_json (string) or service_account_file (path) must be provided."
            )
        return Credentials.from_service_account_info(info, scopes=SCOPES)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export(self, leads: list[dict], columns: list[str]) -> None:
        """Write *leads* to the spreadsheet.  Clears existing data first."""
        if not leads:
            logger.warning("No leads to export.")
            return

        client = gspread.authorize(self._creds)
        spreadsheet = client.open_by_key(self.spreadsheet_id)

        # Get or create the target worksheet
        try:
            worksheet = spreadsheet.worksheet(self.tab_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title=self.tab_name, rows=len(leads) + 10, cols=len(columns) + 2
            )

        # Build the 2-D array: header row + data rows
        header = [col.replace("_", " ").title() for col in columns]
        rows = [header]
        for lead in leads:
            row = [self._cell(lead.get(col)) for col in columns]
            rows.append(row)

        # Clear and update in one call
        worksheet.clear()
        worksheet.update(rows, value_input_option="USER_ENTERED")

        # Auto-resize columns (best-effort)
        try:
            worksheet.columns_auto_resize(0, len(columns) - 1)
        except Exception:
            pass

        # Add a simple header format
        try:
            worksheet.format(
                f"A1:{chr(65 + len(columns) - 1)}1",
                {
                    "backgroundColor": {"red": 0.12, "green": 0.47, "blue": 0.71},
                    "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                    "horizontalAlignment": "CENTER",
                },
            )
        except Exception:
            pass

        logger.info(
            "Exported %d rows to spreadsheet %s / tab %s",
            len(leads),
            self.spreadsheet_id,
            self.tab_name,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cell(value) -> str:
        """Convert a Python value to a spreadsheet-safe string."""
        if value is None:
            return ""
        if isinstance(value, bool):
            return "Yes" if value else "No"
        return str(value)

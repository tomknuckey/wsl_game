"""Transfer ledger backends for local CSV and hosted Google Sheets storage."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from utils.transfer_utils import (
    TRANSFER_FIELDS,
    TransferLedgerProtocol,
    validate_transfer_records,
)


class TransferStorageError(RuntimeError):
    """Raised when a configured transfer storage backend is unavailable."""


class GoogleSheetsTransferLedger:
    """Append-only transfer ledger backed by a single Google Sheets worksheet."""

    def __init__(self, worksheet: Any):
        self._worksheet = worksheet

    @classmethod
    def from_secrets(cls, secrets: Mapping[str, Any]) -> "GoogleSheetsTransferLedger":
        sheets_config = secrets.get("google_sheets")
        service_account = secrets.get("google_service_account")
        if not isinstance(sheets_config, Mapping) or not isinstance(
            service_account, Mapping
        ):
            raise TransferStorageError(
                "Google Sheets transfer storage is selected, but "
                "[google_sheets] or [google_service_account] is missing from "
                "Streamlit secrets."
            )

        spreadsheet_id = str(sheets_config.get("spreadsheet_id", "")).strip()
        worksheet_name = str(sheets_config.get("worksheet", "")).strip()
        if not spreadsheet_id or not worksheet_name:
            raise TransferStorageError(
                "[google_sheets] must include spreadsheet_id and worksheet."
            )

        try:
            import gspread

            client = gspread.service_account_from_dict(dict(service_account))
            worksheet = client.open_by_key(spreadsheet_id).worksheet(worksheet_name)
        except ImportError as error:
            raise TransferStorageError(
                "Google Sheets support is not installed. Install the project "
                "requirements and redeploy."
            ) from error
        except Exception as error:
            raise TransferStorageError(
                "Could not connect to the configured Google Sheet. Check the "
                "spreadsheet ID, worksheet name, service-account credentials, "
                "and sharing permissions."
            ) from error
        return cls(worksheet)

    def _read_rows(self) -> list[list[str]]:
        try:
            rows = self._worksheet.get_all_values()
            if not rows:
                self._worksheet.update(
                    [list(TRANSFER_FIELDS)],
                    range_name=f"A1:{_column_name(len(TRANSFER_FIELDS))}1",
                    value_input_option="RAW",
                )
                rows = self._worksheet.get_all_values()
        except Exception as error:
            raise TransferStorageError(
                "Could not read the Google Sheets transfer ledger. Check that "
                "the service account has access and the Sheets API is enabled."
            ) from error

        if not rows or tuple(rows[0]) != TRANSFER_FIELDS:
            raise TransferStorageError(
                "The Google Sheets transfer worksheet has an invalid header. "
                "Its first row must match the transfer columns documented in "
                "the README."
            )
        return rows

    def load_transfer_records(self) -> list[dict[str, str]]:
        rows = self._read_rows()
        records = [
            {
                field: str(row[index]) if index < len(row) else ""
                for index, field in enumerate(TRANSFER_FIELDS)
            }
            for row in rows[1:]
            if any(str(value).strip() for value in row)
        ]
        return validate_transfer_records(records)

    def append_transfer_record(self, record: Mapping[str, str]) -> None:
        values = [str(record.get(field, "")) for field in TRANSFER_FIELDS]
        try:
            self._worksheet.append_row(values, value_input_option="RAW")
            persisted_records = self.load_transfer_records()
        except TransferStorageError:
            raise
        except Exception as error:
            raise TransferStorageError(
                "Could not save the transfer to Google Sheets. The transfer "
                "was not confirmed; check the sheet before retrying."
            ) from error

        persisted = next(
            (
                saved
                for saved in persisted_records
                if saved["transfer_id"] == record["transfer_id"]
            ),
            None,
        )
        if persisted is None or any(
            persisted.get(field, "") != str(record.get(field, ""))
            for field in TRANSFER_FIELDS
        ):
            raise TransferStorageError(
                "Google Sheets did not confirm the saved transfer. Check the "
                "sheet before retrying."
            )


def get_transfer_ledger(
    data_source: str,
    secrets: Mapping[str, Any],
    local_csv_path: str | Path,
) -> str | Path | TransferLedgerProtocol:
    """Select a source-specific backend; local development defaults to CSV."""
    try:
        backend_setting = secrets.get(f"{data_source}_transfer_storage", "csv")
    except FileNotFoundError:
        backend_setting = "csv"
    backend = str(backend_setting).strip()
    if backend == "csv":
        return Path(local_csv_path)
    if backend == "google_sheets":
        return GoogleSheetsTransferLedger.from_secrets(secrets)
    raise TransferStorageError(
        f"Unsupported transfer storage backend '{backend}' for '{data_source}'. "
        "Use 'csv' or 'google_sheets'."
    )


def _column_name(column_number: int) -> str:
    """Convert a one-based column number to a spreadsheet column label."""
    label = ""
    while column_number:
        column_number, remainder = divmod(column_number - 1, 26)
        label = chr(65 + remainder) + label
    return label

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from utils.transfer_storage import (
    GoogleSheetsTransferLedger,
    TransferStorageError,
    get_transfer_ledger,
)
from utils.transfer_utils import (
    TRANSFER_FIELDS,
    TransferRule,
    get_active_team_transfer,
    load_transfer_records,
    record_correction,
    record_transfer,
)


class FakeWorksheet:
    def __init__(self, rows=None, *, fail_append=False, discard_append=False):
        self.rows = rows or []
        self.fail_append = fail_append
        self.discard_append = discard_append

    def get_all_values(self):
        return [list(row) for row in self.rows]

    def update(self, values, range_name, value_input_option):
        self.rows.extend(values)

    def append_row(self, values, value_input_option):
        if self.fail_append:
            raise OSError("Sheets unavailable")
        if not self.discard_append:
            self.rows.append(list(values))


class MissingSecrets:
    def get(self, key, default=None):
        raise FileNotFoundError("No secrets file")


def future_rule():
    return TransferRule(
        season_id="2026-27",
        gameweek=11,
        start_utc="2020-01-01T00:00:00Z",
        deadline_utc="2099-01-01T00:00:00Z",
        max_transfers_per_team=1,
    )


class GoogleSheetsTransferLedgerTests(unittest.TestCase):
    @patch("gspread.service_account_from_dict")
    def test_from_secrets_connects_to_configured_sheet(self, service_account):
        worksheet = FakeWorksheet([list(TRANSFER_FIELDS)])
        spreadsheet = Mock()
        spreadsheet.worksheet.return_value = worksheet
        client = Mock()
        client.open_by_key.return_value = spreadsheet
        service_account.return_value = client
        secrets = {
            "google_sheets": {
                "spreadsheet_id": "sheet-id",
                "worksheet": "Transfers",
            },
            "google_service_account": {"client_email": "service@example.com"},
        }

        ledger = GoogleSheetsTransferLedger.from_secrets(secrets)

        service_account.assert_called_once_with({"client_email": "service@example.com"})
        client.open_by_key.assert_called_once_with("sheet-id")
        spreadsheet.worksheet.assert_called_once_with("Transfers")
        self.assertEqual(load_transfer_records(ledger), [])

    def test_empty_worksheet_is_initialized_and_records_can_be_loaded(self):
        worksheet = FakeWorksheet()
        ledger = GoogleSheetsTransferLedger(worksheet)

        self.assertEqual(load_transfer_records(ledger), [])
        self.assertEqual(tuple(worksheet.rows[0]), TRANSFER_FIELDS)

    def test_transfer_and_correction_are_appended_and_audited(self):
        worksheet = FakeWorksheet([list(TRANSFER_FIELDS)])
        ledger = GoogleSheetsTransferLedger(worksheet)
        rule = future_rule()
        original = record_transfer(
            ledger,
            team_name="Chelsea Dagger",
            current_player_ids=["A", "B"],
            player_out_id="A",
            player_out_name="Player A",
            player_in_id="C",
            player_in_name="Player C",
            player_in_club="Club C",
            effective_gameweek=11,
            rule=rule,
        )
        correction = record_correction(
            ledger,
            team_name="Chelsea Dagger",
            current_player_ids=["A", "B"],
            player_out_id="A",
            player_out_name="Player A",
            player_in_id="D",
            player_in_name="Player D",
            player_in_club="Club D",
            correction_of_transfer_id=original["transfer_id"],
            correction_reason="Update selection",
            effective_gameweek=11,
            rule=rule,
        )

        records = load_transfer_records(ledger)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[1], correction)
        self.assertEqual(
            get_active_team_transfer(records, "Chelsea Dagger")["player_in_id"],
            "D",
        )

    def test_write_failure_is_raised_instead_of_reported_as_success(self):
        worksheet = FakeWorksheet(
            [list(TRANSFER_FIELDS)],
            fail_append=True,
        )
        ledger = GoogleSheetsTransferLedger(worksheet)

        with self.assertRaisesRegex(TransferStorageError, "Could not save"):
            record_transfer(
                ledger,
                team_name="Chelsea Dagger",
                current_player_ids=["A", "B"],
                player_out_id="A",
                player_out_name="Player A",
                player_in_id="C",
                player_in_name="Player C",
                player_in_club="Club C",
                effective_gameweek=11,
                rule=future_rule(),
            )

    def test_unconfirmed_write_is_reported_as_an_error(self):
        worksheet = FakeWorksheet(
            [list(TRANSFER_FIELDS)],
            discard_append=True,
        )
        ledger = GoogleSheetsTransferLedger(worksheet)

        with self.assertRaisesRegex(TransferStorageError, "did not confirm"):
            record_transfer(
                ledger,
                team_name="Chelsea Dagger",
                current_player_ids=["A", "B"],
                player_out_id="A",
                player_out_name="Player A",
                player_in_id="C",
                player_in_name="Player C",
                player_in_club="Club C",
                effective_gameweek=11,
                rule=future_rule(),
            )

    def test_bad_sheet_header_is_rejected(self):
        ledger = GoogleSheetsTransferLedger(FakeWorksheet([["wrong", "header"]]))

        with self.assertRaisesRegex(TransferStorageError, "invalid header"):
            load_transfer_records(ledger)

    def test_backend_selection_is_explicit_and_csv_remains_default(self):
        csv_path = Path("data/input/actual/team_transfers.csv")
        self.assertEqual(
            get_transfer_ledger("actual", {}, csv_path),
            csv_path,
        )
        self.assertEqual(
            get_transfer_ledger("actual", MissingSecrets(), csv_path),
            csv_path,
        )
        with self.assertRaisesRegex(TransferStorageError, "Unsupported"):
            get_transfer_ledger(
                "actual",
                {"actual_transfer_storage": "unknown"},
                csv_path,
            )

    def test_google_sheet_secrets_are_required_without_csv_fallback(self):
        with self.assertRaisesRegex(TransferStorageError, "is missing"):
            get_transfer_ledger(
                "actual",
                {"actual_transfer_storage": "google_sheets"},
                "data/input/actual/team_transfers.csv",
            )


if __name__ == "__main__":
    unittest.main()

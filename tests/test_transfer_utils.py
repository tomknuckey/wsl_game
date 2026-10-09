import tempfile
import unittest
from pathlib import Path

from utils.transfer_utils import (
    TransferRule,
    get_team_transfer,
    load_transfer_records,
    record_correction,
    record_transfer,
)


class TransferLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.ledger_path = Path(self.temp_directory.name) / "team_transfers.csv"

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def save_sample_transfer(self) -> dict[str, str]:
        return record_transfer(
            self.ledger_path,
            team_name="Chelsea Dagger",
            current_player_ids=["player-1", "player-2"],
            player_out_id="player-1",
            player_out_name="Player One",
            player_in_id="player-3",
            player_in_name="Player Three",
            player_in_club="Club Three",
            effective_gameweek=10,
        )

    def test_transfer_is_saved_to_csv(self) -> None:
        saved_transfer = self.save_sample_transfer()

        records = load_transfer_records(self.ledger_path)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["player_out_id"], "player-1")
        self.assertEqual(records[0]["player_in_id"], "player-3")
        self.assertEqual(records[0]["effective_gameweek"], "10")
        self.assertEqual(
            get_team_transfer(records, "  chelsea   dagger "),
            saved_transfer,
        )

    def test_legacy_transfer_without_effective_gameweek_is_supported(self) -> None:
        with self.ledger_path.open("w", newline="", encoding="utf-8-sig") as ledger_file:
            ledger_file.write(
                "team_name,player_out_id,player_out_name,player_in_id,"
                "player_in_name,player_in_club,submitted_at_utc\n"
                "Chelsea Dagger,player-1,Player One,player-3,Player Three,"
                "Club Three,2026-10-05T15:08:05+00:00\n"
            )

        records = load_transfer_records(self.ledger_path)

        self.assertEqual(records[0]["effective_gameweek"], "10")

    def test_team_cannot_save_a_second_transfer(self) -> None:
        self.save_sample_transfer()

        with self.assertRaisesRegex(ValueError, "used all 1 transfers"):
            record_transfer(
                self.ledger_path,
                team_name="Chelsea Dagger",
                current_player_ids=["player-2", "player-3"],
                player_out_id="player-2",
                player_out_name="Player Two",
                player_in_id="player-4",
                player_in_name="Player Four",
                player_in_club="Club Four",
                max_transfers=1,
            )

        self.assertEqual(len(load_transfer_records(self.ledger_path)), 1)

    def test_team_can_make_multiple_transfers_under_a_rule(self) -> None:
        rule = TransferRule(
            season_id="2026-27",
            gameweek=10,
            deadline_utc="2026-09-01T20:00:00Z",
            max_transfers_per_team=2,
        )
        first = record_transfer(
            self.ledger_path,
            team_name="Chelsea Dagger",
            current_player_ids=["player-1", "player-2"],
            player_out_id="player-1",
            player_out_name="Player One",
            player_in_id="player-3",
            player_in_name="Player Three",
            player_in_club="Club Three",
            effective_gameweek=10,
            rule=rule,
        )
        second = record_transfer(
            self.ledger_path,
            team_name="Chelsea Dagger",
            current_player_ids=["player-2", "player-3"],
            player_out_id="player-2",
            player_out_name="Player Two",
            player_in_id="player-4",
            player_in_name="Player Four",
            player_in_club="Club Four",
            effective_gameweek=10,
            rule=rule,
        )

        records = load_transfer_records(self.ledger_path)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["season_id"], "2026-27")
        self.assertEqual(records[1]["season_id"], "2026-27")
        self.assertEqual(first["transfer_id"] != second["transfer_id"], True)

    def test_incoming_player_cannot_already_be_on_roster(self) -> None:
        with self.assertRaisesRegex(ValueError, "already on this team's roster"):
            record_transfer(
                self.ledger_path,
                team_name="Chelsea Dagger",
                current_player_ids=["player-1", "player-2"],
                player_out_id="player-1",
                player_out_name="Player One",
                player_in_id="player-2",
                player_in_name="Player Two",
                player_in_club="Club Two",
            )

    def test_duplicate_current_roster_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate players"):
            record_transfer(
                self.ledger_path,
                team_name="Chelsea Dagger",
                current_player_ids=["player-1", "player-1"],
                player_out_id="player-1",
                player_out_name="Player One",
                player_in_id="player-3",
                player_in_name="Player Three",
                player_in_club="Club Three",
            )

    def test_correction_is_audited_and_does_not_count_as_a_new_transfer(self) -> None:
        original = self.save_sample_transfer()

        correction = record_correction(
            self.ledger_path,
            team_name="Chelsea Dagger",
            current_player_ids=["player-1", "player-2"],
            player_out_id="player-1",
            player_out_name="Player One",
            player_in_id="player-4",
            player_in_name="Player Four",
            player_in_club="Club Four",
            correction_of_transfer_id=original["submitted_at_utc"],
            correction_reason="The incoming player was unavailable",
        )

        records = load_transfer_records(self.ledger_path)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[1]["action_type"], "correction")
        self.assertEqual(records[1]["correction_of_transfer_id"], original["transfer_id"])
        self.assertEqual(correction["player_in_id"], "player-4")
        self.assertEqual(len([record for record in records if record["action_type"] == "transfer"]), 1)


if __name__ == "__main__":
    unittest.main()
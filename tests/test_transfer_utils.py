import tempfile
import unittest
from pathlib import Path

from utils.transfer_utils import get_team_transfer, load_transfer_records, record_transfer


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
        )

    def test_transfer_is_saved_to_csv(self) -> None:
        saved_transfer = self.save_sample_transfer()

        records = load_transfer_records(self.ledger_path)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["player_out_id"], "player-1")
        self.assertEqual(records[0]["player_in_id"], "player-3")
        self.assertEqual(
            get_team_transfer(records, "  chelsea   dagger "),
            saved_transfer,
        )

    def test_team_cannot_save_a_second_transfer(self) -> None:
        self.save_sample_transfer()

        with self.assertRaisesRegex(ValueError, "already used its one transfer"):
            record_transfer(
                self.ledger_path,
                team_name="Chelsea Dagger",
                current_player_ids=["player-2", "player-3"],
                player_out_id="player-2",
                player_out_name="Player Two",
                player_in_id="player-4",
                player_in_name="Player Four",
                player_in_club="Club Four",
            )

        self.assertEqual(len(load_transfer_records(self.ledger_path)), 1)

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


if __name__ == "__main__":
    unittest.main()
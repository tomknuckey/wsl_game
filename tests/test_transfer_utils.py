import csv
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from utils.transfer_utils import (
    TransferRule,
    filter_transfer_records_for_rules,
    format_utc_datetime,
    get_active_team_transfer,
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

    def test_pre_start_legacy_transfers_are_excluded(self) -> None:
        with self.ledger_path.open("w", newline="", encoding="utf-8") as ledger_file:
            ledger_file.write(
                "team_name,player_out_id,player_out_name,player_in_id,"
                "player_in_name,player_in_club,submitted_at_utc\n"
                "Team One,A,Player A,F,Player F,Club F,2026-10-05T15:08:05+00:00\n"
                "Team Two,B,Player B,G,Player G,Club G,2026-10-05T21:18:04+00:00\n"
            )

        records = load_transfer_records(self.ledger_path)
        rule = TransferRule(
            season_id="2026-27",
            gameweek=10,
            start_utc="2026-10-10T00:00:00Z",
            deadline_utc="2026-10-12T20:00:00Z",
            max_transfers_per_team=1,
        )

        eligible_records = filter_transfer_records_for_rules(records, [rule])

        self.assertEqual(eligible_records, [])

    def test_after_deadline_legacy_transfers_are_excluded(self) -> None:
        with self.ledger_path.open("w", newline="", encoding="utf-8") as ledger_file:
            ledger_file.write(
                "team_name,player_out_id,player_out_name,player_in_id,"
                "player_in_name,player_in_club,submitted_at_utc\n"
                "Team One,A,Player A,F,Player F,Club F,2026-11-12T20:00:00+00:00\n"
            )

        records = load_transfer_records(self.ledger_path)
        rule = TransferRule(
            season_id="2026-27",
            gameweek=10,
            start_utc="2026-10-10T00:00:00Z",
            deadline_utc="2026-11-12T20:00:00Z",
            max_transfers_per_team=1,
        )

        eligible_records = filter_transfer_records_for_rules(records, [rule])

        self.assertEqual(eligible_records, [])

    def test_eligible_legacy_transfers_with_blank_ids_are_preserved(self) -> None:
        with self.ledger_path.open("w", newline="", encoding="utf-8") as ledger_file:
            ledger_file.write(
                "team_name,player_out_id,player_out_name,player_in_id,"
                "player_in_name,player_in_club,submitted_at_utc\n"
                "Team One,A,Player A,F,Player F,Club F,2026-10-10T01:00:00+00:00\n"
                "Team Two,B,Player B,G,Player G,Club G,2026-10-10T02:00:00+00:00\n"
            )

        records = load_transfer_records(self.ledger_path)
        rule = TransferRule(
            season_id="2026-27",
            gameweek=10,
            start_utc="2026-10-10T00:00:00Z",
            deadline_utc="2026-10-12T20:00:00Z",
            max_transfers_per_team=1,
        )

        eligible_records = filter_transfer_records_for_rules(records, [rule])

        self.assertEqual(len(eligible_records), 2)

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
            deadline_utc="2099-09-01T20:00:00Z",
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

    def test_transfer_rule_opens_at_start_and_closes_at_deadline(self) -> None:
        rule = TransferRule(
            season_id="2026-27",
            gameweek=10,
            start_utc="2026-10-10T00:00:00Z",
            deadline_utc="2026-10-12T20:00:00Z",
            max_transfers_per_team=1,
        )

        self.assertFalse(rule.is_open(datetime(2026, 10, 9, 23, 59, tzinfo=timezone.utc)))
        self.assertTrue(rule.is_open(datetime(2026, 10, 10, 0, 0, tzinfo=timezone.utc)))
        self.assertFalse(rule.is_open(datetime(2026, 10, 12, 20, 0, tzinfo=timezone.utc)))

    def test_transfer_datetime_has_human_readable_utc_format(self) -> None:
        self.assertEqual(
            format_utc_datetime("2026-10-07T00:00:00Z"),
            "Wednesday, 7 October 2026 at 00:00 UTC",
        )

    def test_transfer_cannot_be_recorded_before_rule_start(self) -> None:
        rule = TransferRule(
            season_id="2026-27",
            gameweek=10,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=1),
            deadline_utc=datetime.now(timezone.utc) + timedelta(days=1),
            max_transfers_per_team=1,
        )

        with self.assertRaisesRegex(ValueError, "transfer window is not open"):
            record_transfer(
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

    def test_pre_start_transfer_does_not_use_the_transfer_limit(self) -> None:
        old_record = self.save_sample_transfer()
        old_record["season_id"] = "2026-27"
        old_record["rule_id"] = "2026-27-GW10"
        old_record["submitted_at_utc"] = "2019-12-31T23:59:59+00:00"
        with self.ledger_path.open("w", newline="", encoding="utf-8") as ledger_file:
            writer = csv.DictWriter(ledger_file, fieldnames=old_record.keys())
            writer.writeheader()
            writer.writerow(old_record)

        rule = TransferRule(
            season_id="2026-27",
            gameweek=10,
            start_utc="2020-01-01T00:00:00Z",
            deadline_utc="2099-09-01T20:00:00Z",
            max_transfers_per_team=1,
        )

        new_record = record_transfer(
            self.ledger_path,
            team_name="Chelsea Dagger",
            current_player_ids=["player-1", "player-2"],
            player_out_id="player-2",
            player_out_name="Player Two",
            player_in_id="player-4",
            player_in_name="Player Four",
            player_in_club="Club Four",
            effective_gameweek=10,
            rule=rule,
        )

        self.assertEqual(new_record["action_type"], "transfer")
        self.assertEqual(len(load_transfer_records(self.ledger_path)), 2)

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
        active_transfer = get_active_team_transfer(records, "Chelsea Dagger")
        self.assertIsNotNone(active_transfer)
        self.assertEqual(active_transfer["player_in_id"], "player-4")


if __name__ == "__main__":
    unittest.main()
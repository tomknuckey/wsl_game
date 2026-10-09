import csv
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from utils.general_utils import (
    build_weekly_rosters,
    calculate_weekly_results,
    generate_gameweek_goals,
)
from utils.transfer_utils import (
    TransferRule,
    load_transfer_records,
    record_correction,
    record_transfer,
)


class WeeklyRosterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.ledger_path = Path(self.temp_directory.name) / "team_transfers.csv"

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def test_transfer_changes_roster_from_effective_gameweek(self) -> None:
        record_transfer(
            self.ledger_path,
            team_name="Chelsea Dagger",
            current_player_ids=["A", "B", "C", "D", "E"],
            player_out_id="A",
            player_out_name="Player A",
            player_in_id="F",
            player_in_name="Player F",
            player_in_club="Club F",
            effective_gameweek=10,
        )
        picks = pd.DataFrame(
            [
                ["Manager One", "Chelsea Dagger", 1, "A"],
                ["Manager One", "Chelsea Dagger", 2, "B"],
                ["Manager One", "Chelsea Dagger", 3, "C"],
                ["Manager One", "Chelsea Dagger", 4, "D"],
                ["Manager One", "Chelsea Dagger", 5, "E"],
            ],
            columns=["name", "team_name", "pick_slot", "player_id"],
        )

        rosters = build_weekly_rosters(picks, self.ledger_path, max_gameweek=10)

        self.assertEqual(
            rosters.loc[rosters["gameweek"] == 9, "player_id"].tolist(),
            ["A", "B", "C", "D", "E"],
        )
        self.assertEqual(
            rosters.loc[rosters["gameweek"] == 10, "player_id"].tolist(),
            ["F", "B", "C", "D", "E"],
        )

    def test_multiple_transfers_are_applied_in_submission_order(self) -> None:
        rule = TransferRule(
            season_id="2026-27",
            gameweek=10,
            deadline_utc="2099-09-01T20:00:00Z",
            max_transfers_per_team=2,
        )
        record_transfer(
            self.ledger_path,
            team_name="Chelsea Dagger",
            current_player_ids=["A", "B", "C", "D", "E"],
            player_out_id="A",
            player_out_name="Player A",
            player_in_id="F",
            player_in_name="Player F",
            player_in_club="Club F",
            effective_gameweek=10,
            rule=rule,
        )
        record_transfer(
            self.ledger_path,
            team_name="Chelsea Dagger",
            current_player_ids=["F", "B", "C", "D", "E"],
            player_out_id="B",
            player_out_name="Player B",
            player_in_id="G",
            player_in_name="Player G",
            player_in_club="Club G",
            effective_gameweek=10,
            rule=rule,
        )
        picks = pd.DataFrame(
            [["Manager One", "Chelsea Dagger", 1, player_id] for player_id in ["A", "B", "C", "D", "E"]],
            columns=["name", "team_name", "pick_slot", "player_id"],
        )

        rosters = build_weekly_rosters(picks, self.ledger_path, max_gameweek=10)

        self.assertEqual(
            rosters.loc[rosters["gameweek"] == 10, "player_id"].tolist(),
            ["F", "G", "C", "D", "E"],
        )

    def test_correction_replaces_original_incoming_player(self) -> None:
        record_transfer(
            self.ledger_path,
            team_name="Chelsea Dagger",
            current_player_ids=["A", "B", "C", "D", "E"],
            player_out_id="A",
            player_out_name="Player A",
            player_in_id="F",
            player_in_name="Player F",
            player_in_club="Club F",
            effective_gameweek=10,
        )
        records = load_transfer_records(self.ledger_path)
        record_correction(
            self.ledger_path,
            team_name="Chelsea Dagger",
            current_player_ids=["A", "B", "C", "D", "E"],
            player_out_id="A",
            player_out_name="Player A",
            player_in_id="G",
            player_in_name="Player G",
            player_in_club="Club G",
            correction_of_transfer_id=records[0]["transfer_id"],
            correction_reason="Player F was unavailable",
            effective_gameweek=10,
        )
        picks = pd.DataFrame(
            [["Manager One", "Chelsea Dagger", 1, player_id] for player_id in ["A", "B", "C", "D", "E"]],
            columns=["name", "team_name", "pick_slot", "player_id"],
        )

        rosters = build_weekly_rosters(picks, self.ledger_path, max_gameweek=10)
        corrected_records = load_transfer_records(self.ledger_path)

        self.assertEqual(
            rosters.loc[rosters["gameweek"] == 10, "player_id"].tolist(),
            ["G", "B", "C", "D", "E"],
        )
        self.assertEqual(len(corrected_records), 2)
        self.assertEqual(corrected_records[1]["correction_of_transfer_id"], records[0]["transfer_id"])

    def test_correction_can_replace_both_transfer_players(self) -> None:
        original = record_transfer(
            self.ledger_path,
            team_name="Chelsea Dagger",
            current_player_ids=["A", "B", "C", "D", "E"],
            player_out_id="A",
            player_out_name="Player A",
            player_in_id="F",
            player_in_name="Player F",
            player_in_club="Club F",
            effective_gameweek=10,
        )
        record_correction(
            self.ledger_path,
            team_name="Chelsea Dagger",
            current_player_ids=["A", "B", "C", "D", "E"],
            player_out_id="B",
            player_out_name="Player B",
            player_in_id="G",
            player_in_name="Player G",
            player_in_club="Club G",
            correction_of_transfer_id=original["transfer_id"],
            correction_reason="Change both transfer selections",
            effective_gameweek=10,
        )
        picks = pd.DataFrame(
            [
                ["Manager One", "Chelsea Dagger", slot, player_id]
                for slot, player_id in enumerate(["A", "B", "C", "D", "E"], start=1)
            ],
            columns=["name", "team_name", "pick_slot", "player_id"],
        )

        rosters = build_weekly_rosters(picks, self.ledger_path, max_gameweek=10)

        self.assertEqual(
            rosters.loc[rosters["gameweek"] == 10, "player_id"].tolist(),
            ["A", "G", "C", "D", "E"],
        )

    def test_transfer_submitted_before_rule_start_is_not_applied_to_roster(self) -> None:
        record = record_transfer(
            self.ledger_path,
            team_name="Chelsea Dagger",
            current_player_ids=["A", "B", "C", "D", "E"],
            player_out_id="A",
            player_out_name="Player A",
            player_in_id="F",
            player_in_name="Player F",
            player_in_club="Club F",
            effective_gameweek=10,
        )
        record["season_id"] = "2026-27"
        record["rule_id"] = "2026-27-GW10"
        record["submitted_at_utc"] = "2026-10-09T23:59:59+00:00"
        with self.ledger_path.open("w", newline="", encoding="utf-8") as ledger_file:
            writer = csv.DictWriter(ledger_file, fieldnames=record.keys())
            writer.writeheader()
            writer.writerow(record)

        picks = pd.DataFrame(
            [["Manager One", "Chelsea Dagger", slot, player_id]
             for slot, player_id in enumerate(["A", "B", "C", "D", "E"], start=1)],
            columns=["name", "team_name", "pick_slot", "player_id"],
        )
        rule = TransferRule(
            season_id="2026-27",
            gameweek=10,
            start_utc="2026-10-10T00:00:00Z",
            deadline_utc="2026-10-12T20:00:00Z",
            max_transfers_per_team=1,
        )

        rosters = build_weekly_rosters(
            picks,
            self.ledger_path,
            max_gameweek=10,
            transfer_rules=[rule],
        )

        self.assertEqual(
            rosters.loc[rosters["gameweek"] == 10, "player_id"].tolist(),
            ["A", "B", "C", "D", "E"],
        )

    def test_goals_are_shared_by_weekly_roster_ownership(self) -> None:
        picks = pd.DataFrame(
            [
                ["Manager One", "Chelsea Dagger", 1, "A"],
                ["Manager Two", "Beth's Booming Army", 1, "A"],
                ["Manager One", "Chelsea Dagger", 2, "B"],
                ["Manager Two", "Beth's Booming Army", 2, "B"],
            ],
            columns=["name", "team_name", "pick_slot", "player_id"],
        )
        goals = pd.DataFrame(
            [["A", 10, 10], ["B", 2, 10]],
            columns=["player_id", "goals", "gameweek"],
        )

        results = calculate_weekly_results(picks, goals, max_gameweek=10)
        gameweek_results = results[results["gameweek"] == 10]

        self.assertEqual(len(gameweek_results), 2)
        self.assertEqual(gameweek_results["goals"].tolist(), [6.0, 6.0])

    def test_gameweek_goals_keep_their_source_week(self) -> None:
        goals_path = Path(self.temp_directory.name) / "GW_10.csv"
        pd.DataFrame([["A", 2]]).to_csv(goals_path, index=False, header=False)
        goals_path.write_text("player_id,goals\nA,2\n", encoding="utf-8")

        goals = generate_gameweek_goals(11, "actual", goals_dir=Path(self.temp_directory.name))

        self.assertEqual(goals.to_dict("records"), [{"player_id": "A", "gameweek": 10, "goals": 2}])


if __name__ == "__main__":
    unittest.main()

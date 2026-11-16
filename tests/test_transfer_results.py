import unittest
from datetime import datetime, timezone

import pandas as pd

from utils.transfer_results import (
    build_transfer_outcomes,
    get_effective_transfers,
)
from utils.transfer_utils import TransferRule


class TransferResultsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rule = TransferRule(
            season_id="2026-27",
            gameweek=10,
            start_utc="2026-10-01T00:00:00Z",
            deadline_utc="2026-11-18T20:00:00Z",
            max_transfers_per_team=1,
        )
        self.transfer = {
            "team_name": "Team One",
            "season_id": "2026-27",
            "rule_id": "2026-27-GW10",
            "transfer_id": "transfer-1",
            "player_out_id": "out-1",
            "player_out_name": "Player Out",
            "player_in_id": "in-1",
            "player_in_name": "Player In",
            "player_in_club": "Club In",
            "effective_gameweek": "10",
            "submitted_at_utc": "2026-10-05T12:00:00+00:00",
            "action_type": "transfer",
            "correction_of_transfer_id": "",
            "correction_reason": "",
        }

    def test_latest_correction_replaces_transfer_without_adding_a_row(self) -> None:
        first_correction = {
            **self.transfer,
            "transfer_id": "correction-1",
            "player_in_id": "in-2",
            "player_in_name": "Earlier Correction",
            "action_type": "correction",
            "correction_of_transfer_id": "transfer-1",
            "submitted_at_utc": "2026-10-06T12:00:00+00:00",
        }
        latest_correction = {
            **first_correction,
            "transfer_id": "correction-2",
            "player_in_id": "in-3",
            "player_in_name": "Latest Correction",
            "submitted_at_utc": "2026-10-07T12:00:00+00:00",
        }

        effective = get_effective_transfers(
            [self.transfer, first_correction, latest_correction],
            [self.rule],
            "2026-27",
            as_of_utc=datetime(2026, 11, 19, tzinfo=timezone.utc),
        )

        self.assertEqual(len(effective), 1)
        self.assertEqual(effective[0]["player_in_id"], "in-3")
        self.assertEqual(effective[0]["player_in_name"], "Latest Correction")

    def test_other_seasons_are_not_included(self) -> None:
        previous_season_transfer = {
            **self.transfer,
            "season_id": "2025-26",
            "rule_id": "2025-26-GW10",
        }

        effective = get_effective_transfers(
            [self.transfer, previous_season_transfer],
            [self.rule],
            "2026-27",
            as_of_utc=datetime(2026, 11, 19, tzinfo=timezone.utc),
        )

        self.assertEqual(len(effective), 1)
        self.assertEqual(effective[0]["season_id"], "2026-27")

    def test_transfers_are_hidden_until_the_deadline(self) -> None:
        before_deadline = get_effective_transfers(
            [self.transfer],
            [self.rule],
            "2026-27",
            as_of_utc=datetime(2026, 11, 18, 19, 59, tzinfo=timezone.utc),
        )
        at_deadline = get_effective_transfers(
            [self.transfer],
            [self.rule],
            "2026-27",
            as_of_utc=datetime(2026, 11, 18, 20, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(before_deadline, [])
        self.assertEqual(at_deadline, [self.transfer])

    def test_unannounced_rule_transfers_are_hidden_after_an_older_deadline(self) -> None:
        next_rule = TransferRule(
            season_id="2026-27",
            gameweek=15,
            start_utc="2026-11-19T00:00:00Z",
            deadline_utc="2026-12-01T20:00:00Z",
            max_transfers_per_team=1,
        )
        next_transfer = {
            **self.transfer,
            "rule_id": next_rule.rule_id,
            "effective_gameweek": "15",
        }

        effective = get_effective_transfers(
            [self.transfer, next_transfer],
            [self.rule, next_rule],
            "2026-27",
            as_of_utc=datetime(2026, 11, 19, tzinfo=timezone.utc),
        )

        self.assertEqual(effective, [self.transfer])

    def test_outcome_sums_goal_data_from_effective_gameweek(self) -> None:
        weekly_goals = pd.DataFrame(
            [
                ["in-1", 90, 9],
                ["out-1", 90, 9],
                ["in-1", 8, 10],
                ["out-1", 6, 10],
                ["in-1", 3, 11],
                ["out-1", 1, 11],
            ],
            columns=["player_id", "goals", "gameweek"],
        )

        outcomes = build_transfer_outcomes([self.transfer], weekly_goals)

        self.assertEqual(outcomes[0]["incoming_goals"], 11)
        self.assertEqual(outcomes[0]["outgoing_goals"], 7)
        self.assertEqual(outcomes[0]["net_goals"], 4)

    def test_outcome_is_pending_when_no_post_transfer_weeks_exist(self) -> None:
        weekly_goals = pd.DataFrame(
            [["in-1", 2, 9]],
            columns=["player_id", "goals", "gameweek"],
        )

        outcomes = build_transfer_outcomes([self.transfer], weekly_goals)

        self.assertIsNone(outcomes[0]["incoming_goals"])
        self.assertIsNone(outcomes[0]["outgoing_goals"])
        self.assertIsNone(outcomes[0]["net_goals"])


if __name__ == "__main__":
    unittest.main()

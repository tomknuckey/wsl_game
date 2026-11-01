import unittest
from unittest.mock import patch

import pandas as pd

import utils.espn_utils as espn_utils
from utils.espn_utils import _parse_match_goal_totals, normalize_player_name


class NormalizePlayerNameTests(unittest.TestCase):
    def test_normalizes_case_accents_and_punctuation(self):
        self.assertEqual(
            normalize_player_name("  Éve-Marie O'Connor! "), "eve marie o connor"
        )


class ParseMatchGoalTotalsTests(unittest.TestCase):
    def test_reconciles_score_and_excludes_own_goals_from_player_totals(self):
        summary = {
            "header": {
                "id": "match-1",
                "competitions": [{"competitors": [{"score": "2"}, {"score": "1"}]}],
            },
            "keyEvents": [
                {
                    "scoringPlay": True,
                    "type": {"text": "Goal"},
                    "participants": [
                        {"athlete": {"displayName": "Éve-Marie O'Connor"}}
                    ],
                },
                {
                    "scoringPlay": True,
                    "type": {"text": "Own Goal"},
                    "participants": [{"athlete": {"displayName": "Defender"}}],
                },
                {
                    "scoringPlay": True,
                    "shootout": True,
                    "type": {"text": "Penalty"},
                    "participants": [{"athlete": {"displayName": "Shooter"}}],
                },
                {
                    "scoringPlay": True,
                    "type": {"text": "Goal"},
                    "participants": [
                        {"athlete": {"displayName": "Eve Marie O Connor"}}
                    ],
                },
            ],
        }

        self.assertEqual(
            _parse_match_goal_totals("match-1", summary),
            (3, 3, {"eve marie o connor": 2}),
        )

    def test_rejects_goal_events_that_do_not_match_the_final_score(self):
        summary = {
            "header": {
                "id": "match-1",
                "competitions": [{"competitors": [{"score": "1"}, {"score": "0"}]}],
            },
            "keyEvents": [],
        }

        with self.assertRaisesRegex(ValueError, "do not match the final score"):
            _parse_match_goal_totals("match-1", summary)


class GenerateEspnGoalFrameTests(unittest.TestCase):
    def test_fetches_and_aggregates_a_valid_completed_season(self):
        event = {
            "id": "match-1",
            "season": {"year": 2025},
            "competitions": [{"status": {"type": {"completed": True}}}],
        }
        summary = {
            "header": {
                "id": "match-1",
                "competitions": [{"competitors": [{"score": "1"}, {"score": "0"}]}],
            },
            "keyEvents": [
                {
                    "scoringPlay": True,
                    "type": {"text": "Goal"},
                    "participants": [{"athlete": {"displayName": "Ada Player"}}],
                }
            ],
        }

        def fake_fetch(url, purpose):
            if "schedule" in purpose:
                return {"events": [event]}
            return summary

        with patch.object(espn_utils, "LAST_SEASON_CALENDAR_YEARS", (2025,)):
            with patch.object(espn_utils, "EXPECTED_LAST_SEASON_MATCHES", 1):
                with patch.object(
                    espn_utils, "_fetch_espn_json", side_effect=fake_fetch
                ):
                    frame = espn_utils.generate_espn_goal_frame(
                        pd.DataFrame(
                            {
                                "player_id": ["WSL_0001"],
                                "full_name": ["Ada Player"],
                            }
                        )
                    )

        self.assertEqual(
            frame.to_dict("records"),
            [
                {
                    "season": "2025-26",
                    "player_id": "WSL_0001",
                    "normalized_name": "ada player",
                    "last_season_goals": 1,
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()

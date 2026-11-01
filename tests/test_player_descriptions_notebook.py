import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from utils.espn_utils import LAST_SEASON

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "player_descriptions.ipynb"
NOTEBOOK = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
FUNCTION_CELL = next(
    cell
    for cell in NOTEBOOK["cells"]
    if cell.get("id") == "player-description-functions"
)
FUNCTIONS = {
    "LAST_SEASON": LAST_SEASON,
    "__name__": "player_descriptions_notebook_tests",
}
exec(compile("".join(FUNCTION_CELL["source"]), str(NOTEBOOK_PATH), "exec"), FUNCTIONS)


class PlayerDescriptionNotebookTests(unittest.TestCase):
    def test_builds_fact_rows_with_trends_ownership_and_season_comparison(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            input_dir = data_dir / "input" / "test"
            goals_dir = input_dir / "player_goals"
            intermediate_dir = data_dir / "intermediate" / "test"
            output_dir = data_dir / "output" / "test"
            goals_dir.mkdir(parents=True)
            intermediate_dir.mkdir(parents=True)
            output_dir.mkdir(parents=True)

            pd.DataFrame(
                {
                    "player_id": ["WSL_1", "WSL_2", "WSL_3", "WSL_4"],
                    "full_name": ["Palmer", "Neto", "Mead", "No Goals"],
                    "team": ["Club A", "Club B", "Club C", "Club D"],
                }
            ).to_csv(input_dir / "player_reference.csv", index=False)
            pd.DataFrame(
                {"player_id": ["WSL_1", "WSL_2", "WSL_3"], "goals": [1, 1, 1]}
            ).to_csv(goals_dir / "GW_1.csv", index=False)
            pd.DataFrame(
                {"player_id": ["WSL_1", "WSL_2", "WSL_3"], "goals": [1, 2, 1]}
            ).to_csv(goals_dir / "GW_2.csv", index=False)
            pd.DataFrame({"player_id": ["WSL_2"]}).to_csv(
                goals_dir / "GW_3.csv", index=False
            )
            pd.DataFrame({"player_id": ["WSL_1", "WSL_2"], "num_picks": [3, 5]}).to_csv(
                output_dir / "player_pics.csv", index=False
            )
            pd.DataFrame(
                {
                    "season": [LAST_SEASON, LAST_SEASON],
                    "player_id": ["WSL_1", "WSL_2"],
                    "normalized_name": ["palmer", "neto"],
                    "last_season_goals": [10, 5],
                }
            ).to_csv(intermediate_dir / "espn_goals.csv", index=False)

            facts = FUNCTIONS["build_player_description_facts"](data_dir, "test")

        by_id = facts.set_index("player_id")
        self.assertEqual(by_id.loc["WSL_1", "current_season_goals"], 2)
        self.assertEqual(by_id.loc["WSL_1", "goals_by_gameweek"], "[1, 1, 0]")
        self.assertEqual(by_id.loc["WSL_1", "gameweeks_since_last_goal"], 1)
        self.assertEqual(by_id.loc["WSL_1", "last_season_goals"], 10)
        self.assertEqual(by_id.loc["WSL_2", "brace_gameweeks"], "[2]")
        self.assertEqual(by_id.loc["WSL_2", "ownership_count"], 5)
        self.assertEqual(by_id.loc["WSL_3", "current_season_goal_rank"], 2)
        self.assertEqual(by_id.loc["WSL_3", "current_season_goal_rank_tie_count"], 2)
        self.assertEqual(by_id.loc["WSL_3", "ownership_count"], 0)
        self.assertNotIn("WSL_4", set(facts["player_id"]))

    def test_rejects_nonconsecutive_gameweek_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            input_dir = data_dir / "input" / "test"
            goals_dir = input_dir / "player_goals"
            intermediate_dir = data_dir / "intermediate" / "test"
            output_dir = data_dir / "output" / "test"
            goals_dir.mkdir(parents=True)
            intermediate_dir.mkdir(parents=True)
            output_dir.mkdir(parents=True)
            pd.DataFrame(
                {"player_id": ["WSL_1"], "full_name": ["Player"], "team": ["Club"]}
            ).to_csv(input_dir / "player_reference.csv", index=False)
            pd.DataFrame({"player_id": ["WSL_1"]}).to_csv(
                goals_dir / "GW_1.csv", index=False
            )
            pd.DataFrame({"player_id": ["WSL_1"]}).to_csv(
                goals_dir / "GW_3.csv", index=False
            )
            pd.DataFrame({"player_id": ["WSL_1"], "num_picks": [1]}).to_csv(
                output_dir / "player_pics.csv", index=False
            )
            pd.DataFrame(
                {
                    "season": [LAST_SEASON],
                    "player_id": ["WSL_1"],
                    "normalized_name": ["player"],
                    "last_season_goals": [1],
                }
            ).to_csv(intermediate_dir / "espn_goals.csv", index=False)

            with self.assertRaisesRegex(ValueError, "not consecutive"):
                FUNCTIONS["build_player_description_facts"](data_dir, "test")

    def test_rejects_wrong_prior_season_goal_total(self):
        facts = {
            "current_season_goals": 1,
            "completed_gameweeks": 6,
            "goals_by_gameweek": "[0, 0, 1, 0, 0, 0]",
            "ownership_count": 0,
            "last_season_goals": 2,
        }
        with self.assertRaisesRegex(ValueError, "prior-season facts"):
            FUNCTIONS["validate_description"](
                "Smilla Holmberg scored once this season, following thirteen goals last season.",
                "WSL_0009",
                facts,
            )

    def test_rejects_ownership_rank_misrepresented_as_scoring_rank(self):
        facts = {
            "current_season_goals": 0,
            "completed_gameweeks": 6,
            "goals_by_gameweek": "[0, 0, 0, 0, 0, 0]",
            "ownership_count": 4,
            "ownership_rank": 3,
            "last_season_goals": 13,
            "current_season_goal_rank": None,
        }
        with self.assertRaisesRegex(ValueError, "unavailable scoring rank"):
            FUNCTIONS["validate_description"](
                "Alessia Russo ranks third for goals this season after scoring 13 goals last year.",
                "WSL_0018",
                facts,
            )

    def test_rejects_scoring_rank_for_one_goal(self):
        facts = {
            "current_season_goals": 1,
            "current_season_goal_rank": 28,
            "completed_gameweeks": 6,
            "goals_by_gameweek": "[0, 0, 1, 0, 0, 0]",
            "ownership_count": 0,
            "last_season_goals": None,
        }
        with self.assertRaisesRegex(ValueError, "one-goal-or-less"):
            FUNCTIONS["validate_description"](
                "The player has one goal this season and ranks 28th.",
                "WSL_1",
                facts,
            )

    def test_validates_owner_count_and_rejects_contradictory_backing_claim(self):
        facts = {
            "current_season_goals": 0,
            "completed_gameweeks": 6,
            "goals_by_gameweek": "[0, 0, 0, 0, 0, 0]",
            "ownership_count": 1,
            "last_season_goals": None,
        }
        with self.assertRaisesRegex(ValueError, "nobody picked"):
            FUNCTIONS["validate_description"](
                "No managers backing Chloe yet, despite being picked by one owner.",
                "WSL_0353",
                facts,
            )

    def test_rejects_wrong_number_of_owners(self):
        facts = {
            "current_season_goals": 0,
            "completed_gameweeks": 6,
            "goals_by_gameweek": "[0, 0, 0, 0, 0, 0]",
            "ownership_count": 1,
            "last_season_goals": None,
        }
        with self.assertRaisesRegex(ValueError, "ownership count"):
            FUNCTIONS["validate_description"](
                "Two owners have picked Chloe this season.",
                "WSL_0353",
                facts,
            )

    def test_valid_description_uses_matching_facts(self):
        facts = {
            "current_season_goals": 0,
            "completed_gameweeks": 6,
            "goals_by_gameweek": "[0, 0, 0, 0, 0, 0]",
            "ownership_count": 4,
            "last_season": "2025-26",
            "last_season_goals": 13,
        }
        self.assertEqual(
            FUNCTIONS["validate_description"](
                "Alessia Russo has yet to score in six gameweeks, following 13 league goals in the 2025-26 season; four managers have picked her.",
                "WSL_0018",
                facts,
            ),
            "Alessia Russo has yet to score in six gameweeks, following 13 league goals in the 2025-26 season; four managers have picked her.",
        )

    def test_validates_current_and_prior_goal_totals_in_contrast_clauses(self):
        facts = {
            "current_season_goals": 0,
            "completed_gameweeks": 6,
            "goals_by_gameweek": "[0, 0, 0, 0, 0, 0]",
            "ownership_count": 4,
            "last_season": "2025-26",
            "last_season_goals": 13,
        }
        description = (
            "Alessia Russo has scored zero goals so far this season despite scoring "
            "13 goals in 2025-26."
        )
        self.assertEqual(
            FUNCTIONS["validate_description"](description, "WSL_0018", facts),
            description,
        )

    def test_rejects_zero_ownership_claim_when_player_is_owned(self):
        facts = {
            "current_season_goals": 0,
            "completed_gameweeks": 6,
            "goals_by_gameweek": "[0, 0, 0, 0, 0, 0]",
            "ownership_count": 1,
            "last_season_goals": None,
        }
        with self.assertRaisesRegex(ValueError, "despite nonzero ownership"):
            FUNCTIONS["validate_description"](
                "No managers have picked Lisa this season.",
                "WSL_0353",
                facts,
            )

    def test_rejects_historical_ownership_claims_even_when_current_count_matches(self):
        facts = {
            "current_season_goals": 0,
            "completed_gameweeks": 6,
            "goals_by_gameweek": "[0, 0, 0, 0, 0, 0]",
            "ownership_count": 4,
            "last_season": "2025-26",
            "last_season_goals": 13,
        }
        with self.assertRaisesRegex(ValueError, "historical ownership"):
            FUNCTIONS["validate_description"](
                "Alessia has scored zero goals this season but remains popular with four managers who picked her last season after 13 league goals.",
                "WSL_0018",
                facts,
            )

    def test_rejects_goal_total_not_supported_by_prior_season_facts(self):
        facts = {
            "current_season_goals": 0,
            "completed_gameweeks": 6,
            "goals_by_gameweek": "[0, 0, 0, 0, 0, 0]",
            "ownership_count": 4,
            "last_season": "2025-26",
            "last_season_goals": 13,
        }
        with self.assertRaisesRegex(ValueError, "prior-season facts"):
            FUNCTIONS["validate_description"](
                "Alessia Russo has yet to score in six gameweeks, following 99 league goals in 2025-26.",
                "WSL_0018",
                facts,
            )

    def test_generation_cell_rejects_stale_validator_kernel(self):
        generation_cell = next(
            cell
            for cell in NOTEBOOK["cells"]
            if cell.get("id") == "generate-player-descriptions"
        )
        self.assertIn(
            'globals().get("DESCRIPTION_VALIDATOR_VERSION") != 7',
            "".join(generation_cell["source"]),
        )

    def test_generation_collects_validation_issues_for_final_report(self):
        generation_cell = next(
            cell
            for cell in NOTEBOOK["cells"]
            if cell.get("id") == "generate-player-descriptions"
        )
        generation_source = "".join(generation_cell["source"])
        self.assertIn("generation_issues = []", generation_source)
        self.assertIn("except ValueError as error:", generation_source)
        self.assertIn("generation_issues.append(", generation_source)

        output_cell = next(
            cell
            for cell in NOTEBOOK["cells"]
            if cell.get("id") == "save-player-descriptions"
        )
        output_source = "".join(output_cell["source"])
        self.assertIn("if generation_issues:", output_source)
        self.assertIn("display(pd.DataFrame(generation_issues))", output_source)
        self.assertIn("The existing output file is unchanged.", output_source)

    def test_generation_continues_after_a_validation_failure(self):
        generation_cell = next(
            cell
            for cell in NOTEBOOK["cells"]
            if cell.get("id") == "generate-player-descriptions"
        )

        def generate_description(player_facts, model, ollama_url, validation_feedback=None):
            if player_facts["player_id"] == "WSL_1":
                raise ValueError("invalid rank")
            return "Player two has scored twice."

        namespace = {
            "DESCRIPTION_VALIDATOR_VERSION": 7,
            "MAX_VALIDATION_ATTEMPTS": 3,
            "facts": pd.DataFrame(
                [
                    {"player_id": "WSL_1", "full_name": "Player One"},
                    {"player_id": "WSL_2", "full_name": "Player Two"},
                ]
            ),
            "expected_player_ids": ["WSL_1", "WSL_2"],
            "MODEL": "test-model",
            "OLLAMA_URL": "http://localhost",
            "generate_player_description": generate_description,
        }
        exec(compile("".join(generation_cell["source"]), str(NOTEBOOK_PATH), "exec"), namespace)

        self.assertEqual(namespace["generated_rows"], [
            {"player_id": "WSL_2", "description": "Player two has scored twice."}
        ])
        self.assertEqual(namespace["generation_issues"], [
            {"player_id": "WSL_1", "full_name": "Player One", "issue": "invalid rank", "attempts": 3}
        ])

    def test_generation_retries_with_validation_feedback(self):
        generation_cell = next(
            cell
            for cell in NOTEBOOK["cells"]
            if cell.get("id") == "generate-player-descriptions"
        )
        calls = []

        def generate_description(player_facts, model, ollama_url, validation_feedback=None):
            calls.append(validation_feedback)
            if len(calls) == 1:
                raise ValueError("unsupported scoring rank")
            return "Player has scored twice this season."

        namespace = {
            "DESCRIPTION_VALIDATOR_VERSION": 7,
            "MAX_VALIDATION_ATTEMPTS": 3,
            "facts": pd.DataFrame(
                [{"player_id": "WSL_1", "full_name": "Player One"}]
            ),
            "expected_player_ids": ["WSL_1"],
            "MODEL": "test-model",
            "OLLAMA_URL": "http://localhost",
            "generate_player_description": generate_description,
        }
        exec(compile("".join(generation_cell["source"]), str(NOTEBOOK_PATH), "exec"), namespace)

        self.assertEqual(calls, [None, "unsupported scoring rank"])
        self.assertEqual(namespace["generation_issues"], [])
        self.assertEqual(len(namespace["generated_rows"]), 1)

    def test_generation_uses_local_ollama_response(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps(
                    {
                        "response": json.dumps(
                            {"description": "Palmer is still scoreless."}
                        )
                    }
                ).encode("utf-8")

        facts = {
            "player_id": "WSL_1",
            "full_name": "Palmer",
            "current_season_goals": 0,
            "completed_gameweeks": 6,
            "goals_by_gameweek": "[0, 0, 0, 0, 0, 0]",
            "ownership_count": 0,
            "last_season_goals": None,
        }
        with patch("urllib.request.urlopen", return_value=FakeResponse()) as urlopen:
            description = FUNCTIONS["generate_player_description"](
                facts, "local-test-model", "http://localhost:11434/api/generate"
            )

        self.assertEqual(description, "Palmer is still scoreless.")
        request = urlopen.call_args.args[0]
        request_body = json.loads(request.data)
        self.assertIn("Palmer", request_body["prompt"])
        self.assertNotIn("ownership_rank", request_body["prompt"])
        self.assertEqual(request_body["model"], "local-test-model")


if __name__ == "__main__":
    unittest.main()

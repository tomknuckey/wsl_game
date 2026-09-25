import unittest
from pathlib import Path

import pandas as pd

from app import get_manager_count, get_weeks_of_data


class TestApp(unittest.TestCase):
    def test_get_manager_count_uses_name_when_team_missing(self):
        df = pd.DataFrame({
            "name": ["Alice", "Bob", "Alice"],
            "goals": [1.2, 2.5, 3.1],
        })

        self.assertEqual(get_manager_count(df), 2)

    def test_get_manager_count_uses_manager_label(self):
        df = pd.DataFrame({
            "Manager": ["Alice", "Bob", "Alice"],
            "Goals": [1.2, 2.5, 3.1],
        })

        self.assertEqual(get_manager_count(df), 2)

    def test_get_weeks_of_data_counts_weekly_goal_files(self):
        input_dir = Path("data/input/actual/player_goals")
        if input_dir.exists():
            count = get_weeks_of_data("actual")
            self.assertGreaterEqual(count, 1)
        else:
            self.assertEqual(get_weeks_of_data("actual"), 0)


if __name__ == "__main__":
    unittest.main()

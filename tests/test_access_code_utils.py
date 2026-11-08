import csv
import tempfile
import unittest
from pathlib import Path

from utils.access_code_utils import (
    authenticate_team,
    load_team_access_codes,
    team_access_codes_path,
    validate_access_codes,
)


class TeamAccessCodeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.access_codes = {
            "Chelsea Dagger": "9736",
            "UpTheImps": "7392",
        }

    def test_correct_code_authenticates_team(self) -> None:
        self.assertEqual(
            authenticate_team("  chelsea   dagger ", "9736", self.access_codes),
            "Chelsea Dagger",
        )

    def test_wrong_code_does_not_authenticate_team(self) -> None:
        self.assertIsNone(
            authenticate_team("Chelsea Dagger", "7392", self.access_codes)
        )

    def test_team_cannot_use_another_teams_code(self) -> None:
        self.assertIsNone(
            authenticate_team("Chelsea Dagger", "7392", self.access_codes)
        )

    def test_duplicate_codes_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "distinct access code"):
            validate_access_codes({"Team A": "1234", "Team B": "1234"})

    def test_codes_must_be_exactly_four_digits(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly four digits"):
            validate_access_codes({"Team A": "123"})

    def test_actual_and_test_access_code_files_are_separate(self) -> None:
        self.assertNotEqual(
            team_access_codes_path("actual"),
            team_access_codes_path("test"),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            actual_path = Path(temp_dir) / "actual.csv"
            test_path = Path(temp_dir) / "test.csv"
            for path, code in ((actual_path, "1234"), (test_path, "5678")):
                with path.open("w", newline="", encoding="utf-8") as code_file:
                    writer = csv.DictWriter(
                        code_file,
                        fieldnames=["team_name", "access_code"],
                    )
                    writer.writeheader()
                    writer.writerow(
                        {"team_name": "Chelsea Dagger", "access_code": code}
                    )

            actual_codes = load_team_access_codes(actual_path)
            test_codes = load_team_access_codes(test_path)

        self.assertEqual(
            authenticate_team("Chelsea Dagger", "1234", actual_codes),
            "Chelsea Dagger",
        )
        self.assertIsNone(
            authenticate_team("Chelsea Dagger", "1234", test_codes)
        )
        self.assertEqual(
            authenticate_team("Chelsea Dagger", "5678", test_codes),
            "Chelsea Dagger",
        )


if __name__ == "__main__":
    unittest.main()
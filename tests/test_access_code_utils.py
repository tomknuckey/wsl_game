import unittest

from utils.access_code_utils import authenticate_team, validate_access_codes


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


if __name__ == "__main__":
    unittest.main()
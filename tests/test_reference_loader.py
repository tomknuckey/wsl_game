import unittest

from utils.general_utils import load_reference_sheet


class LoadReferenceSheetTests(unittest.TestCase):
    def test_load_reference_sheet_handles_comma_delimited_csv(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "player_reference.csv"
            path.write_text(
                "full_name,team,player_id\n"
                "Alessia Russo,Arsenal,WSL_0018\n"
                "Caitlin Foord,Arsenal,WSL_0017\n",
                encoding="utf-8",
            )

            df = load_reference_sheet(str(path))

            self.assertEqual(list(df.columns), ["full_name", "team", "player_id"])
            self.assertEqual(df.loc[0, "full_name"], "Alessia Russo")
            self.assertEqual(df.loc[1, "player_id"], "WSL_0017")


if __name__ == "__main__":
    unittest.main()

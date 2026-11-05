"""Generate and save the prior-season ESPN scorer data."""

import logging
from pathlib import Path

from config import data_source
from utils.general_utils import load_reference_sheet
from utils.espn_utils import generate_espn_goal_frame

logging.basicConfig(level=logging.INFO)


def main() -> None:
    reference_path = Path(f"data/input/{data_source}/player_reference.csv")
    reference = load_reference_sheet(str(reference_path))
    output_dir = Path(f"data/intermediate/{data_source}")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "espn_goals.csv"

    espn_goals = generate_espn_goal_frame(reference)
    espn_goals.to_csv(output_path, index=False)
    logging.info("ESPN scorer data saved to %s", output_path)


if __name__ == "__main__":
    main()

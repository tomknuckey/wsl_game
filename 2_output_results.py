import pandas as pd
import random
from config import (
    data_source,
    max_gw,
    transfer_rules,
)
from utils.general_utils import (
    calculate_weekly_results,
    generate_best_differential,
    generate_gameweek_goals,
    generate_manager_ownership,
    generate_top_missed,
    number_of_pics,
    load_reference_sheet,
)
from utils.transfer_utils import transfer_rules_from_config

import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
random.seed(42)

logging.info("Started Running")

pdf_form = pd.read_csv(f"data/intermediate/{data_source}/player_pics.csv")

pdf_reference = load_reference_sheet(f"data/input/{data_source}/player_reference.csv")

pdf_prep = pdf_reference.merge(pdf_form, how="inner", on="full_name")

output_dir = Path(f"data/output/{data_source}")
output_dir.mkdir(parents=True, exist_ok=True)

pdf_pics = number_of_pics(pdf_prep, output_dir)

generate_manager_ownership(pdf_prep, pdf_pics, output_dir)

pdf_goals_by_gameweek = generate_gameweek_goals(max_gw, data_source)
pdf_goals_agg = pdf_goals_by_gameweek.groupby("player_id").agg(
    {"goals": "sum"}
).reset_index().merge(
    pdf_reference[["player_id", "full_name", "team"]],
    how="left",
    on="player_id",
)
pdf_goals_agg.sort_values("goals", ascending=False).to_csv(output_dir / "pdf_goals_agg.csv", index=False)

generate_top_missed(pdf_goals_agg, pdf_pics, output_dir)
generate_best_differential(pdf_pics, pdf_goals_agg, pdf_prep, output_dir)

weekly_results = calculate_weekly_results(
    pdf_prep,
    pdf_goals_by_gameweek,
    roster_path="data/team_transfers.csv",
    max_gameweek=max_gw,
    transfer_rules=transfer_rules_from_config(transfer_rules),
)
pdf_results = (
    weekly_results.groupby(["name", "team_name"], dropna=False)["goals"]
    .sum()
    .round(2)
    .reset_index()
)
pdf_results.to_csv(output_dir / "results.csv", index=False)

logging.info("Results saved to CSV; transfer rules: %s", transfer_rules)
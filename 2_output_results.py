import argparse
import pandas as pd
import random
from pathlib import Path

from config import (
    data_source,
    max_gw,
    transfer_rules,
)
from utils.general_utils import (
    calculate_player_weekly_results,
    generate_best_differential,
    generate_gameweek_goals,
    generate_manager_ownership,
    generate_top_missed,
    number_of_pics,
    load_reference_sheet,
)
from utils.transfer_utils import transfer_rules_from_config

import logging

logging.basicConfig(level=logging.INFO)
random.seed(42)

parser = argparse.ArgumentParser(description="Generate reports for the selected data source.")
parser.add_argument(
    "--data-source",
    default=data_source,
    help=f"Data source directory under data/input (default: {data_source}).",
)
selected_data_source = parser.parse_args().data_source

logging.info("Started Running")

pdf_form = pd.read_csv(
    f"data/intermediate/{selected_data_source}/player_pics.csv"
)

pdf_reference = load_reference_sheet(
    f"data/input/{selected_data_source}/player_reference.csv"
)

pdf_prep = pdf_reference.merge(pdf_form, how="inner", on="full_name")

output_dir = Path(f"data/output") / selected_data_source
output_dir.mkdir(parents=True, exist_ok=True)

pdf_pics = number_of_pics(pdf_prep, output_dir)

generate_manager_ownership(pdf_prep, pdf_pics, output_dir)

pdf_goals_by_gameweek = generate_gameweek_goals(max_gw, selected_data_source)
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

transfer_ledger_path = (
    Path("data/team_transfers.csv")
    if selected_data_source == "actual"
    else Path("data/input") / selected_data_source / "team_transfers.csv"
)
last_gameweek_with_data = (
    int(pdf_goals_by_gameweek["gameweek"].max())
    if not pdf_goals_by_gameweek.empty
    else 1
)
player_weekly_results = calculate_player_weekly_results(
    pdf_prep,
    pdf_goals_by_gameweek,
    roster_path=transfer_ledger_path,
    max_gameweek=last_gameweek_with_data,
    transfer_rules=transfer_rules_from_config(transfer_rules),
)
weekly_results = (
    player_weekly_results.groupby(["name", "team_name", "gameweek"], dropna=False)[
        "goals"
    ]
    .sum()
    .round(2)
    .reset_index()
)
pdf_results = (
    weekly_results.groupby(["name", "team_name"], dropna=False)["goals"]
    .sum()
    .round(2)
    .reset_index()
)
pdf_results.to_csv(output_dir / "results.csv", index=False)

player_weekly_results = player_weekly_results.merge(
    pdf_reference[["player_id", "full_name", "team"]],
    on="player_id",
    how="left",
    validate="many_to_one",
)
player_weekly_results = player_weekly_results[
    ["name", "team_name", "player_id", "full_name", "team", "gameweek", "goals"]
].sort_values(
    ["name", "team_name", "gameweek", "full_name"]
).reset_index(drop=True)
player_weekly_results.to_csv(
    output_dir / "manager_player_gameweek_points.csv",
    index=False,
)
manager_player_results = (
    player_weekly_results.groupby(
        ["name", "team_name", "player_id", "full_name", "team"],
        dropna=False,
    )["goals"]
    .sum()
    .round(2)
    .reset_index()
    .sort_values(
        ["name", "team_name", "goals", "full_name"],
        ascending=[True, True, False, True],
    )
    .reset_index(drop=True)
)
manager_player_results.to_csv(
    output_dir / "manager_player_points.csv",
    index=False,
)

logging.info(
    "Results and player contribution reports saved for data source '%s'; "
    "transfer rules: %s",
    selected_data_source,
    transfer_rules,
)
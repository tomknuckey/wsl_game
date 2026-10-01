import pandas as pd
import random
from config import (
    data_source,
    max_gw,
)
from utils.general_utils import (
    generate_best_differential,
    generate_goals,
    generate_manager_ownership,
    generate_top_missed,
    number_of_pics,
    adjust_goals,
    generate_results,
    load_reference_sheet,
)

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

pdf_goals_agg = generate_goals(max_gw, data_source).merge(
    pdf_reference[["player_id", "full_name"]], how="left", on="player_id"
)
pdf_goals_agg.sort_values("goals", ascending=False).to_csv(output_dir / "pdf_goals_agg.csv", index=False)

generate_top_missed(pdf_goals_agg, pdf_pics, output_dir)
generate_best_differential(pdf_pics, pdf_goals_agg, pdf_prep, output_dir)

pdf_results= (
    pdf_prep.merge(pdf_goals_agg, how="left", on="player_id")
    .merge(pdf_pics, how="left", on="player_id")
    .pipe(adjust_goals)
    .pipe(generate_results, output_dir)
)

logging.info("Results saved to CSV")
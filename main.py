import pandas as pd
import random
from config import (
    data_source,
    manual_renaming_flag,
    player_fill_flag,
    players_to_fill_with,
)
from utils.general_utils import (
    rename_form_columns,
    form_to_long,
    clean_form_data,
    number_of_pics,
    adjust_goals,
    generate_results,
    apply_manual_renames,
    fill_missing_players,
    resolve_duplicates_in_picks,
)
from utils.validation_utils import run_validations
from manual_updates import MANUAL_RENAMES

import logging

logging.basicConfig(level=logging.INFO)
random.seed(42)

logging.info("Started Running")

# Load form, rename columns, convert to long and clean
pdf_form = (
    pd.read_csv(f"data/input/{data_source}/form_response.csv")
    .pipe(rename_form_columns)
    .pipe(form_to_long)
    .pipe(clean_form_data)
)

# Apply manual renames if enabled
if manual_renaming_flag:
    pdf_form = pdf_form.pipe(apply_manual_renames, MANUAL_RENAMES)

# Load reference
pdf_reference = pd.read_csv(f"data/input/{data_source}/player_reference.csv")

# Fill invalid picks with random players if enabled
if player_fill_flag:
    pdf_form = fill_missing_players(pdf_form, pdf_reference, players_to_fill_with)
    pdf_form = resolve_duplicates_in_picks(
        pdf_form, pdf_reference, players_to_fill_with
    )

# Run validations using only the long form

errors, warnings = run_validations(pdf_form, pdf_reference)

# Log and raise if any issues
for w in warnings:
    logging.warning(w)
for e in errors:
    logging.error(e)

if errors or warnings:
    all_msgs = []
    all_msgs += [f"WARNING: {w}" for w in warnings]
    all_msgs += [f"ERROR: {e}" for e in errors]
    raise AssertionError("Validation failures:\n" + "\n".join(all_msgs))

# Prepare merged dataset for downstream processing
pdf_prep = pdf_reference.merge(pdf_form, how="inner", on="full_name")

pdf_pics = number_of_pics(pdf_prep)

pdf_goals = pd.read_csv(
    f"data/input/{data_source}/player_goals/GW_1.csv"
)  # TODO - Generate function for multiple

pdf_combined = (
    pdf_prep.merge(pdf_goals, how="left", on="player_id")
    .merge(pdf_pics, how="left", on="player_id")
    .pipe(adjust_goals)
)

pdf_results = generate_results(pdf_combined)

pdf_results.to_csv(f"data/output/{data_source}/results.csv", index=False)
logging.info("Results saved to CSV")
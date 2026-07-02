import pandas as pd
import random
from config import (
    data_source,
    submission_deadline,
    manual_renaming_flag,
    player_fill_flag,
    players_to_fill_with,
    max_gw,
)
from utils.general_utils import (
    generate_goals,
    rename_form_columns,
    form_to_long,
    clean_form_data,
    filter_form_by_deadline,
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
pdf_form_raw = pd.read_csv(f"data/input/{data_source}/form_response.csv")
pdf_form = (
    pdf_form_raw.pipe(rename_form_columns)
    .pipe(form_to_long)
    .pipe(clean_form_data)
)

pdf_form_before_deadline = pdf_form.pipe(
    filter_form_by_deadline, submission_deadline
)

if len(pdf_form_before_deadline) == 0:
    raise RuntimeError(
        "No form entries remained after applying the submission deadline."
    )

pdf_form = pdf_form_before_deadline

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

# Log warnings and raise only for actual errors
for w in warnings:
    logging.warning(w)
for e in errors:
    logging.error(e)

if errors:
    all_msgs = [f"ERROR: {e}" for e in errors]
    raise AssertionError("Validation failures:\n" + "\n".join(all_msgs))

# Prepare merged dataset for downstream processing
pdf_prep = pdf_reference.merge(pdf_form, how="inner", on="full_name")

pdf_pics = number_of_pics(pdf_prep)

pdf_goals_agg = generate_goals(max_gw, data_source)

pdf_combined = (
    pdf_prep.merge(pdf_goals_agg, how="left", on="player_id")
    .merge(pdf_pics, how="left", on="player_id")
    .pipe(adjust_goals)
)

pdf_results = generate_results(pdf_combined)

pdf_results.to_csv(f"data/output/{data_source}/results.csv", index=False)
logging.info("Results saved to CSV")
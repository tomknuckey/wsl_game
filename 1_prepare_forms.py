import pandas as pd
import random
from config import (
    data_source,
    submission_deadline,
    exclude_name_prefixes_flag,
    exclude_name_prefixes,
    manual_renaming_flag,
    player_fill_flag,
    players_to_fill_with,
)
from utils.general_utils import (
    rename_form_columns,
    form_to_long,
    clean_form_data,
    filter_by_name_prefixes,
    filter_form_by_deadline,
    apply_manual_renames,
    fill_missing_players,
    resolve_duplicates_in_picks,
    load_reference_sheet,
)
from utils.validation_utils import run_validations
from config import MANUAL_RENAMES

import logging
import sys
from pathlib import Path

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

# Optionally exclude submitters by name prefix (e.g. TEMP)
if exclude_name_prefixes_flag:
    pdf_form = pdf_form.pipe(filter_by_name_prefixes, exclude_name_prefixes, exclude_name_prefixes_flag)

pdf_form = pdf_form.pipe(
    filter_form_by_deadline, submission_deadline
)


if len(pdf_form) == 0:
    logging.info(
        "No form entries remained after applying prefix exclusion and/or the submission deadline; exiting."
    )
    sys.exit(0)

# Apply manual renames if enabled
if manual_renaming_flag:
    pdf_form = pdf_form.pipe(apply_manual_renames, MANUAL_RENAMES)

# Load reference
pdf_reference = load_reference_sheet(f"data/input/{data_source}/player_reference.csv")

# Fill invalid picks with random players if enabled
if player_fill_flag:
    pdf_form = fill_missing_players(pdf_form, pdf_reference, players_to_fill_with)
    pdf_form = resolve_duplicates_in_picks(
        pdf_form, pdf_reference, players_to_fill_with
    )


errors, warnings = run_validations(pdf_form, pdf_reference)

# Log warnings and raise only for actual errors
for w in warnings:
    logging.warning(w)
for e in errors:
    logging.error(e)

if errors:
    all_msgs = [f"ERROR: {e}" for e in errors]
    raise AssertionError("Validation failures:\n" + "\n".join(all_msgs))

intermediate_dir = Path(f"data/intermediate/{data_source}")
intermediate_dir.mkdir(parents=True, exist_ok=True)

pdf_form.to_csv(intermediate_dir / "player_pics.csv", index=False)
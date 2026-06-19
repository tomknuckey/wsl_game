import pandas as pd
from config import source
from utils import (
    rename_form_columns,
    form_to_long,
    clean_form_data,
    number_of_pics,
    adjust_goals,
    generate_results,
)

# Load and process form responses
pdf_form = (
    pd.read_csv(f"data/input/{source}/form_response.csv")
    .pipe(rename_form_columns)
    .pipe(form_to_long)
    .pipe(clean_form_data)
)

pdf_reference = pd.read_csv(f"data/input/{source}/player_reference.csv")

pdf_prep = pdf_reference.merge(pdf_form, how="inner", on="full_name")

pdf_pics = number_of_pics(pdf_prep)

pdf_goals = pd.read_csv(
    f"data/input/{source}/player_goals/GW_1.csv"
)  # TODO - Generate function for multiple

pdf_combined= (
    pdf_prep.merge(pdf_goals, how="left", on="player_id")
    .merge(pdf_pics, how="left", on="player_id")
    .pipe(adjust_goals)
)

pdf_results = generate_results(pdf_combined)

pdf_results.to_csv(f"data/output/{source}/results.csv", index=False)

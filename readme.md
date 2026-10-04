## WSL Fantasy Game

The project processes form submissions and weekly player goals into CSV reports, then displays those reports in a read-only Streamlit app.

Live app: <https://wslplayerpics.streamlit.app/>

## Setup

From the repository root in PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run Locally

To display the latest reports already present in `data/output/actual/`:

```powershell
streamlit run app.py
```

To regenerate reports, run the pipeline stages in order:

```powershell
python 1_prepare_forms.py
python 2_output_results.py
```

The first stage reads form responses and player reference data from `data/input/<data_source>/` and writes cleaned picks to `data/intermediate/<data_source>/`. The second stage reads those picks and the weekly goals, then writes reports to `data/output/<data_source>/`.

The selected data source and other pipeline options are in `config.py`; it currently selects `actual`. Check this setting before running the pipeline: generated CSVs in the selected output directory may be replaced.

## Input Data

Each data source has `form_response.csv`, `player_reference.csv`, and a `player_goals/` directory under `data/input/<data_source>/`. Use the stable `player_id` from the reference data to identify players across files.

Add one goals CSV per gameweek under `data/input/<data_source>/player_goals/`, named `GW_<number>.csv` (for example, `GW_5.csv`). The filename supplies the gameweek, so no `week` column is needed. Use `player_id` and an optional `goals` column:

```csv
player_id,goals
WSL_0001,
WSL_0002,2
WSL_0003,3
```

A blank `goals` value, or an omitted `goals` column, counts as one goal. Enter `2`, `3`, or another count only when a player scored multiple goals.

## Project Notes

- [Web app plan](docs/webapp_plan.md): current app status and planned participant-input workflow.
- [Project plan](docs/plan_2026_09_17.md): priorities and outstanding improvements.
- [Copilot project guidance](.github/copilot-instructions.md): concise repository context and working rules.
- [Pipeline guidance](.github/instructions/data-pipeline.instructions.md) and [Streamlit guidance](.github/instructions/streamlit.instructions.md): task-scoped AI instructions.
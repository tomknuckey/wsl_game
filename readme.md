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

## Optional Local Player Descriptions

After running the pipeline, install and start [Ollama](https://ollama.com/) and download the local model once:

```powershell
ollama pull llama3.2:3b
```

After the standard pipeline has updated the weekly results and player ownership, generate ESPN data:

```powershell
python 3_generate_espn_data.py
```

The ESPN script validates all 132 completed 2025-26 WSL match summaries and saves prior-season non-own-goal scorer totals to `data/intermediate/<data_source>/espn_goals.csv`. Open `player_descriptions.ipynb` from the repository root and run its cells. The notebook validates the ESPN frame, player reference, consecutive weekly goal files, and `player_pics.csv`, prepares facts in memory, then generates and validates descriptions with local Ollama. No separate player-description Python script or prepared-facts CSV is needed. Its `MAX_PLAYERS_TO_GENERATE` setting can be set to `10` for a limited run or left as `None` to generate all eligible descriptions. After a successful run it overwrites `data/output/<data_source>/player_descriptions.csv`; a limited run therefore replaces that CSV with only the selected subset. Unknown prior-season totals stay blank. The description output is not loaded by Streamlit.

This only runs when laptop isn't charging

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
- [Player description requirements](docs/player_descriptions_requirements.md): scope for the local weekly description notebook.
- [Copilot project guidance](.github/copilot-instructions.md): concise repository context and working rules.
- [Pipeline guidance](.github/instructions/data-pipeline.instructions.md) and [Streamlit guidance](.github/instructions/streamlit.instructions.md): task-scoped AI instructions.
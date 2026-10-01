### App Website

https://wslgame.streamlit.app/

## Setting up Env

1. python -m venv venv

2. .\venv\Scripts\Activate.ps1

3. pip install -r requirements.txt

### Running App Locally

streamlit run app.py

### Updating Gameweek Goals

Add one CSV per gameweek under `data/input/<data_source>/player_goals/`, named
`GW_<number>.csv` (for example, `GW_5.csv`). The filename supplies the gameweek,
so no `week` column is needed. Use `player_id` and an optional `goals` column:

```csv
player_id,goals
WSL_0001,
WSL_0002,2
WSL_0003,3
```

An empty `goals` value, or an omitted `goals` column, counts as one goal. Enter
`2`, `3`, or another count only for a player who scored multiple goals.
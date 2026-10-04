# Project Guidance

This repository runs a WSL fantasy game data pipeline and a read-only Streamlit results app. Use `readme.md` as the canonical source for setup, commands, paths, and input formats.

## Working rules

- Read the relevant README section and project plan before changing a data contract or behavior. Prefer stable `player_id` values for joins and stored references; names are display/input data.
- Before running pipeline scripts, inspect `config.py` for the selected data source and check which generated CSVs may be overwritten.
- Keep changes focused. Preserve existing CSV schemas unless the task calls for a migration, and update the relevant documentation when a contract changes.
- Add or run focused tests for behavior changes. Do not claim validation that was not performed.

For planned app and transfer work, consult `docs/plan_2026_09_17.md` and `docs/webapp_plan.md`.
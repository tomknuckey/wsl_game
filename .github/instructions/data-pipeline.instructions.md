---
applyTo: "1_prepare_forms.py,2_output_results.py,utils/**/*.py,config.py"
---

# Data Pipeline Guidance

- Follow the pipeline order and input/output paths documented in `readme.md`; it is the canonical source for commands and input formats.
- Use `player_id` as the stable player key. Keep name cleanup, manual renames, exclusions, deadlines, and fill behavior consistent with the options in `config.py`.
- Preserve existing intermediate/output schemas unless the task explicitly changes them. Do not edit generated reports to implement a source-data or scoring change.
- Before executing the pipeline, check `config.data_source` and which output CSVs may be replaced. Prefer focused tests or checks over regenerating actual results when practical.
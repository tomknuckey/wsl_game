# Weekly Player Descriptions - Requirements Draft

**Status:** Implemented in `player_descriptions.ipynb`

## Keep it simple

Choose the simplest approach that meets these requirements. Keep this to one local notebook, the existing CSV inputs, a locally run LLM, and one separate CSV output. Save the output with the selected data source's other reports. Avoid extra services, infrastructure, dependencies, automation, or Streamlit changes unless they are necessary.

## Goal

Use a locally run LLM to produce one short English description for every player in the reference sheet who has scored at least one goal or been selected by at least one manager. Descriptions summarize recorded goal trends and player popularity to help fantasy-game participants understand the data.

Example:

> Started the season well, but has scored less in the last three gameweeks; selected by 4 managers.

## Simple weekly workflow

1. Run the existing data pipeline as usual.
2. Open and run a separate notebook locally. It reads the relevant input CSV files and prepares player statistics for a locally installed LLM.
3. Save the generated descriptions to `data/output/<data_source>/player_descriptions.csv`, overwriting the previous description output on each successful run.
4. Review the output CSV.

The notebook and output CSV are separate from the Streamlit app. Do not upload or integrate the descriptions into Streamlit. No paid or hosted model API is used. Running the model locally avoids per-request charges, though it uses the maintainer's computer, storage, and electricity. The notebook uses Ollama with the local `llama3.2:3b` model; install Ollama and download the model once before running it.

## Data to use

- `data/input/actual/player_reference.csv` supplies the complete player list and stable `player_id` values.
- `data/input/actual/player_goals/GW_<number>.csv` records goals scored in that specific gameweek. Use the completed weekly files to describe season and recent goal trends.
- `data/output/actual/player_pics.csv` contains player-level `num_picks`, the number of managers who selected each player. Use it to describe how many owners a player has.

`manager_ownership.csv` summarizes each manager's overall player ownership statistics; it is not the per-player ownership list. Use `player_pics.csv` for each player's owner count. The pipeline creates this report after processing picks; a reference-sheet player with no row in the completed report has zero owners.

Use `player_id` to join player and goal data. Do not join on names.

## Description requirements

- Include both goal trends and pick popularity when the data supports them.
- Calculate ownership ranks among players with at least one pick and goalscorer ranks among players with at least one goal. Add top-three rank highlights to descriptions; players tied on a count share a competition rank and the description should identify them as joint at that rank. Do not rank zero-pick or zero-goal players.
- Define recent form as the last three completed gameweeks.
- For a player with no recorded goals, say they have not scored yet and include the owner count when available.
- If too little history exists to describe a trend, state the recorded goals and owner count without implying a trend.
- Keep each description to one concise sentence (maximum 30 words), in neutral English.
- Use only the supplied reference, goals, and ownership data. Do not imply appearances, minutes, injuries, availability, fixtures, or other information that is not present.
- Have Python calculate the facts and ranks (including totals, recent goals, and owner counts); the LLM words the goal trends, and Python appends verified owner-count and rank clauses.
- Treat goal records as goals for their named gameweek. Do not infer that a player appeared in a gameweek from having no goal row.

## Output and safeguards

- Write one CSV output at `data/output/<data_source>/player_descriptions.csv`, with exactly one row per eligible reference-sheet `player_id` (at least one recorded goal or one pick), the description, and enough metadata to identify the data source and latest completed gameweek. Exclude players with no recorded goals and no picks. Overwrite this file on each successful run instead of creating additional copies.
- Do not load the description CSV into Streamlit or make app visitors trigger LLM inference.
- Review the generated descriptions in the output CSV.
- Check that all eligible players appear once and that each description is non-empty and within the length limit. Stop with a clear error if inputs or output are incomplete or invalid.
- Do not send participant names, form responses, or other personal data to the model.
- Do not use external network access or a hosted API for inference.

## Out of scope

- Live LLM calls from Streamlit or calls triggered by app visitors.
- Transfer recommendations, predictions, injury/news research, or automatic changes to player picks.
- Additional agents or workflow infrastructure beyond the local notebook and saved output.

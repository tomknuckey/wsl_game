# Player Description Requirements

## Goal

Write a short, natural football description for each player who has scored at least one goal or has been selected by at least one manager. It should read like an informed fantasy-football note, not a report assembled from a fixed template.

The local language model should write the whole description from verified player facts. Keep the entire player-description workflow—fact preparation, prompt construction, generation, validation, and output—in `player_descriptions.ipynb`. Do not add a separate player-description Python script or utility module.

## Example descriptions

These are style examples, not claims about the current season:

> Palmer scored in each of his opening two gameweeks but has since gone six without scoring, following ten goals last season.

> Neto has scored three goals in eight gameweeks, including a brace, already showing strong improvement on last season's five league goals.

> Russo is still waiting for a first goal after six gameweeks, though four managers have picked her.

> With three goals in eight gameweeks and a brace along the way, Neto is giving his five-goal league return last season a serious challenge; four managers own him.

> Ten league goals last season made Palmer a popular pick, but the four managers backing him are still waiting for his first goal this season.

> The second-highest scorer so far, Mead has three goals from eight gameweeks despite not appearing in any manager's picks.

> Hemp has yet to score in six gameweeks after last season's 12-goal return, though seven managers have selected her.

> Russo's four goals make her the second-highest scorer, but no managers have picked her so far.

> With no goals yet this season, Kerr is still a popular choice among six managers after scoring nine league goals last year.

These examples show different ways to balance current-season form, prior-season context, and ownership. Only include each detail when its supporting fact is present, and avoid implying that a zero in the picks data means poor performance or that a prior-season total guarantees current form.

## Style guidance for the prompt

- Ask for one concise, readable sentence in natural English, usually around 15-35 words.
- Vary sentence structure and choose the most interesting supported facts. Avoid repeating a stock opening or following the same clause order for every player.
- Describe the goal story in context: when the player scored, whether goals came in a burst, how long the current dry spell is, and how the current total compares with last season where the data supports that comparison.
- Work the ownership count into the sentence when it adds useful context. Do not force it into every description, and do not describe an unpicked player as owned by zero managers.
- Ownership counts are current-season picks only. Do not attribute them to last season or make claims about historical manager picks; that information is unavailable.
- Avoid goalscoring ranks for players with only one goal; the low rank is not useful context. Ownership wording must agree with the current-season `num_picks` count.
- Use a brace only when a gameweek contains exactly two recorded goals; distinguish it from a gameweek with three or more.
- Do not turn missing goal rows into claims about appearances, minutes, availability, effort, ability, or a full match record.
- Do not claim improvement or decline unless the supplied totals support the comparison. Describe prior-season goals as league goals only where that characterization is appropriate to the source.
- Do not invent fixtures, news, injuries, positions, or other player information. Avoid empty hype, generic football clichés, and awkward phrases added solely to include every statistic.

## Data and workflow

Run the existing results pipeline first so the current season's goals and player ownership report are up to date. Then generate the ESPN scorer data and run the notebook from the repository root:

```powershell
python 3_generate_espn_data.py
```

`3_generate_espn_data.py` fetches and validates ESPN's completed 2025-26 WSL matches, then saves prior-season non-own-goal scorer totals in `data/intermediate/<data_source>/espn_goals.csv`.

Run `player_descriptions.ipynb` for all remaining steps. It reads the player reference, consecutive gameweek goal files, `data/output/<data_source>/player_pics.csv`, and ESPN's intermediate file; validates them, joins by stable `player_id`, and prepares facts in memory. Those facts include current-season goal sequence and totals, goalscoring rank (including ties), scoring and brace gameweeks, the dry spell, ownership count/rank, and matched prior-season total. Unknown ESPN scorers remain unmatched and an absent prior-season total stays unknown, not zero. The notebook sends only individual player facts—not participant or form data—to local Ollama and validates generated descriptions against those facts. It retries validation failures up to three times, passing the validation message back to the model. If a description still fails, generation continues for the remaining players; the final output cell lists each issue and leaves the existing CSV unchanged rather than writing an incomplete file. The notebook overwrites `data/output/<data_source>/player_descriptions.csv` only after every eligible player in the run has a valid description. Set `MAX_PLAYERS_TO_GENERATE` to a positive integer for a limited run or `None` to generate all eligible players. A limited run overwrites the normal output with that subset. Review local model output before sharing.

## Data rules and safeguards

- Use `player_id` for joins. Player names are for display and prompt context, not the join key.
- Keep all player-description source loading, validation, joining, aggregation, fact preparation, prompting, generation, and output in `player_descriptions.ipynb`; do not maintain a second player-description Python implementation.
- Follow the existing weekly goal input rule: a blank or omitted `goals` value means one goal. A missing player row in a gameweek means zero goals recorded for that gameweek, not that the player appeared or did not appear.
- Require gameweek files numbered consecutively from GW 1. Reject missing or duplicate player IDs within a gameweek, unknown player IDs, and invalid goal counts.
- Count `num_picks` in `player_pics.csv` as the number of managers who selected the player this season. A player with no ownership row has zero picks. Historical manager ownership is unknown.
- ESPN totals are based on completed 2025-26 WSL scoring events, excluding own goals. ESPN does not establish a player's zero-goal appearances; a scorer absent from ESPN's events has no matched prior-season total, not a verified zero.
- Do not pass submitter names, form responses, or participant data to the language model. Only individual player facts needed for the description are in scope.
- Keep the description workflow local and separate from Streamlit. App visitors must not trigger model calls.
- Stop with a clear error if input validation fails or any eligible player is missing from the prepared facts or final output. Preserve a clear distinction between unknown prior-season goals and zero.

## Output

Write `data/output/<data_source>/player_descriptions.csv` with one row per eligible `player_id`, including the description, player identity, ownership count, current-season goals, prior-season label and goals, data source, and latest completed gameweek. Keep one output file and overwrite it on each successful run.

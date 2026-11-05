# Player Description Experiment Learnings

## Status

The local Ollama player-description workflow has been retired. The notebook, its test, the generated description output, and its intermediate facts export were removed. ESPN data generation remains available through `3_generate_espn_data.py`; it is independent of description generation and writes prior-season scorer totals to `data/intermediate/<data_source>/espn_goals.csv`.

The current-season player picks files named `player_pics.csv` are still part of the results pipeline and have not been removed. They are not description-specific artifacts.

## What happened

The saved notebook run prepared facts for 95 players. It then rejected seven generated descriptions:

- Four incorrectly claimed a player had no manager picks despite nonzero ownership.
- Three stated a current-season goal total that disagreed with the prepared facts.

The notebook correctly refused to write a partial output, so the existing description CSV was left unchanged. This demonstrates that the model output was not reliably grounded in the supplied facts. A small model and a broad prompt covering many players and many possible facts may have contributed, but the run does not establish model size as the only cause.

## Prompt used

The notebook sent one request per player. It inserted the relevant player's facts as JSON in place of `{PLAYER_FACTS}` and added conditional goal-count, ownership, rank, and scoreless-gameweek checks based on those facts. When a previous response failed validation, it appended the revision instructions shown below.

```text
Write one natural, polished football description of this fantasy-game player using only the facts in the JSON below.

STYLE:
- Aim for 15-35 words, and never exceed 40 words.
- Write a complete natural sentence; do not use a fixed clause template.
- Select only the most useful supported facts and vary the sentence structure.
FACT CHECKS (mandatory; facts override style preferences):
{FACT-SPECIFIC GOAL-COUNT, OWNERSHIP, RANK, AND SCORELESS-GAMEWEEK RULES}
- Ownership counts are current-season picks only; do not attach them to last season or claim historical manager picks, which are unknown. Do not invent or name individual managers.
- FINAL OWNERSHIP AUDIT: if ownership_count is greater than zero, the sentence must not say or imply nobody/no one/no managers picked, selected, owns, or backs the player. If you cannot state the exact pick count confidently, omit ownership entirely.
- FINAL GOAL AUDIT: every current-season goal total or equivalent claim (including no goals, one goal, once, a single goal, braces, or a numeric total) must agree with current_season_goals exactly. Do not derive a total from the gameweek list; if uncertain, omit the total.
- A blank prior-season total means unknown, not zero. Never invent or infer a missing prior-season total.
- The gameweek count is current-season data only. Never state or imply how many gameweeks a prior season lasted.
- A brace means exactly two goals in a gameweek; describe larger tallies accurately.
- A team value gives club affiliation only. It does not establish position, lineup, bench status, starts, appearances, minutes, availability, effort, or ability. Do not claim any of these.
- No fixture, opponent, scoreline, or match result is supplied. Do not mention or infer one.
- The facts contain no pronouns; use the player's name or neutral wording.
- Return exactly one sentence, with no heading or explanation.

PLAYER FACTS (the only source of claims; do not use outside knowledge):
{PLAYER_FACTS}
```

For a response that failed validation, the notebook appended:

```text
REVISION REQUIRED: Your previous description failed validation: {VALIDATION_FEEDBACK}
Rewrite the sentence from the PLAYER FACTS, not from memory or the previous response. For an ownership error, remove the zero-picks claim and use the exact positive ownership_count or omit ownership. For a goal-total error, remove the incorrect total and use current_season_goals exactly, or omit the goal total. Do not repeat or paraphrase the rejected claim.
```

## Data used

The notebook prepared one request per player with at least one recorded current-season goal or at least one current-season pick. It used the configured data source (`actual` in the run documented here) and joined records by stable `player_id`.

Source inputs were:

- `data/input/<data_source>/player_reference.csv`: player ID, display name, and team.
- `data/input/<data_source>/player_goals/GW_<number>.csv`: current-season weekly goal counts, from consecutive gameweek files starting at GW 1. Blank or omitted `goals` values counted as one; a missing player row counted as zero recorded goals for that gameweek.
- `data/output/<data_source>/player_pics.csv`: current-season ownership counts (`num_picks`). Missing player rows were treated as zero picks.
- `data/intermediate/<data_source>/espn_goals.csv`: prior-season 2025-26 WSL scorer totals, excluding own goals, as fetched and matched from ESPN.

The per-player facts sent to the model included name and team; current-season goal total and weekly sequence; scoring, brace, and multi-goal gameweeks; completed gameweek count and gameweeks since the last goal; current-season scorer rank and tie count; ownership count and rank/tie count; and prior-season label and goals when matched. Unknown prior-season totals remained blank/unknown. The prompt did not include form responses or participant/manager names.

## If revisiting the work

1. Keep ESPN data generation separate. If prior-season totals are wanted, check `config.py` and run `python 3_generate_espn_data.py`; this replaces the selected source's `espn_goals.csv`.
2. Build and validate the player facts independently of the LLM. Use stable `player_id` values for joins, and treat unknown prior-season totals as unknown rather than zero.
3. Reduce the model's task: send a small, curated set of facts for one player at a time and request one short sentence. Do not send participant names, form responses, or other manager-identifying data.
4. Start with a small sample, such as five to ten players. Check each description against its source facts, including ownership and goal totals, before attempting a larger run. Compare a stronger model or a narrower prompt rather than assuming a model upgrade alone will solve the issue.
5. Add focused tests for factual validation and failure handling. Keep the existing output untouched unless every eligible player's description passes validation; write the replacement atomically.
6. Review the final CSV manually before sharing. Generated text can still be misleading even when automated checks pass.

The standard data pipeline and input formats are documented in the [README](../readme.md). The ESPN fetch and validation logic is covered by `tests/test_espn_utils.py`.

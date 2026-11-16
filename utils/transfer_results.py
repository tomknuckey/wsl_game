"""Prepare public transfer activity and outcome summaries."""

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone

import pandas as pd

from utils.transfer_utils import (
    TransferRule,
    filter_transfer_records_for_rules,
)


def get_effective_transfers(
    records: Iterable[Mapping[str, str]],
    rules: Iterable[TransferRule],
    season_id: str,
    as_of_utc: datetime | None = None,
) -> list[dict[str, str]]:
    """Return corrected transfers whose configured deadline has passed."""
    now = as_of_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    configured_rules = [
        rule for rule in rules if rule.season_id == season_id
    ]
    rules_by_id = {rule.rule_id: rule for rule in configured_rules}
    announced_rules = [
        rule
        for rule in configured_rules
        if rule.deadline_datetime_utc <= now
    ]
    announced_rule_ids = {rule.rule_id for rule in announced_rules}
    announced_records = []
    for source_record in records:
        record = dict(source_record)
        rule = rules_by_id.get(record["rule_id"])
        if rule is None and record["season_id"] == "legacy":
            matching_rules = [
                configured_rule
                for configured_rule in configured_rules
                if configured_rule.gameweek == int(record["effective_gameweek"])
            ]
            if len(matching_rules) == 1:
                rule = matching_rules[0]
        if rule is not None and rule.rule_id in announced_rule_ids:
            announced_records.append(record)

    eligible_records = filter_transfer_records_for_rules(
        announced_records,
        announced_rules,
    )
    season_records = [
        dict(record)
        for record in eligible_records
        if record["season_id"] in {season_id, "legacy"}
    ]
    latest_corrections: dict[str, dict[str, str]] = {}
    for record in season_records:
        transfer_id = record["correction_of_transfer_id"]
        if record["action_type"] != "correction" or not transfer_id:
            continue
        prior_correction = latest_corrections.get(transfer_id)
        if prior_correction is None or record["submitted_at_utc"] > prior_correction[
            "submitted_at_utc"
        ]:
            latest_corrections[transfer_id] = record

    effective_transfers = []
    for record in season_records:
        if record["action_type"] != "transfer":
            continue
        try:
            effective_gameweek = int(record["effective_gameweek"])
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Transfer ledger contains an invalid effective gameweek."
            ) from error
        if effective_gameweek < 1:
            raise ValueError(
                "Transfer ledger contains an invalid effective gameweek."
            )
        effective = dict(record)
        correction = latest_corrections.get(record["transfer_id"])
        if correction is not None:
            for field in (
                "player_out_id",
                "player_out_name",
                "player_in_id",
                "player_in_name",
                "player_in_club",
            ):
                effective[field] = correction[field]
        effective_transfers.append(effective)

    return effective_transfers


def build_transfer_outcomes(
    transfers: Iterable[Mapping[str, str]],
    weekly_goals: pd.DataFrame,
) -> list[dict[str, object]]:
    """Calculate net goals for each transfer using available post-transfer weeks."""
    required_columns = {"player_id", "gameweek", "goals"}
    if not required_columns.issubset(weekly_goals.columns):
        weekly_goals = pd.DataFrame(columns=["player_id", "gameweek", "goals"])

    goal_data = weekly_goals.copy()
    if not goal_data.empty:
        goal_data["player_id"] = goal_data["player_id"].astype(str).str.strip()
        goal_data["gameweek"] = pd.to_numeric(
            goal_data["gameweek"], errors="coerce"
        )
        goal_data["goals"] = pd.to_numeric(goal_data["goals"], errors="coerce").fillna(0)

    outcomes = []
    for transfer in transfers:
        effective_gameweek = int(transfer["effective_gameweek"])
        post_transfer_goals = goal_data.loc[
            goal_data["gameweek"] >= effective_gameweek
        ]
        incoming_goals = None
        outgoing_goals = None
        net_goals = None
        if not post_transfer_goals.empty:
            goals_by_player = post_transfer_goals.groupby("player_id")["goals"].sum()
            incoming_goals = float(goals_by_player.get(transfer["player_in_id"], 0))
            outgoing_goals = float(goals_by_player.get(transfer["player_out_id"], 0))
            net_goals = incoming_goals - outgoing_goals
        outcomes.append(
            {
                **dict(transfer),
                "incoming_goals": incoming_goals,
                "outgoing_goals": outgoing_goals,
                "net_goals": net_goals,
            }
        )
    return outcomes

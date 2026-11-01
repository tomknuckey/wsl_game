"""Utilities for retrieving and validating prior-season WSL goals from ESPN."""

import concurrent.futures
import json
import logging
import re
import unicodedata
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

import pandas as pd

LAST_SEASON = "2025-26"
LAST_SEASON_ESPN_YEAR = 2025
LAST_SEASON_CALENDAR_YEARS = (2025, 2026)
EXPECTED_LAST_SEASON_MATCHES = 132
ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.w.1/"
    "scoreboard?dates={calendar_year}&limit=1000"
)
ESPN_SUMMARY_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.w.1/"
    "summary?event={event_id}"
)
JsonFetcher = Callable[[str, str], dict[str, Any]]


def normalize_player_name(name: Any) -> str:
    """Normalize names for matching ESPN scorer names to the player reference."""
    normalized = unicodedata.normalize("NFKD", str(name).casefold())
    without_accents = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return " ".join(re.sub(r"[^a-z0-9]+", " ", without_accents).split())


def _fetch_espn_json(url: str, purpose: str) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as error:
        raise RuntimeError(f"Could not retrieve ESPN {purpose}.") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"ESPN returned invalid {purpose} data.") from error
    if not isinstance(payload, dict):
        raise ValueError(f"ESPN returned invalid {purpose} data.")
    return payload


def _get_season_events(fetch_json: JsonFetcher) -> dict[str, dict[str, Any]]:
    events_by_id: dict[str, dict[str, Any]] = {}
    for calendar_year in LAST_SEASON_CALENDAR_YEARS:
        scoreboard = fetch_json(
            ESPN_SCOREBOARD_URL.format(calendar_year=calendar_year),
            f"the {LAST_SEASON} WSL schedule",
        )
        events = scoreboard.get("events")
        if not isinstance(events, list):
            raise ValueError("ESPN returned an invalid prior-season WSL schedule.")
        for event in events:
            if not isinstance(event, dict) or not isinstance(event.get("season"), dict):
                raise ValueError(
                    "ESPN returned an invalid event in the prior-season WSL schedule."
                )
            try:
                event_season = int(event["season"]["year"])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(
                    "ESPN returned an event without a valid season year."
                ) from error
            if event_season != LAST_SEASON_ESPN_YEAR:
                continue
            event_id = str(event.get("id", "")).strip()
            if not event_id or event_id in events_by_id:
                raise ValueError(
                    "ESPN returned an empty or duplicate prior-season event ID."
                )
            events_by_id[event_id] = event

    if len(events_by_id) != EXPECTED_LAST_SEASON_MATCHES:
        raise ValueError(
            f"ESPN returned {len(events_by_id)} prior-season matches; "
            f"expected {EXPECTED_LAST_SEASON_MATCHES}."
        )
    for event_id, event in events_by_id.items():
        try:
            is_complete = event["competitions"][0]["status"]["type"]["completed"]
        except (IndexError, KeyError, TypeError) as error:
            raise ValueError(
                f"ESPN returned an invalid status for match {event_id}."
            ) from error
        if is_complete is not True:
            raise ValueError(
                f"ESPN reports prior-season match {event_id} as incomplete."
            )
    return events_by_id


def _parse_match_goal_totals(
    event_id: str, summary: dict[str, Any]
) -> tuple[int, int, dict[str, int]]:
    try:
        header = summary["header"]
        summary_event_id = str(header["id"])
        match = header["competitions"][0]
        team_scores = [int(team["score"]) for team in match["competitors"]]
        key_events = summary["keyEvents"]
    except (IndexError, KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"ESPN returned an incomplete summary for match {event_id}."
        ) from error
    if summary_event_id != event_id:
        raise ValueError(f"ESPN returned the wrong match summary for event {event_id}.")
    if len(team_scores) != 2 or any(score < 0 for score in team_scores):
        raise ValueError(f"ESPN returned invalid final scores for match {event_id}.")
    if not isinstance(key_events, list) or not all(
        isinstance(play, dict) for play in key_events
    ):
        raise ValueError(f"ESPN returned invalid goal events for match {event_id}.")
    goal_events = [
        play
        for play in key_events
        if play.get("scoringPlay") is True and play.get("shootout") is not True
    ]
    if len(goal_events) != sum(team_scores):
        raise ValueError(
            f"ESPN goal events do not match the final score for match {event_id}."
        )

    player_goals: dict[str, int] = {}
    for goal in goal_events:
        event_type_data = goal.get("type", {})
        if not isinstance(event_type_data, dict):
            raise ValueError(f"ESPN returned an invalid goal type in match {event_id}.")
        event_type = event_type_data.get("text", "")
        if not isinstance(event_type, str):
            raise ValueError(f"ESPN returned an invalid goal type in match {event_id}.")
        if "own goal" in event_type.casefold():
            continue
        try:
            scorer_name = goal["participants"][0]["athlete"]["displayName"]
        except (IndexError, KeyError, TypeError) as error:
            raise ValueError(
                f"ESPN omitted the scorer for a goal in match {event_id}."
            ) from error
        if not isinstance(scorer_name, str) or not normalize_player_name(scorer_name):
            raise ValueError(
                f"ESPN returned an invalid scorer name in match {event_id}."
            )
        normalized_name = normalize_player_name(scorer_name)
        player_goals[normalized_name] = player_goals.get(normalized_name, 0) + 1
    return sum(team_scores), len(goal_events), player_goals


def _fetch_match_goal_totals(
    event_id: str, fetch_json: JsonFetcher
) -> tuple[int, int, dict[str, int]]:
    summary = fetch_json(
        ESPN_SUMMARY_URL.format(event_id=event_id),
        f"the prior-season WSL summary for match {event_id}",
    )
    return _parse_match_goal_totals(event_id, summary)


def generate_espn_goal_frame(reference: pd.DataFrame) -> pd.DataFrame:
    """Fetch all completed 2025-26 WSL matches and aggregate non-own-goal scorers."""
    required_reference_columns = {"player_id", "full_name"}
    if not required_reference_columns.issubset(reference.columns):
        raise ValueError(
            "The player reference must contain player_id and full_name columns."
        )
    reference_players = reference[["player_id", "full_name"]].copy()
    reference_players["player_id"] = (
        reference_players["player_id"].astype("string").str.strip()
    )
    reference_players["full_name"] = (
        reference_players["full_name"].astype("string").str.strip()
    )
    if (
        reference_players["player_id"].isna().any()
        or reference_players["player_id"].eq("").any()
        or reference_players["full_name"].isna().any()
        or reference_players["full_name"].eq("").any()
    ):
        raise ValueError(
            "The player reference contains an empty player_id or full_name."
        )
    if reference_players["player_id"].duplicated().any():
        raise ValueError("The player reference contains duplicate player_id values.")
    reference_players["normalized_name"] = reference_players["full_name"].map(
        normalize_player_name
    )
    if reference_players["normalized_name"].duplicated().any():
        raise ValueError(
            "The player reference contains names that collide after normalization."
        )
    player_id_by_name = dict(
        zip(reference_players["normalized_name"], reference_players["player_id"])
    )

    events_by_id = _get_season_events(_fetch_espn_json)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        match_totals = list(
            executor.map(
                lambda event_id: _fetch_match_goal_totals(event_id, _fetch_espn_json),
                events_by_id,
            )
        )

    score_total = sum(match[0] for match in match_totals)
    goal_event_total = sum(match[1] for match in match_totals)
    if goal_event_total != score_total:
        raise ValueError(
            "ESPN's prior-season goal events do not match the completed match scores."
        )

    goals_by_name: dict[str, int] = {}
    for _, _, match_player_goals in match_totals:
        for normalized_name, goals_scored in match_player_goals.items():
            goals_by_name[normalized_name] = (
                goals_by_name.get(normalized_name, 0) + goals_scored
            )
    if not goals_by_name:
        raise ValueError("ESPN's prior-season goal events contain no valid scorers.")

    frame = pd.DataFrame(
        [
            {
                "season": LAST_SEASON,
                "player_id": player_id_by_name.get(normalized_name, pd.NA),
                "normalized_name": normalized_name,
                "last_season_goals": goals,
            }
            for normalized_name, goals in goals_by_name.items()
        ]
    )
    if frame["normalized_name"].duplicated().any():
        raise ValueError(
            "ESPN's prior-season goal events contain duplicate player names."
        )
    if (frame["last_season_goals"] <= 0).any():
        raise ValueError(
            "ESPN's prior-season goal events contain an invalid goals value."
        )
    matched_player_ids = frame["player_id"].dropna()
    if matched_player_ids.duplicated().any():
        raise ValueError(
            "ESPN's prior-season goal events map to duplicate reference player IDs."
        )

    logging.info(
        "Validated %s completed ESPN matches and %s match goal events; "
        "aggregated non-own-goal scorers for %s players.",
        len(match_totals),
        goal_event_total,
        len(frame),
    )
    return frame

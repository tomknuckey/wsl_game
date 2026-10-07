import csv
import os
import tempfile
import threading
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path


TRANSFER_FIELDS = (
    "team_name",
    "player_out_id",
    "player_out_name",
    "player_in_id",
    "player_in_name",
    "player_in_club",
    "submitted_at_utc",
)
_TRANSFER_LOCK = threading.Lock()


def normalise_team_name(team_name: str) -> str:
    return " ".join(team_name.split()).casefold()


def load_transfer_records(path: str | Path) -> list[dict[str, str]]:
    transfer_path = Path(path)
    if not transfer_path.exists():
        return []

    with transfer_path.open("r", newline="", encoding="utf-8-sig") as transfer_file:
        reader = csv.DictReader(transfer_file)
        if reader.fieldnames is None or not set(TRANSFER_FIELDS).issubset(reader.fieldnames):
            raise ValueError("Transfer ledger has an invalid header.")

        records = [dict(row) for row in reader]

    seen_teams: set[str] = set()
    for record in records:
        normalized_team = normalise_team_name(record["team_name"])
        if not normalized_team:
            raise ValueError("Transfer ledger contains a blank team name.")
        if normalized_team in seen_teams:
            raise ValueError("Transfer ledger contains more than one transfer for a team.")
        if not record["player_out_id"] or not record["player_in_id"]:
            raise ValueError("Transfer ledger contains a missing player ID.")
        if record["player_out_id"] == record["player_in_id"]:
            raise ValueError("A transfer must exchange two different players.")
        seen_teams.add(normalized_team)

    return records


def get_team_transfer(
    records: Iterable[Mapping[str, str]], team_name: str
) -> dict[str, str] | None:
    normalized_team = normalise_team_name(team_name)
    return next(
        (
            dict(record)
            for record in records
            if normalise_team_name(record["team_name"]) == normalized_team
        ),
        None,
    )


def record_transfer(
    path: str | Path,
    *,
    team_name: str,
    current_player_ids: Iterable[str],
    player_out_id: str,
    player_out_name: str,
    player_in_id: str,
    player_in_name: str,
    player_in_club: str,
) -> dict[str, str]:
    normalized_team = normalise_team_name(team_name)
    if not normalized_team:
        raise ValueError("Team name cannot be blank.")

    roster_ids = [str(player_id) for player_id in current_player_ids]
    if not roster_ids or any(not player_id for player_id in roster_ids):
        raise ValueError("The current roster has missing player IDs.")
    if len(roster_ids) != len(set(roster_ids)):
        raise ValueError("The current roster contains duplicate players.")
    if player_out_id not in roster_ids:
        raise ValueError("The outgoing player is not on this team's roster.")
    if player_in_id in roster_ids:
        raise ValueError("The incoming player is already on this team's roster.")
    if not player_in_id or player_in_id == player_out_id:
        raise ValueError("Choose a different incoming player.")

    new_roster_ids = [
        player_in_id if player_id == player_out_id else player_id
        for player_id in roster_ids
    ]
    if len(new_roster_ids) != len(roster_ids) or len(new_roster_ids) != len(set(new_roster_ids)):
        raise ValueError("The transfer would create a duplicate player or change roster size.")

    record = {
        "team_name": team_name,
        "player_out_id": player_out_id,
        "player_out_name": player_out_name,
        "player_in_id": player_in_id,
        "player_in_name": player_in_name,
        "player_in_club": player_in_club,
        "submitted_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    transfer_path = Path(path)

    with _TRANSFER_LOCK:
        existing_records = load_transfer_records(transfer_path)
        if get_team_transfer(existing_records, team_name) is not None:
            raise ValueError("This team has already used its one transfer.")

        transfer_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                newline="",
                encoding="utf-8",
                dir=transfer_path.parent,
                delete=False,
            ) as temporary_file:
                temporary_path = temporary_file.name
                writer = csv.DictWriter(temporary_file, fieldnames=TRANSFER_FIELDS)
                writer.writeheader()
                writer.writerows(existing_records)
                writer.writerow(record)

            os.replace(temporary_path, transfer_path)
        finally:
            if temporary_path is not None and os.path.exists(temporary_path):
                os.unlink(temporary_path)

    return record
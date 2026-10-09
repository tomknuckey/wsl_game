import csv
import os
import tempfile
import threading
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class TransferRule:
    """A transfer allowance for one season and effective gameweek."""

    season_id: str
    gameweek: int
    deadline_utc: str | datetime
    max_transfers_per_team: int
    start_utc: str | datetime | None = None

    def __post_init__(self) -> None:
        if not str(self.season_id).strip():
            raise ValueError("Transfer rule season ID cannot be blank.")
        if isinstance(self.gameweek, bool) or not isinstance(self.gameweek, int) or self.gameweek < 1:
            raise ValueError("Transfer rule gameweek must be a positive integer.")
        if isinstance(self.max_transfers_per_team, bool) or not isinstance(
            self.max_transfers_per_team, int
        ) or self.max_transfers_per_team < 1:
            raise ValueError("Transfer rule maximum must be a positive integer.")
        if self.start_datetime_utc >= self._parse_utc_datetime(self.deadline_utc):
            raise ValueError("Transfer rule start must be before its deadline.")

    @staticmethod
    def _parse_utc_datetime(value: str | datetime) -> datetime:
        if isinstance(value, datetime):
            deadline = value
        else:
            deadline = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        return deadline.astimezone(timezone.utc)

    @property
    def start_datetime_utc(self) -> datetime:
        if self.start_utc is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        return self._parse_utc_datetime(self.start_utc)

    @property
    def deadline_datetime_utc(self) -> datetime:
        return self._parse_utc_datetime(self.deadline_utc)

    @property
    def rule_id(self) -> str:
        return f"{self.season_id}-GW{self.gameweek}"

    def has_started(self, submitted_at: datetime | None = None) -> bool:
        submitted_at = submitted_at or datetime.now(timezone.utc)
        return self.start_datetime_utc <= self._parse_utc_datetime(submitted_at)

    def is_open(self, submitted_at: datetime | None = None) -> bool:
        submitted_at = submitted_at or datetime.now(timezone.utc)
        submitted_at = self._parse_utc_datetime(submitted_at)
        return self.start_datetime_utc <= submitted_at < self.deadline_datetime_utc


def format_utc_datetime(value: str | datetime) -> str:
    """Format a transfer-rule timestamp for participant-facing display."""
    timestamp = TransferRule._parse_utc_datetime(value)
    return (
        f"{timestamp:%A}, {timestamp.day} {timestamp:%B %Y} "
        f"at {timestamp:%H:%M} UTC"
    )


def transfer_rules_from_config(
    configured_rules: Iterable[Mapping[str, object]],
) -> list[TransferRule]:
    """Build validated transfer rules from config dictionaries."""
    return [
        TransferRule(
            season_id=str(rule["season_id"]),
            gameweek=int(rule["gameweek"]),
            start_utc=str(rule["start_utc"]),
            deadline_utc=str(rule["deadline_utc"]),
            max_transfers_per_team=int(rule["max_transfers_per_team"]),
        )
        for rule in configured_rules
    ]


def filter_transfer_records_for_rules(
    records: Iterable[Mapping[str, str]],
    rules: Iterable[TransferRule],
) -> list[dict[str, str]]:
    """Exclude transfers submitted before the start of their configured rule."""
    configured_rules = list(rules)
    rules_by_id = {rule.rule_id: rule for rule in configured_rules}
    eligible_transfers: list[dict[str, str]] = []
    eligible_transfer_ids: set[str] = set()
    corrections: list[dict[str, str]] = []
    other_records: list[dict[str, str]] = []

    for source_record in records:
        record = dict(source_record)
        rule = rules_by_id.get(record["rule_id"])
        if rule is None and record["season_id"] == "legacy":
            legacy_candidates = [
                configured_rule
                for configured_rule in configured_rules
                if configured_rule.gameweek == int(record["effective_gameweek"])
            ]
            if len(legacy_candidates) == 1:
                rule = legacy_candidates[0]
        submitted_at = TransferRule._parse_utc_datetime(record["submitted_at_utc"])
        if rule is not None and not rule.is_open(submitted_at):
            continue

        if record["action_type"] == "transfer":
            eligible_transfers.append(record)
            if record["transfer_id"]:
                eligible_transfer_ids.add(record["transfer_id"])
        elif record["action_type"] == "correction":
            corrections.append(record)
        else:
            other_records.append(record)

    eligible_corrections = [
        correction
        for correction in corrections
        if correction["correction_of_transfer_id"] in eligible_transfer_ids
    ]
    return eligible_transfers + eligible_corrections + other_records


TRANSFER_FIELDS = (
    "team_name",
    "season_id",
    "rule_id",
    "transfer_id",
    "player_out_id",
    "player_out_name",
    "player_in_id",
    "player_in_name",
    "player_in_club",
    "effective_gameweek",
    "submitted_at_utc",
    "action_type",
    "correction_of_transfer_id",
    "correction_reason",
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
        required_fields = {
            "team_name",
            "player_out_id",
            "player_out_name",
            "player_in_id",
            "player_in_name",
            "player_in_club",
            "submitted_at_utc",
        }
        if reader.fieldnames is None or not required_fields.issubset(reader.fieldnames):
            raise ValueError("Transfer ledger has an invalid header.")

        records = [dict(row) for row in reader]

    for record in records:
        record.setdefault("season_id", "legacy")
        record.setdefault("rule_id", "legacy")
        record.setdefault("transfer_id", "")
        record.setdefault("effective_gameweek", "10")
        record.setdefault("action_type", "transfer")
        record.setdefault("correction_of_transfer_id", "")
        record.setdefault("correction_reason", "")
        normalized_team = normalise_team_name(record["team_name"])
        if not normalized_team:
            raise ValueError("Transfer ledger contains a blank team name.")
        if not record["player_out_id"] or not record["player_in_id"]:
            raise ValueError("Transfer ledger contains a missing player ID.")
        if record["player_out_id"] == record["player_in_id"]:
            raise ValueError("A transfer must exchange two different players.")
        if record["action_type"] not in {"transfer", "correction"}:
            raise ValueError("Transfer ledger contains an invalid action type.")

    return records

def _write_transfer_records(
    path: str | Path, records: list[dict[str, str]]
) -> None:
    transfer_path = Path(path)
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
            writer.writerows(records)
        os.replace(temporary_path, transfer_path)
    finally:
        if temporary_path is not None and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def record_correction(
    path: str | Path,
    *,
    team_name: str,
    current_player_ids: Iterable[str],
    player_out_id: str,
    player_out_name: str,
    player_in_id: str,
    player_in_name: str,
    player_in_club: str,
    correction_of_transfer_id: str,
    correction_reason: str,
    effective_gameweek: int = 10,
    rule: TransferRule | None = None,
) -> dict[str, str]:
    """Record a correction while preserving the original transfer as an audit row."""
    if not correction_of_transfer_id:
        raise ValueError("A correction must reference the original transfer.")
    if not correction_reason.strip():
        raise ValueError("A correction must include a reason.")

    roster_ids = [str(player_id) for player_id in current_player_ids]
    if not roster_ids or len(roster_ids) != len(set(roster_ids)):
        raise ValueError("The current roster is missing or duplicated.")
    if player_out_id not in roster_ids:
        raise ValueError("The outgoing player is not on the pre-transfer roster.")
    if player_in_id in roster_ids or player_in_id == player_out_id:
        raise ValueError("The incoming player must be different and not already on the roster.")

    transfer_path = Path(path)
    with _TRANSFER_LOCK:
        existing_records = load_transfer_records(transfer_path)
        original_transfer = next(
            (
                record
                for record in existing_records
                if record["transfer_id"] == correction_of_transfer_id
                or record["submitted_at_utc"] == correction_of_transfer_id
            ),
            None,
        )
        if original_transfer is None or original_transfer["action_type"] != "transfer":
            raise ValueError("The referenced transfer does not exist.")

        rule = rule or TransferRule(
            season_id="legacy",
            gameweek=effective_gameweek,
            deadline_utc=datetime.max.replace(tzinfo=timezone.utc),
            max_transfers_per_team=1,
        )
        submitted_at = datetime.now(timezone.utc)
        if not rule.is_open(submitted_at):
            raise ValueError("The transfer window is not open.")
        record = {
            "team_name": team_name,
            "season_id": rule.season_id,
            "rule_id": rule.rule_id,
            "transfer_id": str(uuid.uuid4()),
            "player_out_id": player_out_id,
            "player_out_name": player_out_name,
            "player_in_id": player_in_id,
            "player_in_name": player_in_name,
            "player_in_club": player_in_club,
            "effective_gameweek": str(effective_gameweek),
            "submitted_at_utc": submitted_at.isoformat(timespec="seconds"),
            "action_type": "correction",
            "correction_of_transfer_id": original_transfer["transfer_id"],
            "correction_reason": correction_reason.strip(),
        }
        _write_transfer_records(transfer_path, existing_records + [record])

    return record

def get_team_transfer(
    records: Iterable[Mapping[str, str]], team_name: str
) -> dict[str, str] | None:
    normalized_team = normalise_team_name(team_name)
    team_records = [
        dict(record)
        for record in records
        if normalise_team_name(record["team_name"]) == normalized_team
        and record["action_type"] == "transfer"
    ]
    if not team_records:
        return None

    return max(team_records, key=lambda record: record["submitted_at_utc"])


def get_active_team_transfer(
    records: Iterable[Mapping[str, str]], team_name: str
) -> dict[str, str] | None:
    normalized_team = normalise_team_name(team_name)
    team_records = [
        dict(record)
        for record in records
        if normalise_team_name(record["team_name"]) == normalized_team
    ]
    transfers = [
        record for record in team_records if record["action_type"] == "transfer"
    ]
    if not transfers:
        return None

    active_transfer = max(transfers, key=lambda record: record["submitted_at_utc"])
    corrections = [
        record
        for record in team_records
        if record["action_type"] == "correction"
        and record["correction_of_transfer_id"] == active_transfer["transfer_id"]
    ]
    if corrections:
        latest_correction = max(
            corrections,
            key=lambda record: record["submitted_at_utc"],
        )
        for field in (
            "player_out_id",
            "player_out_name",
            "player_in_id",
            "player_in_name",
            "player_in_club",
        ):
            active_transfer[field] = latest_correction[field]
    return active_transfer


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
    effective_gameweek: int = 10,
    max_transfers: int = 1,
    rule: TransferRule | None = None,
    season_id: str = "legacy",
) -> dict[str, str]:
    normalized_team = normalise_team_name(team_name)
    if not normalized_team:
        raise ValueError("Team name cannot be blank.")
    if not isinstance(effective_gameweek, int) or isinstance(effective_gameweek, bool) or effective_gameweek < 1:
        raise ValueError("Effective gameweek must be a positive integer.")
    if not isinstance(max_transfers, int) or isinstance(max_transfers, bool) or max_transfers < 1:
        raise ValueError("Maximum transfers must be a positive integer.")

    rule = rule or TransferRule(
        season_id=season_id,
        gameweek=effective_gameweek,
        deadline_utc=datetime.max.replace(tzinfo=timezone.utc),
        max_transfers_per_team=max_transfers,
    )
    if rule.season_id != season_id and season_id != "legacy":
        raise ValueError("The transfer rule and season ID must match.")
    if rule.gameweek != effective_gameweek:
        raise ValueError("The transfer rule gameweek must match the effective gameweek.")

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

    submitted_at = datetime.now(timezone.utc)
    if not rule.is_open(submitted_at):
        raise ValueError("The transfer window is not open.")

    record = {
        "team_name": team_name,
        "season_id": rule.season_id,
        "rule_id": rule.rule_id,
        "transfer_id": str(uuid.uuid4()),
        "player_out_id": player_out_id,
        "player_out_name": player_out_name,
        "player_in_id": player_in_id,
        "player_in_name": player_in_name,
        "player_in_club": player_in_club,
        "effective_gameweek": str(effective_gameweek),
        "submitted_at_utc": submitted_at.isoformat(timespec="seconds"),
        "action_type": "transfer",
        "correction_of_transfer_id": "",
        "correction_reason": "",
    }
    transfer_path = Path(path)

    with _TRANSFER_LOCK:
        existing_records = load_transfer_records(transfer_path)
        prior_transfer_count = sum(
            1
            for existing_record in existing_records
            if normalise_team_name(existing_record["team_name"]) == normalized_team
            and existing_record["season_id"] == rule.season_id
            and existing_record["action_type"] == "transfer"
            and rule.is_open(
                TransferRule._parse_utc_datetime(
                    existing_record["submitted_at_utc"]
                )
            )
        )
        if prior_transfer_count >= rule.max_transfers_per_team:
            raise ValueError(
                f"This team has used all {rule.max_transfers_per_team} transfers "
                f"for {rule.season_id}."
            )
        _write_transfer_records(transfer_path, existing_records + [record])

    return record
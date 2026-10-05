import csv
import hmac
import re
from collections.abc import Mapping
from pathlib import Path


ACCESS_CODE_PATTERN = re.compile(r"\d{4}\Z")


def normalise_team_name(team_name: str) -> str:
    return " ".join(team_name.split()).casefold()


def validate_access_codes(access_codes: Mapping[str, str]) -> dict[str, tuple[str, str]]:
    validated: dict[str, tuple[str, str]] = {}
    seen_codes: set[str] = set()

    for team_name, access_code in access_codes.items():
        normalized_name = normalise_team_name(str(team_name))
        code = str(access_code)
        if not normalized_name:
            raise ValueError("Team names in the access-code mapping cannot be blank.")
        if normalized_name in validated:
            raise ValueError(f"Duplicate team name in access-code mapping: {team_name}")
        if ACCESS_CODE_PATTERN.fullmatch(code) is None:
            raise ValueError(f"Access code for {team_name} must contain exactly four digits.")
        if code in seen_codes:
            raise ValueError("Each team must have a distinct access code.")

        validated[normalized_name] = (str(team_name), code)
        seen_codes.add(code)

    return validated


def authenticate_team(
    team_name: str,
    access_code: str,
    access_codes: Mapping[str, str],
) -> str | None:
    """Return the canonical team name only when its assigned code matches."""
    team_entry = validate_access_codes(access_codes).get(normalise_team_name(team_name))
    if team_entry is None or ACCESS_CODE_PATTERN.fullmatch(access_code) is None:
        return None

    canonical_name, expected_code = team_entry
    if hmac.compare_digest(expected_code, access_code):
        return canonical_name
    return None


def load_team_access_codes(
    local_csv_path: str | Path = "data/team_access_codes.csv",
    secrets_mapping: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Load private Streamlit secrets, or the local operator spreadsheet."""
    if secrets_mapping:
        access_codes = {str(team): str(code) for team, code in secrets_mapping.items()}
    else:
        path = Path(local_csv_path)
        if not path.is_file():
            raise FileNotFoundError("Team access codes are not configured.")

        with path.open("r", newline="", encoding="utf-8-sig") as code_file:
            rows = csv.DictReader(code_file)
            if rows.fieldnames is None or not {"team_name", "access_code"}.issubset(rows.fieldnames):
                raise ValueError("Access-code spreadsheet must have team_name and access_code columns.")
            access_codes = {
                str(row["team_name"]): str(row["access_code"])
                for row in rows
            }

    validate_access_codes(access_codes)
    return access_codes
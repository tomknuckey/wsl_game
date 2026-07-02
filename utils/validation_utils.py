import pandas as pd
from typing import List, Tuple
from utils.general_utils import _safe_str, form_to_long, clean_form_data


def validate_form_responses(pdf_long: pd.DataFrame) -> Tuple[List[str], List[str]]:
    """Validate long-form response data for required picks and duplicates.

    Args:
        pdf_long: Long-form DataFrame containing columns such as
            ``name``, ``team_name``, ``pick_slot``, and ``full_name``.

    Returns:
        A tuple with ``errors`` and ``warnings`` lists.

    Errors are appended for missing pick counts and duplicate player picks
    within the same submitter. Warnings are emitted for duplicate submissions
    and duplicate team names across submitters.
    """
    errors: List[str] = []
    warnings: List[str] = []

    # Ensure required columns exist
    required = {"name", "pick_slot", "full_name"}
    if not required.issubset(set(pdf_long.columns)):
        errors.append(
            f"Form long data missing required columns: {required - set(pdf_long.columns)}"
        )
        return errors, warnings

    # Per-submission checks: count non-empty picks and check duplicates
    grouped = pdf_long.copy()
    grouped["full_name_clean"] = grouped["full_name"].apply(lambda v: _safe_str(v, ""))
    submitters = grouped.groupby("name")
    for submitter, df in submitters:
        picks = df["full_name_clean"].loc[lambda s: s != ""].tolist()
        if len(picks) != 5:
            warnings.append(f"{submitter} has {len(picks)} picks (expected 5)")
            errors.append(f"{submitter} missing picks: expected 5, found {len(picks)}")
        dupes = sorted({p for p in picks if picks.count(p) > 1})
        if dupes:
            errors.append(f"{submitter} duplicate picks: {', '.join(dupes)}")

        submission_count = df[["name", "timestamp"]].drop_duplicates().shape[0]
        if submission_count > 1:
            warnings.append(
                f"{submitter} has multiple submitter entries; using the latest entry before the deadline"
            )

    # Duplicate team names - warn but do not fail the pipeline
    if "team_name" in pdf_long.columns:
        submitter_teams = (
            pdf_long.groupby("name")["team_name"]
            .apply(lambda x: x.iloc[0] if len(x) > 0 else None)
            .reset_index()
        )
        submitter_teams["team_name_clean"] = submitter_teams["team_name"].apply(
            lambda v: _safe_str(v, "")
        )
        non_empty_teams = submitter_teams[
            submitter_teams["team_name_clean"] != ""
        ]["team_name_clean"]
        team_counts = non_empty_teams.value_counts()
        dup_teams = team_counts[team_counts > 1].index.tolist()
        if dup_teams:
            warnings.append(
                f"Duplicate team names across submitters: {', '.join(sorted(dup_teams))}"
            )

    return errors, warnings


def validate_reference_unique_names(pdf_reference: pd.DataFrame) -> List[str]:
    """Validate that the reference sheet contains unique player names.

    Args:
        pdf_reference: DataFrame that should contain a ``full_name`` column.

    Returns:
        A list of error messages for duplicated reference names.
    """
    errors: List[str] = []
    if "full_name" not in pdf_reference.columns:
        errors.append("Reference is missing 'full_name' column")
        return errors

    counts = pdf_reference["full_name"].astype(str).str.strip().value_counts()
    dup = counts[counts > 1]
    for name, cnt in dup.items():
        errors.append(f"Duplicate reference name: '{name}' appears {cnt} times")
    return errors


def validate_reference_sheet(pdf_reference: pd.DataFrame) -> List[str]:
    """Validate the structure and content of the player reference sheet.

    Args:
        pdf_reference: Reference DataFrame containing player metadata.

    Returns:
        A list of error messages for invalid reference sheet contents.
    """
    errors: List[str] = []
    required = {"full_name", "team", "player_id"}
    missing = required - set(pdf_reference.columns)
    if missing:
        errors.append(
            f"Reference is missing required columns: {', '.join(sorted(missing))}"
        )
        return errors

    pdf_reference = pdf_reference.copy()
    pdf_reference["team"] = pdf_reference["team"].astype(str).str.strip()
    pdf_reference["full_name"] = pdf_reference["full_name"].astype(str).str.strip()
    pdf_reference["player_id"] = pdf_reference["player_id"].astype(str).str.strip()

    # Basic structural checks
    if pdf_reference["full_name"].eq("").any():
        count = int(pdf_reference["full_name"].eq("").sum())
        errors.append(f"Reference has {count} blank full_name value(s)")
    if pdf_reference["team"].eq("").any():
        count = int(pdf_reference["team"].eq("").sum())
        errors.append(f"Reference has {count} blank team value(s)")
    if pdf_reference["player_id"].eq("").any():
        count = int(pdf_reference["player_id"].eq("").sum())
        errors.append(f"Reference has {count} blank player_id value(s)")

    # Team count checks
    team_counts = pdf_reference["team"].value_counts().sort_index()
    if len(team_counts) != 14:
        errors.append(
            f"Reference has {len(team_counts)} teams, expected 14 teams"
        )

    for team, count in team_counts.items():
        if count < 11 or count > 50:
            errors.append(
                f"Team '{team}' has {count} players; expected between 11 and 50"
            )

    # ID uniqueness
    player_id_counts = pdf_reference["player_id"].value_counts()
    dup_ids = player_id_counts[player_id_counts > 1]
    for player_id, cnt in dup_ids.items():
        errors.append(f"Duplicate player_id in reference: '{player_id}' appears {cnt} times")

    # Prohibited content checks
    string_columns = pdf_reference.select_dtypes(include=["object"]).columns.tolist()
    prohibited = {"captain", "loan"}
    for keyword in prohibited:
        matches = []
        for idx, row in pdf_reference.iterrows():
            row_context = f"{row['full_name']} ({row['team']})"
            for col in string_columns:
                cell = str(row[col])
                if keyword in cell.lower():
                    matches.append(f"{row_context} in column '{col}'")
        if matches:
            errors.append(
                f"Reference contains prohibited text '{keyword}' in rows: {', '.join(matches)}"
            )

    return errors


def validate_players_exist_in_reference(
    pdf_long: pd.DataFrame, pdf_reference: pd.DataFrame
) -> List[str]:
    """Check that every picked player exists in the reference sheet.

    Args:
        pdf_long: Long-form form response DataFrame containing ``full_name``.
        pdf_reference: Reference DataFrame containing valid ``full_name`` values.

    Returns:
        A list of error messages for unknown players, including submitter context.
    """
    errors: List[str] = []
    if "full_name" not in pdf_reference.columns:
        errors.append("Reference is missing 'full_name' column")
        return errors

    ref_names = set(pdf_reference["full_name"].astype(str).str.strip())

    unknown_map: dict = {}

    for _, row in pdf_long.iterrows():
        v = _safe_str(row.get("full_name"), "")
        if not v:
            continue
        if v not in ref_names:
            submitter = _safe_str(row.get("name"), "<unknown>")
            team = _safe_str(row.get("team_name"), "")
            submit_ctx = submitter + (f" (team: {team})" if team else "")
            unknown_map.setdefault(v, set()).add(submit_ctx)

    if unknown_map:
        parts = []
        for player in sorted(unknown_map.keys()):
            submitters = sorted(unknown_map[player])
            parts.append(f"{player} (submitted by: {', '.join(submitters)})")
        errors.append("Players in form not found in reference: " + ", ".join(parts))

    return errors


def validate_prep_merge(pdf_prep: pd.DataFrame) -> List[str]:
    """Validate that a merged player reference join produced player IDs.

    Args:
        pdf_prep: DataFrame created by merging the long-form picks with reference
            data on ``full_name``.

    Returns:
        A list of error messages for rows where ``player_id`` is missing after merge.
    """
    errors: List[str] = []
    if "player_id" not in pdf_prep.columns:
        errors.append("Merged data missing 'player_id' column")
        return errors

    missing_ids = pdf_prep[pdf_prep["player_id"].isna()]
    if not missing_ids.empty:
        names = missing_ids["full_name"].astype(str).str.strip().unique().tolist()
        details = []
        for n in sorted(names):
            rows = missing_ids[missing_ids["full_name"].astype(str).str.strip().eq(n)]
            submitters = []
            for _, r in rows.iterrows():
                submitter = _safe_str(r.get("name"), "<unknown>")
                team = _safe_str(r.get("team_name"), "")
                submitters.append(submitter + (f" (team: {team})" if team else ""))
            submitters = sorted(set(submitters))
            details.append(f"{n} (submitted by: {', '.join(submitters)})")

        errors.append(
            "After merge some players have no player_id (not found in reference): "
            + ", ".join(details)
        )

    return errors


def run_validations(
    pdf_long: pd.DataFrame, pdf_reference: pd.DataFrame
) -> Tuple[List[str], List[str]]:
    """Run the full validation suite and return deduplicated messages.

    Args:
        pdf_long: Long-form form response DataFrame to validate.
        pdf_reference: Reference DataFrame containing valid ``full_name`` values.

    Returns:
        A tuple containing deduplicated ``errors`` and ``warnings`` lists.
    """
    errors, warnings = validate_form_responses(pdf_long)
    errors += validate_reference_sheet(pdf_reference)
    errors += validate_reference_unique_names(pdf_reference)
    errors += validate_players_exist_in_reference(pdf_long, pdf_reference)
    pdf_prep_local = pdf_long.merge(pdf_reference, how="left", on="full_name")
    errors += validate_prep_merge(pdf_prep_local)

    # Deduplicate messages while keeping order
    seen = set()
    dedup_warnings = []
    for w in warnings:
        if w not in seen:
            dedup_warnings.append(w)
            seen.add(w)

    seen = set()
    dedup_errors = []
    for e in errors:
        if e not in seen:
            dedup_errors.append(e)
            seen.add(e)

    return dedup_errors, dedup_warnings

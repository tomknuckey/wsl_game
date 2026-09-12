import logging
import pandas as pd
from typing import Any


def _safe_str(val: Any, default: str = "") -> str:
    """Return a trimmed string for val, or default when val is missing.

    Avoid calling `.strip()` on non-string types (floats/NaN).
    """
    if pd.isna(val):
        return default
    return str(val).strip()


def load_reference_sheet(file_path: str) -> pd.DataFrame:
    """Load the player reference sheet with automatic delimiter detection.

    Some project files are TSV while others are CSV. The loader tries the
    common delimiters and accepts the first DataFrame that contains the
    expected reference columns.
    """
    candidates = [None, "\t", ",", ";", "|"]
    last_error = None

    for sep in candidates:
        try:
            df = pd.read_csv(file_path, sep=sep, engine="python")
        except Exception as exc:  # pragma: no cover - fallback path only
            last_error = exc
            continue

        df = df.copy()
        df.columns = [str(col).strip() for col in df.columns]

        if "player_id" in df.columns:
            df["player_id"] = df["player_id"].astype(str).str.strip()
        if "full_name" in df.columns:
            df["full_name"] = df["full_name"].astype(str).str.strip()

        normalized_columns = {str(col).strip() for col in df.columns}
        if {"full_name", "team", "player_id"}.issubset(normalized_columns):
            return df

        if "full_name" in normalized_columns or "player_id" in normalized_columns:
            return df

    raise ValueError(
        f"Could not load reference sheet '{file_path}' with a valid delimiter. "
        f"Last error: {last_error}"
    )


def _coerce_datetime(value: Any) -> pd.Timestamp:
    """Parse a timestamp-like value into a pandas Timestamp."""
    if pd.isna(value):
        return pd.NaT
    if isinstance(value, pd.Timestamp):
        return value
    if hasattr(value, "to_pydatetime"):
        try:
            return pd.Timestamp(value.to_pydatetime())
        except (TypeError, ValueError):
            pass

    for fmt in (
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ):
        try:
            return pd.to_datetime(value, format=fmt, dayfirst=True)
        except (TypeError, ValueError):
            continue

    try:
        return pd.to_datetime(value, dayfirst=True, errors="coerce")
    except (TypeError, ValueError):
        return pd.NaT


def filter_form_by_deadline(pdf: pd.DataFrame, deadline: Any) -> pd.DataFrame:
    """Keep only the latest valid submission per submitter before the deadline."""
    df = pdf.copy()

    if "timestamp" not in df.columns:
        logging.info("No timestamp column found; skipping deadline filter")
        return df

    if df.empty:
        return df

    deadline_dt = _coerce_datetime(deadline)
    if pd.isna(deadline_dt):
        logging.warning("Could not parse submission deadline: %s", deadline)
        return df

    df["timestamp_parsed"] = df["timestamp"].apply(_coerce_datetime)
    df["before_deadline"] = df["timestamp_parsed"].isna() | (
        df["timestamp_parsed"] <= deadline_dt
    )

    if "name" not in df.columns:
        filtered_df = df.loc[df["before_deadline"]].drop(
            columns=["timestamp_parsed", "before_deadline"]
        )
        return filtered_df

    eligible_rows = df.loc[df["before_deadline"]].copy()
    if eligible_rows.empty:
        passed_count = 0
        failed_count = int(len(df))
        logging.info(
            "Deadline filter summary: %s kept before deadline, %s excluded after deadline",
            passed_count,
            failed_count,
        )
        return eligible_rows.drop(columns=["timestamp_parsed", "before_deadline"])

    latest_timestamp_by_submitter = eligible_rows.groupby("name")[
        "timestamp_parsed"
    ].transform("max")
    latest_submission_mask = eligible_rows["timestamp_parsed"].eq(
        latest_timestamp_by_submitter
    )
    filtered_df = eligible_rows.loc[latest_submission_mask].drop(
        columns=["timestamp_parsed", "before_deadline"]
    )

    passed_count = int(len(filtered_df))
    failed_count = int(len(df) - passed_count)
    logging.info(
        "Deadline filter summary: %s kept before deadline, %s excluded because a later duplicate submission was used",
        passed_count,
        failed_count,
    )

    return filtered_df


def filter_by_name_prefixes(
    pdf: pd.DataFrame, prefixes: list, enabled: bool = True
) -> pd.DataFrame:
    """Exclude rows where the submitter name starts with any prefix in ``prefixes``.

    Operates on the long-form DataFrame (one pick per row). Logs how many rows
    were dropped and returns the filtered DataFrame.
    """
    df = pdf.copy()

    if not enabled or not prefixes:
        return df

    if "name" not in df.columns:
        logging.info("No name column found; skipping prefix-based exclusion")
        return df

    prefixes_norm = [str(p).strip().lower() for p in prefixes if p]
    if not prefixes_norm:
        return df

    name_series = df["name"].astype(str).str.strip().str.lower()
    mask = name_series.apply(lambda n: any(n.startswith(pref) for pref in prefixes_norm))
    removed_count = int(mask.sum())
    if removed_count:
        logging.info(
            "Excluded %s rows where submitter name started with prefixes: %s",
            removed_count,
            prefixes,
        )

    return df.loc[~mask]


def rename_form_columns(pdf: pd.DataFrame) -> pd.DataFrame:
    """Rename form response columns to standard names.

    Args:
        pdf: DataFrame with form response data

    Returns:
        DataFrame with renamed columns
    """
    return pdf.rename(
        columns={
            "Timestamp": "timestamp",
            "Your Full Name": "name",
            (
                "Player 1 \nEnter full player name exactly as shown in the "
                "reference sheet, as defined at the top"
            ): "player_1",
            (
                "Player 2\nEnter full player name exactly as shown in the "
                "reference sheet, as defined at the top"
            ): "player_2",
            (
                "Player 3\nEnter full player name exactly as shown in the "
                "reference sheet, as defined at the top"
            ): "player_3",
            (
                "Player 4\nEnter full player name exactly as shown in the "
                "reference sheet, as defined at the top"
            ): "player_4",
            (
                "Player 5\nEnter full player name exactly as shown in the "
                "reference sheet, as defined at the top"
            ): "player_5",
            "Are you happy to be contacted if there's issues with your answers": (
                "contact_permission"
            ),
            "Contact Information (Email / Whatsapp)": "contact_details",
            "Team Name": "team_name",
        }
    )


def form_to_long(pdf: pd.DataFrame) -> pd.DataFrame:
    """Convert form data from wide to long format.

    Args:
        pdf: DataFrame in wide format with player picks

    Returns:
        DataFrame in long format with one pick per row
    """
    return pdf.melt(
        id_vars=["timestamp", "name", "team_name"],
        value_vars=["player_1", "player_2", "player_3", "player_4", "player_5"],
        var_name="pick_slot",
        value_name="full_name",
    )


def clean_form_data(pdf: pd.DataFrame) -> pd.DataFrame:
    """Clean form data by removing NaN values and stripping whitespace.

    Args:
        pdf: DataFrame with form data

    Returns:
        Cleaned DataFrame
    """
    pdf = pdf.dropna(subset=["full_name"])
    pdf["full_name"] = pdf["full_name"].str.strip()
    return pdf


def number_of_pics(pdf: pd.DataFrame) -> pd.DataFrame:
    """Count the number of picks per player.

    Args:
        pdf: DataFrame with player pick data

    Returns:
        DataFrame with player_id and num_picks columns
    """
    return (
        pdf.groupby(["player_id", "full_name"])["team_name"]
        .count()
        .reset_index(name="num_picks")
    )


def adjust_goals(pdf: pd.DataFrame) -> pd.DataFrame:
    """Adjust goals by splitting each goal across all players who picked them.

    Args:
        pdf: DataFrame with goals and num_picks columns

    Returns:
        DataFrame with normalized goals in the ``goals`` column
    """
    pdf["goals"] = pdf["goals"].fillna(0)

    pdf["goals"] = pdf["goals"] / pdf["num_picks"]

    return pdf


def generate_results(pdf: pd.DataFrame) -> pd.DataFrame:
    """Generate summary results grouped by name and sorted by goals.

    Args:
        pdf: DataFrame with combined pick and goals data

    Returns:
        DataFrame with total goals per person, sorted descending
    """
    return (
        pdf.groupby("name")["goals"]
        .sum()
        .round(2)
        .reset_index()
        .sort_values(by="goals", ascending=False)
    )


def apply_manual_renames(pdf_long: pd.DataFrame, renames: dict) -> pd.DataFrame:
    """Apply manual renames to the `full_name` column in a long-form dataframe.

    Logs each rename applied. Returns the modified DataFrame so it is safe
    to use with `DataFrame.pipe()`.
    """
    if not renames:
        logging.info("No manual renames applied (renames dict empty)")
        return pdf_long

    df = pdf_long.copy()
    # ensure full_name is string/stripped
    df["full_name"] = df["full_name"].astype(str)
    for old, new in renames.items():
        mask = df["full_name"].str.strip() == str(old)
        cnt = int(mask.sum())
        if cnt > 0:
            df.loc[mask, "full_name"] = new
            msg = f"{old} -> {new} ({cnt} occurrences)"
            logging.info(f"Applied manual rename: {msg}")

    return df


def fill_missing_players(
    pdf_long: pd.DataFrame,
    pdf_reference: pd.DataFrame,
    fill_with_players: list,
) -> pd.DataFrame:
    """Fill invalid player picks with random valid players from the fill list.

    For each submitter, identifies any picks that are not in the reference sheet
    and replaces them with a random player from ``fill_with_players``, ensuring
    no duplicates within that submitter's picks.

    Args:
        pdf_long: Long-form DataFrame with columns ``name``, ``team_name``,
            ``pick_slot``, and ``full_name``.
        pdf_reference: Reference DataFrame with valid player names in ``full_name``.
        fill_with_players: List of valid player names to use as replacements.

    Returns:
        Modified long-form DataFrame with invalid picks replaced.
    """
    import random

    if not fill_with_players:
        logging.info("No fill players provided; skipping fill process")
        return pdf_long

    df = pdf_long.copy()
    df["full_name"] = df["full_name"].astype(str).str.strip()

    # Get valid reference names
    valid_names = set(
        pdf_reference["full_name"].astype(str).str.strip()
    )

    # Process each submitter
    for submitter_name in df["name"].unique():
        submitter_df = df[df["name"] == submitter_name]
        submitter_team = (
            submitter_df["team_name"].iloc[0]
            if len(submitter_df) > 0
            else "<unknown>"
        )
        submitter_team = _safe_str(submitter_team, "")

        # Get current valid picks for this submitter
        current_picks = submitter_df[
            submitter_df["full_name"].isin(valid_names)
        ]["full_name"].unique()
        current_picks_set = set(current_picks)

        # Find invalid picks
        invalid_rows = submitter_df[
            ~submitter_df["full_name"].isin(valid_names)
        ]

        for idx, row in invalid_rows.iterrows():
            old_player = row["full_name"]
            team_ctx = f" (team: {submitter_team})" if submitter_team else ""

            # Find a replacement from fill_with_players that isn't already picked
            available = [
                p
                for p in fill_with_players
                if p not in current_picks_set
            ]

            if not available:
                logging.warning(
                    f"{submitter_name}{team_ctx}: Could not find unique replacement "
                    f"for '{old_player}' (all fill players already in picks)"
                )
                continue

            new_player = random.choice(available)
            df.loc[idx, "full_name"] = new_player
            current_picks_set.add(new_player)

            msg = (
                f"{submitter_name}{team_ctx}: "
                f"Replaced invalid '{old_player}' with '{new_player}'"
            )
            logging.info(msg)

    return df


def resolve_duplicates_in_picks(
    pdf_long: pd.DataFrame,
    pdf_reference: pd.DataFrame,
    fill_with_players: list,
) -> pd.DataFrame:
    """Resolve any duplicate player picks within each submitter's picks.

    For each submitter, identifies duplicate picks and reassigns all but one
    to random available players from the fill list.

    Args:
        pdf_long: Long-form DataFrame with columns ``name``, ``team_name``,
            ``pick_slot``, and ``full_name``.
        pdf_reference: Reference DataFrame with valid player names in ``full_name``.
        fill_with_players: List of valid player names to use as replacements.

    Returns:
        Modified long-form DataFrame with duplicate picks resolved.
    """
    import random

    if not fill_with_players:
        logging.info("No fill players provided; skipping duplicate resolution")
        return pdf_long

    df = pdf_long.copy()
    df["full_name"] = df["full_name"].astype(str).str.strip()

    # Get valid reference names
    valid_names = set(
        pdf_reference["full_name"].astype(str).str.strip()
    )

    # Process each submitter
    for submitter_name in df["name"].unique():
        submitter_mask = df["name"] == submitter_name
        submitter_df = df[submitter_mask]
        submitter_team = (
            submitter_df["team_name"].iloc[0]
            if len(submitter_df) > 0
            else "<unknown>"
        )
        submitter_team = _safe_str(submitter_team, "")
        team_ctx = f" (team: {submitter_team})" if submitter_team else ""

        # Find duplicates within this submitter's picks
        pick_counts = submitter_df["full_name"].value_counts()
        duplicated_players = pick_counts[pick_counts > 1].index.tolist()

        for dup_player in duplicated_players:
            dup_mask = (df["name"] == submitter_name) & (
                df["full_name"] == dup_player
            )
            dup_indices = df[dup_mask].index.tolist()

            # Keep first occurrence, replace the rest
            for idx in dup_indices[1:]:
                # Get all currently valid picks for this submitter (after any replacements)
                current_picks = df[
                    (df["name"] == submitter_name)
                    & (df["full_name"].isin(valid_names))
                ]["full_name"].unique()
                current_picks_set = set(current_picks)

                # Find available replacements
                available = [
                    p
                    for p in fill_with_players
                    if p not in current_picks_set
                ]

                if not available:
                    logging.warning(
                        f"{submitter_name}{team_ctx}: Could not find replacement "
                        f"for duplicate '{dup_player}' (all fill players in use)"
                    )
                    continue

                new_player = random.choice(available)
                df.loc[idx, "full_name"] = new_player
                valid_names.add(new_player)

                msg = (
                    f"{submitter_name}{team_ctx}: "
                    f"Resolved duplicate '{dup_player}' with '{new_player}'"
                )
                logging.info(msg)

    return df

def generate_goals(max_gw: int, data_source: str) -> pd.DataFrame:
    """Load and aggregate goal data across multiple gameweeks.

    Reads goal CSVs from ``data/input/{data_source}/player_goals/GW_*.csv``
    for gameweeks 1 through ``max_gw``. Missing files are skipped silently.

    Args:
        max_gw: Maximum gameweek number to attempt to load (exclusive).
        data_source: Directory name containing the player goals subdirectory.

    Returns:
        DataFrame with columns ``player_id`` and ``goals`` (aggregated across all GWs).
    """
    pdf_goals = []

    for gw in range(1, max_gw):
        file_path = f"data/input/{data_source}/player_goals/GW_{gw}.csv"

        try:
            pdf_temp = pd.read_csv(file_path)
            if "player_id" in pdf_temp.columns:
                pdf_temp["player_id"] = pdf_temp["player_id"].astype(str).str.strip()
            if "goals" in pdf_temp.columns:
                pdf_temp["goals"] = pd.to_numeric(pdf_temp["goals"], errors="coerce").fillna(0)
            pdf_temp["gw"] = gw
            pdf_goals.append(pdf_temp)
        except FileNotFoundError:
            pass  # skips missing GW files

    if not pdf_goals:
        return pd.DataFrame(columns=["player_id", "goals"])

    pdf_goals = pd.concat(pdf_goals, ignore_index=True)

    return pdf_goals.groupby("player_id").agg({"goals": "sum"}).reset_index()


def generate_top_missed(pdf_goals_agg, pdf_pics):

    """ Generate a report of the top 20 players with goals scored but not picked by any manager."""

    pdf_goals_pics =pdf_goals_agg.merge(pdf_pics[["player_id", "num_picks"]], how="left", on="player_id")
    pdf_goals_pics["num_picks"] = pdf_goals_pics["num_picks"].fillna(0)
    pdf_goals_pics = pdf_goals_pics.query("num_picks == 0").sort_values("goals", ascending=False).head(20)
    print("Top Missed")
    print(pdf_goals_pics.head())

def generate_manager_ownership(pdf_prep, pdf_pics, output_dir):

    """Generate a report of the average ownership per manager and the number of template/differential picks.
    """

    manager_ownership = (
        pdf_prep.merge(pdf_pics, how="left", on="player_id")
        .groupby(["name", "team_name"])
        .agg(
            avg_ownership=("num_picks", "mean"),
            template_picks=("num_picks", lambda picks: (picks >= 2).sum()),
            differential_picks=("num_picks", lambda picks: (picks == 1).sum()),
        )
        .reset_index()
        .assign(avg_ownership=lambda df: df["avg_ownership"].round(2))
        .sort_values(["avg_ownership", "differential_picks"], ascending=[False, True])
    )
    manager_ownership.to_csv(output_dir / "manager_ownership.csv", index=False)

def generate_best_differential(pdf_pics, pdf_goals_agg, pdf_prep):

    """Generate a report of the best differential picks (players picked by only one manager with goals scored).
    """

    pdf_differential = pdf_pics.merge(pdf_goals_agg[["player_id", "goals"]], how="left", on="player_id").sort_values("num_picks", ascending=False).query("num_picks == 1").query("goals > 0").merge(pdf_prep[["player_id", "name", "team_name"]], on="player_id")
    pdf_differential["goals"] = pdf_differential["goals"].fillna(0).astype(int)
    print("Best Differential Picks")
    print(pdf_differential.sort_values("goals", ascending=False).head())
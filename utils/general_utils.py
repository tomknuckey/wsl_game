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
        pdf.groupby("player_id")[["name"]]
        .count()
        .reset_index()
        .rename(columns={"name": "num_picks"})
    )


def adjust_goals(pdf: pd.DataFrame) -> pd.DataFrame:
    """Adjust goals by normalizing by number of picks.

    Args:
        pdf: DataFrame with goals and num_picks columns

    Returns:
        DataFrame with adjusted goals column
    """
    pdf["goals"] = pdf["goals"].fillna(0)

    pdf["adjusted_goals "] = pdf["goals"] / pdf["num_picks"]

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

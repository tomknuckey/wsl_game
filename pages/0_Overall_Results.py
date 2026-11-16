from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from config import data_source, max_gw, season_id, transfer_rules
from utils.general_utils import (
    generate_gameweek_goals,
    load_reference_sheet,
)
from utils.transfer_results import (
    build_transfer_outcomes,
    get_effective_transfers,
)
from utils.transfer_storage import TransferStorageError, get_transfer_ledger
from utils.transfer_utils import (
    format_utc_datetime,
    load_transfer_records,
    transfer_rules_from_config,
)


DATA_SOURCE = data_source


def get_manager_count(pdf: pd.DataFrame) -> int:
    """Return the number of managers from either the legacy or current output schema."""
    if pdf.empty:
        return 0

    for possible in ("team", "name", "Manager"):
        if possible in pdf.columns:
            return int(pdf[possible].dropna().nunique())

    return 0


def get_weeks_of_data(source: str = data_source) -> int:
    """Count the number of weekly GW CSVs without storing any separate metadata."""
    goals_dir = Path("data/input") / source / "player_goals"
    if not goals_dir.exists():
        return 0
    return len(sorted(goals_dir.glob("GW_*.csv")))


def load_csv(path: str, columns: list[str] | None = None) -> pd.DataFrame:
    """Load a CSV if it exists and return an empty DataFrame otherwise."""
    csv_path = Path(path)
    if not csv_path.exists():
        return pd.DataFrame(columns=columns)
    return pd.read_csv(csv_path)


def humanise_columns(pdf: pd.DataFrame, mappings: dict[str, str]) -> pd.DataFrame:
    """Return a copy of a dataframe with friendlier display names for table columns."""
    renamed = pdf.copy()
    for old_name, new_name in mappings.items():
        if old_name in renamed.columns:
            renamed = renamed.rename(columns={old_name: new_name})
    return renamed


def cumulative_history(
    pdf_weekly: pd.DataFrame,
    entity_column: str,
    entity_ids: list,
    gameweeks: list[int],
) -> pd.DataFrame:
    """Build a cumulative gameweek-by-entity history, treating missing rows as zero."""
    if pdf_weekly.empty or not entity_ids:
        return pd.DataFrame(index=gameweeks)

    weekly = (
        pdf_weekly.groupby(["gameweek", entity_column], as_index=False)["goals"]
        .sum()
        .pivot(index="gameweek", columns=entity_column, values="goals")
    )
    return (
        weekly.reindex(index=gameweeks, columns=entity_ids, fill_value=0)
        .fillna(0)
        .cumsum()
    )


# Page configuration
st.set_page_config(
    page_title="Overall Results | WSL Fantasy Game",
    page_icon="⚽",
    layout="wide",
)


# Load data
output_dir = Path("data/output") / DATA_SOURCE
pdf_results = load_csv(str(output_dir / "results.csv"))
pdf_manager_rankings = pdf_results.copy()
pdf_pics = load_csv(str(output_dir / "player_pics.csv"))
pdf_goals_agg = load_csv(str(output_dir / "pdf_goals_agg.csv"))
pdf_manager_ownership = load_csv(str(output_dir / "manager_ownership.csv"))
pdf_best_differential = load_csv(str(output_dir / "best_differential.csv"))
pdf_top_missed = load_csv(str(output_dir / "top_missed.csv"))
pdf_manager_player_points = load_csv(
    str(output_dir / "manager_player_points.csv"),
    columns=["name", "team_name", "player_id", "full_name", "team", "goals"],
)
pdf_manager_player_gameweek_points = load_csv(
    str(output_dir / "manager_player_gameweek_points.csv"),
    columns=[
        "name",
        "team_name",
        "player_id",
        "full_name",
        "team",
        "gameweek",
        "goals",
    ],
)
pdf_reference = load_reference_sheet(
    f"data/input/{DATA_SOURCE}/player_reference.csv"
)
pdf_weekly_goals = generate_gameweek_goals(max_gw, DATA_SOURCE)
pdf_transfer_activity = pd.DataFrame()
pdf_transfer_bought = pd.DataFrame()
pdf_transfer_sold = pd.DataFrame()
pdf_transfer_success = pd.DataFrame()
transfer_rules_for_season = transfer_rules_from_config(transfer_rules)
transfer_results_as_of = datetime.now(timezone.utc)
transfer_empty_state = "No eligible transfers are available for this season yet."
upcoming_announcement_rules = [
    rule
    for rule in transfer_rules_for_season
    if rule.season_id == season_id
    and rule.deadline_datetime_utc > transfer_results_as_of
]
if upcoming_announcement_rules:
    next_announcement = min(
        upcoming_announcement_rules,
        key=lambda rule: rule.deadline_datetime_utc,
    )
    transfer_empty_state = (
        "Transfer results will be shown after the transfer deadline: "
        f"{format_utc_datetime(next_announcement.deadline_utc)}."
    )
try:
    transfer_ledger = get_transfer_ledger(
        DATA_SOURCE,
        st.secrets,
        Path("data/input") / DATA_SOURCE / "team_transfers.csv",
    )
    transfer_records = load_transfer_records(transfer_ledger)
    effective_transfers = get_effective_transfers(
        transfer_records,
        transfer_rules_for_season,
        season_id,
        as_of_utc=transfer_results_as_of,
    )
except (ValueError, TransferStorageError) as error:
    effective_transfers = []
    st.error(f"Transfer data is unavailable: {error}")


def transfer_player_details(
    player_id: str,
    fallback_name: str,
    fallback_club: str = "",
) -> tuple[str, str]:
    reference_match = pdf_reference.loc[
        pdf_reference["player_id"].astype(str).str.strip().eq(str(player_id).strip())
    ]
    if reference_match.empty:
        return fallback_name, fallback_club
    player = reference_match.iloc[0]
    reference_name = player.get("full_name")
    reference_club = player.get("team")
    return (
        fallback_name
        if pd.isna(reference_name) or not str(reference_name).strip()
        else str(reference_name),
        fallback_club
        if pd.isna(reference_club) or not str(reference_club).strip()
        else str(reference_club),
    )


if effective_transfers:
    transfer_display_rows = []
    for transfer in effective_transfers:
        outgoing_name, outgoing_club = transfer_player_details(
            transfer["player_out_id"],
            transfer["player_out_name"],
        )
        incoming_name, incoming_club = transfer_player_details(
            transfer["player_in_id"],
            transfer["player_in_name"],
            transfer["player_in_club"],
        )
        team_name = transfer["team_name"]
        if "@" in team_name:
            team_name = "Team name unavailable"
        transfer_display_rows.append(
            {
                "team_name": team_name,
                "effective_gameweek": int(transfer["effective_gameweek"]),
                "player_out_id": transfer["player_out_id"],
                "player_out_name": outgoing_name,
                "player_out_club": outgoing_club,
                "player_in_id": transfer["player_in_id"],
                "player_in_name": incoming_name,
                "player_in_club": incoming_club,
            }
        )

    transfer_rows = pd.DataFrame(transfer_display_rows)
    pdf_transfer_activity = (
        transfer_rows[
            [
                "team_name",
                "effective_gameweek",
                "player_out_name",
                "player_in_name",
            ]
        ]
        .rename(
            columns={
                "team_name": "Team",
                "effective_gameweek": "Effective Gameweek",
                "player_out_name": "Player Sold",
                "player_in_name": "Player Bought",
            }
        )
        .sort_values(
            ["Effective Gameweek", "Team"],
            ascending=[False, True],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    def player_transfer_ranking(
        transfer_direction: str,
        player_name_column: str,
        club_column: str,
    ) -> pd.DataFrame:
        ranking = (
            transfer_rows.groupby(
                [transfer_direction, player_name_column, club_column],
                dropna=False,
            )
            .size()
            .reset_index(name="Transfers")
            .sort_values(
                ["Transfers", player_name_column],
                ascending=[False, True],
                kind="stable",
            )
            .reset_index(drop=True)
        )
        ranking.insert(
            0,
            "Rank",
            ranking["Transfers"].rank(method="min", ascending=False).astype(int),
        )
        return ranking.rename(
            columns={
                player_name_column: "Player",
                club_column: "Club",
            }
        )[["Rank", "Player", "Club", "Transfers"]]

    pdf_transfer_bought = player_transfer_ranking(
        "player_in_id",
        "player_in_name",
        "player_in_club",
    )
    pdf_transfer_sold = player_transfer_ranking(
        "player_out_id",
        "player_out_name",
        "player_out_club",
    )
    transfer_outcomes = build_transfer_outcomes(
        effective_transfers,
        pdf_weekly_goals,
    )
    success_rows = []
    for outcome, display_transfer in zip(
        transfer_outcomes,
        transfer_display_rows,
    ):
        success_rows.append(
            {
                "team_name": display_transfer["team_name"],
                "effective_gameweek": display_transfer["effective_gameweek"],
                "player_out_name": display_transfer["player_out_name"],
                "player_in_name": display_transfer["player_in_name"],
                "incoming_goals": outcome["incoming_goals"],
                "outgoing_goals": outcome["outgoing_goals"],
                "net_goals": outcome["net_goals"],
            }
        )
    pdf_transfer_success = pd.DataFrame(success_rows)
    pdf_transfer_success = pdf_transfer_success.sort_values(
        ["net_goals", "effective_gameweek", "team_name"],
        ascending=[False, True, True],
        na_position="last",
        kind="stable",
    ).reset_index(drop=True)
    available_outcomes = pdf_transfer_success["net_goals"].notna()
    pdf_transfer_success.insert(
        0,
        "Rank",
        pd.Series(pd.NA, index=pdf_transfer_success.index, dtype="Int64"),
    )
    pdf_transfer_success.loc[available_outcomes, "Rank"] = (
        pdf_transfer_success.loc[available_outcomes, "net_goals"]
        .rank(method="min", ascending=False)
        .astype(int)
    )
    pdf_transfer_success["Outcome"] = pdf_transfer_success["net_goals"].map(
        lambda value: "Pending" if pd.isna(value) else "Available"
    )
    pdf_transfer_success = pdf_transfer_success.rename(
        columns={
            "team_name": "Team",
            "effective_gameweek": "Effective Gameweek",
            "player_out_name": "Player Sold",
            "player_in_name": "Player Bought",
            "incoming_goals": "Incoming Goals",
            "outgoing_goals": "Outgoing Goals",
            "net_goals": "Net Goals",
        }
    )[
        [
            "Rank",
            "Team",
            "Effective Gameweek",
            "Player Sold",
            "Player Bought",
            "Incoming Goals",
            "Outgoing Goals",
            "Net Goals",
            "Outcome",
        ]
    ]

pdf_weekly_manager_results = (
    pdf_manager_player_gameweek_points.groupby(
        ["name", "team_name", "gameweek"], as_index=False
    )["goals"].sum()
)

# Human-readable display names for tables
pdf_results = humanise_columns(
    pdf_results,
    {"name": "Manager", "team_name": "Team Name", "goals": "Goals"},
).sort_values("Goals", ascending=False).reset_index(drop=True)
pdf_results.insert(0, "Position", range(1, len(pdf_results) + 1))
pdf_results = pdf_results[["Position", "Manager", "Team Name", "Goals"]]

pdf_goals_agg = humanise_columns(
    pdf_goals_agg,
    {"player_id": "Player ID", "full_name": "Player", "team": "Club", "goals": "Goals"},
)[["Player", "Club", "Goals"]]

pdf_manager_ownership = humanise_columns(
    pdf_manager_ownership,
    {
        "name": "Manager",
        "team_name": "Team Name",
        "avg_ownership": "Average Player Ownership",
        "template_picks": "Non Unique Picks",
        "differential_picks": "Unique Picks",
    },
)

pdf_pics = humanise_columns(
    pdf_pics,
    {"index": "Rank", "player_id": "Player ID", "full_name": "Player", "team": "Club", "num_picks": "Picks"},
)[["Player", "Club", "Picks"]]

pdf_best_differential = humanise_columns(
    pdf_best_differential,
    {
        "full_name": "Player",
        "team": "Club",
        "goals": "Goals",
        "name": "Manager",
        "team_name": "Team Name",
    },
    )[["Player", "Club", "Goals", "Manager", "Team Name"]]

pdf_top_missed = humanise_columns(
    pdf_top_missed,
    {"full_name": "Player", "team": "Club", "goals": "Goals"},
)[["Player", "Club", "Goals"]]

pdf_manager_player_points = humanise_columns(
    pdf_manager_player_points,
    {
        "name": "Manager",
        "team_name": "Team Name",
        "full_name": "Player",
        "team": "Club",
        "goals": "Points",
    },
)[["Manager", "Team Name", "Player", "Club", "Points"]]

pdf_manager_player_gameweek_points = humanise_columns(
    pdf_manager_player_gameweek_points,
    {
        "name": "Manager",
        "team_name": "Team Name",
        "full_name": "Player",
        "team": "Club",
        "gameweek": "Gameweek",
        "goals": "Points",
    },
)[["Manager", "Team Name", "Player", "Club", "Gameweek", "Points"]]


# Custom styling
st.markdown(
    """
    <style>
        .main-title {
            font-size: 3rem;
            font-weight: 700;
            margin-bottom: 0;
        }

        .subtitle {
            font-size: 1.2rem;
            color: #666;
            margin-bottom: 2rem;
        }

        .info-card {
            padding: 1rem;
            border-radius: 10px;
            background-color: #f5f5f5;
            text-align: center;
        }

        .info-value {
            font-size: 1.8rem;
            font-weight: 700;
        }

        .info-label {
            color: #666;
            font-size: 0.9rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# Header
st.markdown(
    '<div class="main-title">⚽ WSL Fantasy Game</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">'
    "Track how everyone's doing throughout the WSL Fantasy Game."
    "</div>",
    unsafe_allow_html=True,
)


# Game information
st.subheader("Game Information")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="Weeks of data",
        value=get_weeks_of_data(DATA_SOURCE),
    )

with col2:
    st.write("")

with col3:
    st.metric(
        label="Managers",
        value=get_manager_count(pdf_results),
    )


# Leaderboard
st.header("Leaderboard")

st.dataframe(
    pdf_results,
    use_container_width=True,
    hide_index=True,
)

# Performance over time
st.header("Performance Over Time")
if pdf_weekly_goals.empty:
    st.info("Weekly goal data is not available yet.")
elif pdf_reference.empty:
    st.info("Player reference data is not available yet.")
else:
    gameweeks = sorted(pdf_weekly_goals["gameweek"].unique().tolist())
    player_reference = pdf_reference.drop_duplicates("player_id").copy()
    player_reference["player_id"] = player_reference["player_id"].astype(str)
    weekly_goals = pdf_weekly_goals.copy()
    weekly_goals["player_id"] = weekly_goals["player_id"].astype(str)
    player_totals = (
        weekly_goals.groupby("player_id", as_index=False)["goals"]
        .sum()
        .merge(
            player_reference[["player_id", "full_name", "team"]],
            how="right",
            on="player_id",
        )
        .fillna({"goals": 0})
        .sort_values(["goals", "full_name"], ascending=[False, True])
    )
    player_default = player_totals.head(5)["player_id"].tolist()
    player_options = player_totals["player_id"].tolist()
    player_labels = player_reference.set_index("player_id").apply(
        lambda row: f"{row['full_name']} ({row['team']})", axis=1
    ).to_dict()

    manager_rankings = pdf_manager_rankings.copy()
    if {"name", "team_name", "goals"}.issubset(manager_rankings.columns):
        manager_rankings = manager_rankings.sort_values(
            "goals", ascending=False, kind="stable"
        )
        manager_options = list(
            manager_rankings[["name", "team_name"]]
            .drop_duplicates()
            .itertuples(index=False, name=None)
        )
        default_managers = manager_options[:5]
    else:
        manager_options = []
        default_managers = []

    manager_column, player_column = st.columns(2)
    with manager_column:
        st.markdown("**Managers**")
        selected_managers = []
        with st.container(height=340, border=True):
            for manager_index, manager in enumerate(manager_options):
                if st.checkbox(
                    f"{manager[0]} ({manager[1]})",
                    value=manager in default_managers,
                    key=f"manager_history_{manager_index}",
                ):
                    selected_managers.append(manager)
    with player_column:
        st.markdown("**Goal scorers**")
        selected_players = []
        with st.container(height=340, border=True):
            for player_id in player_options:
                if st.checkbox(
                    player_labels[player_id],
                    value=player_id in player_default,
                    key=f"player_history_{player_id}",
                ):
                    selected_players.append(player_id)

    manager_chart_column, player_chart_column = st.columns(2)
    with manager_chart_column:
        st.subheader("Manager cumulative score")
        if not selected_managers:
            st.info("Select one or more managers to compare.")
        elif pdf_weekly_manager_results.empty:
            st.info("Manager picks are not available for weekly scoring.")
        else:
            manager_chart = pd.DataFrame(index=gameweeks)
            for manager in selected_managers:
                manager_weekly = pdf_weekly_manager_results.loc[
                    pdf_weekly_manager_results["name"].eq(manager[0])
                    & pdf_weekly_manager_results["team_name"].eq(manager[1])
                ]
                manager_series = manager_weekly.set_index("gameweek")["goals"].reindex(
                    gameweeks, fill_value=0
                )
                manager_chart[f"{manager[0]} ({manager[1]})"] = (
                    manager_series.cumsum()
                )
            st.line_chart(manager_chart, x_label="Gameweek", y_label="Goals")

    with player_chart_column:
        st.subheader("Goal scorer cumulative goals")
        if not selected_players:
            st.info("Select one or more goal scorers to compare.")
        else:
            player_chart = cumulative_history(
                weekly_goals,
                "player_id",
                selected_players,
                gameweeks,
            )
            player_chart.columns = [
                player_labels[player_id] for player_id in player_chart.columns
            ]
            st.line_chart(player_chart, x_label="Gameweek", y_label="Goals")


# Additional information
st.header("Game Data")

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11 = st.tabs(
    [
        "⚽ Top Scorers",
        "👥 Player Ownership",
        "📊 Player Information",
        "⭐ Best Differential",
        "⚠️ Top Missed",
        "👤 Manager Player Points",
        "📅 Manager Player by Gameweek",
        "🔁 Transfers",
        "📥 Most Bought",
        "📤 Most Sold",
        "🏆 Transfer Success",
    ]
)

with tab1:
    st.dataframe(
        pdf_goals_agg,
        use_container_width=True,
        hide_index=True,
    )

with tab2:
    st.dataframe(
        pdf_manager_ownership,
        use_container_width=True,
        hide_index=True,
    )

with tab3:
    st.dataframe(
        pdf_pics,
        use_container_width=True,
        hide_index=True,
    )

with tab4:
    st.dataframe(
        pdf_best_differential,
        use_container_width=True,
        hide_index=True,
    )

with tab5:
    st.dataframe(
        pdf_top_missed,
        use_container_width=True,
        hide_index=True,
    )

with tab6:
    st.dataframe(
        pdf_manager_player_points,
        use_container_width=True,
        hide_index=True,
    )

with tab7:
    st.dataframe(
        pdf_manager_player_gameweek_points,
        use_container_width=True,
        hide_index=True,
    )

with tab8:
    if pdf_transfer_activity.empty:
        st.info(transfer_empty_state)
    else:
        st.dataframe(
            pdf_transfer_activity,
            use_container_width=True,
            hide_index=True,
        )

with tab9:
    if pdf_transfer_bought.empty:
        st.info(transfer_empty_state)
    else:
        st.dataframe(
            pdf_transfer_bought,
            use_container_width=True,
            hide_index=True,
        )

with tab10:
    if pdf_transfer_sold.empty:
        st.info(transfer_empty_state)
    else:
        st.dataframe(
            pdf_transfer_sold,
            use_container_width=True,
            hide_index=True,
        )

with tab11:
    if pdf_transfer_success.empty:
        st.info(transfer_empty_state)
    else:
        st.caption(
            "Net goals = goals scored by the player bought minus goals scored by "
            "the player sold, from the effective gameweek onward. This is not "
            "the manager's official credited points."
        )
        if not pdf_transfer_success["Net Goals"].notna().any():
            st.info("Transfer outcomes are pending future gameweek goal data.")
        st.dataframe(
            pdf_transfer_success,
            use_container_width=True,
            hide_index=True,
        )
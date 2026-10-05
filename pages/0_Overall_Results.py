from pathlib import Path

import pandas as pd
import streamlit as st

from config import data_source, max_gw
from utils.general_utils import (
    generate_weekly_goals,
    generate_weekly_manager_results,
    load_reference_sheet,
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


def get_weeks_of_data(data_source: str = "actual") -> int:
    """Count the number of weekly GW CSVs without storing any separate metadata."""
    goals_dir = Path("data/input") / data_source / "player_goals"
    if not goals_dir.exists():
        return 0
    return len(sorted(goals_dir.glob("GW_*.csv")))


def load_csv(path: str) -> pd.DataFrame:
    """Load a CSV if it exists and return an empty DataFrame otherwise."""
    csv_path = Path(path)
    if not csv_path.exists():
        return pd.DataFrame()
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
        pdf_weekly.groupby(["gw", entity_column], as_index=False)["goals"]
        .sum()
        .pivot(index="gw", columns=entity_column, values="goals")
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
pdf_results = load_csv(f"data/output/{DATA_SOURCE}/results.csv")
pdf_manager_rankings = pdf_results.copy()
pdf_pics = load_csv(f"data/output/{DATA_SOURCE}/player_pics.csv")
pdf_goals_agg = load_csv(f"data/output/{DATA_SOURCE}/pdf_goals_agg.csv")
pdf_manager_ownership = load_csv(f"data/output/{DATA_SOURCE}/manager_ownership.csv")
pdf_best_differential = load_csv(f"data/output/{DATA_SOURCE}/best_differential.csv")
pdf_top_missed = load_csv(f"data/output/{DATA_SOURCE}/top_missed.csv")
pdf_manager_picks = load_csv(f"data/intermediate/{DATA_SOURCE}/player_pics.csv")
pdf_reference = load_reference_sheet(
    f"data/input/{DATA_SOURCE}/player_reference.csv"
)
pdf_weekly_goals = generate_weekly_goals(max_gw, DATA_SOURCE)
pdf_weekly_manager_results = pd.DataFrame(
    columns=["name", "team_name", "gw", "goals"]
)
if not pdf_manager_picks.empty and not pdf_pics.empty:
    pdf_prep = pdf_reference[["player_id", "full_name"]].merge(
        pdf_manager_picks, how="inner", on="full_name"
    )
    pdf_weekly_manager_results = generate_weekly_manager_results(
        pdf_prep, pdf_pics, pdf_weekly_goals
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
    gameweeks = sorted(pdf_weekly_goals["gw"].unique().tolist())
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
                manager_series = manager_weekly.set_index("gw")["goals"].reindex(
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

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "⚽ Top Scorers",
        "👥 Player Ownership",
        "📊 Player Information",
        "⭐ Best Differential",
        "⚠️ Top Missed",
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
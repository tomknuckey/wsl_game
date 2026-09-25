from pathlib import Path

import pandas as pd
import streamlit as st


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


# Page configuration
st.set_page_config(
    page_title="WSL Fantasy Game",
    page_icon="⚽",
    layout="wide",
)


# Load data
pdf_results = load_csv("data/output/actual/results.csv")
pdf_pics = load_csv("data/output/actual/player_pics.csv")
pdf_goals_agg = load_csv("data/output/actual/pdf_goals_agg.csv")
pdf_manager_ownership = load_csv("data/output/actual/manager_ownership.csv")
pdf_best_differential = load_csv("data/output/actual/best_differential.csv")
pdf_top_missed = load_csv("data/output/actual/top_missed.csv")

# Human-readable display names for tables
pdf_results = humanise_columns(
    pdf_results,
    {"name": "Manager", "goals": "Goals"},
).sort_values("Goals", ascending=False).reset_index(drop=True)
pdf_results.insert(0, "Position", range(1, len(pdf_results) + 1))
pdf_results = pdf_results[["Position", "Manager", "Goals"]]

pdf_goals_agg = humanise_columns(
    pdf_goals_agg,
    {"player_id": "Player ID", "full_name": "Player", "goals": "Goals"},
)[["Player", "Goals"]]

pdf_manager_ownership = humanise_columns(
    pdf_manager_ownership,
    {
        "name": "Manager",
        "team_name": "Team",
        "avg_ownership": "Average Player Ownership",
        "template_picks": "Non Unique Picks",
        "differential_picks": "Unique Picks",
    },
)

pdf_pics = humanise_columns(
    pdf_pics,
    {"index": "Rank", "player_id": "Player ID", "full_name": "Player", "num_picks": "Picks"},
)[["Player", "Picks"]]

pdf_best_differential = humanise_columns(
    pdf_best_differential,
    {
        "full_name": "Player",
        "goals": "Goals",
        "name": "Manager",
        "team_name": "Team",
    },
)[["Player", "Goals", "Manager", "Team"]]

pdf_top_missed = humanise_columns(
    pdf_top_missed,
    {"full_name": "Player", "goals": "Goals"},
)[["Player", "Goals"]]


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
        value=get_weeks_of_data("actual"),
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
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from config import season_id, transfer_rules
from utils.access_code_utils import authenticate_team, load_team_access_codes
from utils.general_utils import build_weekly_rosters
from utils.transfer_utils import (
    TransferRule,
    get_active_team_transfer,
    load_transfer_records,
    record_correction,
    record_transfer,
)


st.set_page_config(page_title="Team Pics | WSL Fantasy Game", page_icon="⚽")
TRANSFER_LEDGER_PATH = Path("data/team_transfers.csv")


@st.cache_data
def load_team_picks() -> pd.DataFrame:
    picks = pd.read_csv("data/intermediate/actual/player_pics.csv")
    reference = pd.read_csv("data/input/actual/player_reference.csv")
    return picks.merge(
        reference[["full_name", "team", "player_id"]],
        on="full_name",
        how="left",
        validate="many_to_one",
    )


@st.cache_data
def load_player_reference() -> pd.DataFrame:
    return pd.read_csv("data/input/actual/player_reference.csv")


st.title("Your Team Picks")

if "team_pics_team_name" not in st.session_state:
    st.session_state["team_pics_team_name"] = None

if st.session_state["team_pics_team_name"] is None:
    with st.form("team_sign_in"):
        team_name = st.text_input("Team name")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("View team picks")

    if submitted:
        try:
            secrets_mapping = st.secrets.get("team_access_codes", {})
        except StreamlitSecretNotFoundError:
            secrets_mapping = {}

        try:
            access_codes = load_team_access_codes(secrets_mapping=secrets_mapping)
        except (FileNotFoundError, ValueError):
            st.error("Team sign-in is not configured. Contact the game administrator.")
        else:
            authenticated_team = authenticate_team(team_name, password, access_codes)
            if authenticated_team is not None:
                st.session_state["team_pics_team_name"] = authenticated_team
                st.session_state.pop("team_pics_outgoing_player_id", None)
                st.session_state.pop("team_pics_incoming_player_id", None)
                st.rerun()
            st.error("Team name or password is incorrect.")
else:
    selected_team = st.session_state["team_pics_team_name"]
    picks = load_team_picks()
    team_picks = picks[
        picks["team_name"].map(lambda value: " ".join(value.split()).casefold())
        == " ".join(selected_team.split()).casefold()
    ]
    player_reference = load_player_reference()
    players_by_id = player_reference.set_index("player_id").to_dict("index")
    current_gameweek = max(
        (
            int(path.stem.partition("_")[2])
            for path in Path("data/input/actual/player_goals").glob("GW_*.csv")
            if path.stem.partition("_")[2].isdigit()
        ),
        default=1,
    )
    active_transfer_rule = next(
        (
            TransferRule(
                season_id=rule["season_id"],
                gameweek=int(rule["gameweek"]),
                deadline_utc=rule["deadline_utc"],
                max_transfers_per_team=int(rule["max_transfers_per_team"]),
            )
            for rule in transfer_rules
            if rule["season_id"] == season_id
            and int(rule["gameweek"]) == current_gameweek
        ),
        None,
    )
    ledger_valid = True
    try:
        transfer_records = load_transfer_records(TRANSFER_LEDGER_PATH)
    except ValueError:
        transfer_records = []
        ledger_valid = False
        st.error("The transfer spreadsheet is invalid. Transfers are temporarily unavailable.")

    weekly_rosters = build_weekly_rosters(
        picks,
        TRANSFER_LEDGER_PATH,
        max_gameweek=current_gameweek,
    )
    current_roster = weekly_rosters.loc[
        (weekly_rosters["team_name"] == selected_team)
        & (weekly_rosters["gameweek"] == current_gameweek),
        ["player_id"],
    ]
    team_picks = team_picks.merge(
        current_roster,
        on="player_id",
        how="inner",
        validate="one_to_one",
    )
    team_transfer = get_active_team_transfer(transfer_records, selected_team)
    transfer_is_active = bool(
        team_transfer
        and int(team_transfer["effective_gameweek"]) <= current_gameweek
    )
    current_player_ids = team_picks["player_id"]
    roster_valid = (
        not team_picks.empty
        and not current_player_ids.isna().any()
        and not current_player_ids.duplicated().any()
        and not player_reference["player_id"].duplicated().any()
    )

    if not roster_valid:
        st.error("This roster has missing or duplicate player IDs. Transfers are blocked.")

    st.subheader(selected_team)
    if team_picks.empty:
        st.info("No player picks were found for this team.")
    else:
        display_picks = team_picks.sort_values("pick_slot").rename(
            columns={"full_name": "Player", "team": "Club"}
        )[["Player", "Club"]]
        st.dataframe(display_picks, use_container_width=True, hide_index=True)

    if team_transfer and transfer_is_active and roster_valid:
        st.success(
            f"Transfer recorded: {team_transfer['player_out_name']} out, "
            f"{team_transfer['player_in_name']} in. Effective from GW"
            f"{team_transfer['effective_gameweek']}."
        )
    elif team_transfer and not transfer_is_active:
        st.info(
            f"Transfer scheduled for GW{team_transfer['effective_gameweek']}: "
            f"{team_transfer['player_out_name']} out, "
            f"{team_transfer['player_in_name']} in."
        )
    elif not ledger_valid:
        pass
    elif roster_valid and active_transfer_rule is not None:
        st.subheader("Make a transfer")
        st.caption(
            f"{active_transfer_rule.max_transfers_per_team} transfers per team in "
            f"{active_transfer_rule.season_id}. The transfer gameweek is GW"
            f"{active_transfer_rule.gameweek}; deadline is "
            f"{active_transfer_rule.deadline_utc}."
        )
        current_player_ids = current_player_ids.tolist()
        available_players = player_reference[
            ~player_reference["player_id"].isin(current_player_ids)
        ].sort_values("full_name")

        with st.form("transfer_submission"):
            outgoing_player_id = st.selectbox(
                "Player to remove",
                options=current_player_ids,
                format_func=lambda player_id: (
                    f"{players_by_id[player_id]['full_name']} "
                    f"({players_by_id[player_id]['team']})"
                ),
                index=None,
                placeholder="Choose a player from your team",
                key="team_pics_outgoing_player_id",
            )
            incoming_player_id = st.selectbox(
                "Player to add",
                options=available_players["player_id"].tolist(),
                format_func=lambda player_id: (
                    f"{players_by_id[player_id]['full_name']} "
                    f"({players_by_id[player_id]['team']})"
                ),
                index=None,
                placeholder="Type a name to search",
                key="team_pics_incoming_player_id",
            )
            submitted = st.form_submit_button("Save transfer")

        if submitted:
            if outgoing_player_id is None or incoming_player_id is None:
                st.error("Choose one player to remove and one player to add.")
            else:
                submitted_at = datetime.now(timezone.utc)
                if not active_transfer_rule.is_open(submitted_at):
                    st.error("The transfer deadline has passed.")
                else:
                    outgoing_player = player_reference.loc[
                        player_reference["player_id"] == outgoing_player_id
                    ]
                    incoming_player = player_reference.loc[
                        player_reference["player_id"] == incoming_player_id
                    ]
                    if len(outgoing_player) != 1 or len(incoming_player) != 1:
                        st.error("The selected player IDs are not unique in the reference.")
                    else:
                        outgoing = outgoing_player.iloc[0]
                        incoming = incoming_player.iloc[0]
                        try:
                            record_transfer(
                                TRANSFER_LEDGER_PATH,
                                team_name=selected_team,
                                current_player_ids=current_player_ids,
                                player_out_id=outgoing_player_id,
                                player_out_name=outgoing["full_name"],
                                player_in_id=incoming_player_id,
                                player_in_name=incoming["full_name"],
                                player_in_club=incoming["team"],
                                effective_gameweek=active_transfer_rule.gameweek,
                                rule=active_transfer_rule,
                            )
                        except ValueError as error:
                            st.error(str(error))
                        else:
                            st.rerun()

    if team_transfer and roster_valid and active_transfer_rule is not None:
        if active_transfer_rule.is_open(datetime.now(timezone.utc)):
            correction_players = current_player_ids.tolist()
            correction_available = player_reference[
                ~player_reference["player_id"].isin(correction_players)
            ].sort_values("full_name")
            original_outgoing = team_transfer["player_out_id"]
            original_outgoing_player = player_reference.loc[
                player_reference["player_id"] == original_outgoing
            ]
            with st.form("transfer_correction"):
                correction_incoming = st.selectbox(
                    "Correct the incoming player",
                    options=correction_available["player_id"].tolist(),
                    format_func=lambda player_id: (
                        f"{players_by_id[player_id]['full_name']} "
                        f"({players_by_id[player_id]['team']})"
                    ),
                    index=None,
                )
                correction_reason = st.text_input("Reason for correction")
                correction_submitted = st.form_submit_button("Record correction")

            if correction_submitted:
                if correction_incoming is None:
                    st.error("Choose a replacement incoming player.")
                elif not correction_reason.strip():
                    st.error("Add a reason for the correction.")
                else:
                    correction_incoming_player = player_reference.loc[
                        player_reference["player_id"] == correction_incoming
                    ]
                    if len(original_outgoing_player) != 1 or len(correction_incoming_player) != 1:
                        st.error("The selected player IDs are not unique in the reference.")
                    else:
                        try:
                            record_correction(
                                TRANSFER_LEDGER_PATH,
                                team_name=selected_team,
                                current_player_ids=correction_players,
                                player_out_id=original_outgoing,
                                player_out_name=original_outgoing_player.iloc[0]["full_name"],
                                player_in_id=correction_incoming,
                                player_in_name=correction_incoming_player.iloc[0]["full_name"],
                                player_in_club=correction_incoming_player.iloc[0]["team"],
                                correction_of_transfer_id=team_transfer["transfer_id"],
                                correction_reason=correction_reason,
                                effective_gameweek=active_transfer_rule.gameweek,
                                rule=active_transfer_rule,
                            )
                        except ValueError as error:
                            st.error(str(error))
                        else:
                            st.success(
                                "Correction recorded. The original transfer remains in the audit ledger."
                            )
                            st.rerun()

    if st.button("Sign out"):
        st.session_state["team_pics_team_name"] = None
        st.session_state.pop("team_pics_outgoing_player_id", None)
        st.session_state.pop("team_pics_incoming_player_id", None)
        st.rerun()
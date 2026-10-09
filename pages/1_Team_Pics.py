from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from config import season_id, transfer_rules
from utils.access_code_utils import authenticate_team, load_team_access_codes
from utils.general_utils import build_weekly_rosters
from utils.transfer_utils import (
    filter_transfer_records_for_rules,
    format_utc_datetime,
    get_active_team_transfer,
    load_transfer_records,
    normalise_team_name,
    record_correction,
    record_transfer,
    transfer_rules_from_config,
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
    configured_transfer_rules = transfer_rules_from_config(transfer_rules)
    current_time = datetime.now(timezone.utc)
    season_transfer_rules = [
        rule for rule in configured_transfer_rules if rule.season_id == season_id
    ]
    active_transfer_rule = next(
        (
            rule
            for rule in season_transfer_rules
            if rule.is_open(current_time)
        ),
        None,
    )
    if active_transfer_rule is None:
        upcoming_rules = [
            rule
            for rule in season_transfer_rules
            if not rule.has_started(current_time)
        ]
        if upcoming_rules:
            active_transfer_rule = min(
                upcoming_rules,
                key=lambda rule: rule.start_datetime_utc,
            )
        elif season_transfer_rules:
            active_transfer_rule = max(
                season_transfer_rules,
                key=lambda rule: rule.deadline_datetime_utc,
            )
    ledger_valid = True
    try:
        transfer_records = load_transfer_records(TRANSFER_LEDGER_PATH)
        transfer_records = filter_transfer_records_for_rules(
            transfer_records,
            configured_transfer_rules,
        )
    except ValueError:
        transfer_records = []
        ledger_valid = False
        st.error("The transfer spreadsheet is invalid. Transfers are temporarily unavailable.")

    weekly_rosters = build_weekly_rosters(
        picks,
        TRANSFER_LEDGER_PATH,
        max_gameweek=current_gameweek,
        transfer_rules=configured_transfer_rules,
    )
    current_roster = weekly_rosters.loc[
        (weekly_rosters["team_name"] == selected_team)
        & (weekly_rosters["gameweek"] == current_gameweek),
        ["player_id"],
    ]
    initial_team_player_ids = team_picks["player_id"].tolist()
    team_picks = team_picks.merge(
        current_roster,
        on="player_id",
        how="inner",
        validate="one_to_one",
    )
    current_rule_records = (
        [
            record
            for record in transfer_records
            if active_transfer_rule is not None
            and record["rule_id"] == active_transfer_rule.rule_id
        ]
        if active_transfer_rule is not None
        else []
    )
    team_transfer = get_active_team_transfer(current_rule_records, selected_team)
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

    can_make_transfer_now = False
    current_date = (
        f"{current_time:%A}, {current_time.day} {current_time:%B %Y}"
    )
    st.caption(f"Current date (UTC): {current_date}")
    if active_transfer_rule is not None:
        start_display = format_utc_datetime(active_transfer_rule.start_datetime_utc)
        deadline_display = format_utc_datetime(
            active_transfer_rule.deadline_datetime_utc
        )
        st.caption(
            f"Transfer window for GW{active_transfer_rule.gameweek}: "
            f"{start_display} to {deadline_display}."
        )
        if not ledger_valid or not roster_valid:
            st.warning("Transfer status: unavailable; contact the game administrator.")
        elif not active_transfer_rule.has_started(current_time):
            st.info(
                "Transfer status: not open yet. You can make or update your transfer "
                f"from {start_display}."
            )
        elif not active_transfer_rule.is_open(current_time):
            st.info(
                f"Transfer status: closed. The deadline was {deadline_display}."
            )
        else:
            rule_transfer_count = sum(
                1
                for record in current_rule_records
                if normalise_team_name(record["team_name"])
                == normalise_team_name(selected_team)
                and record["season_id"] == active_transfer_rule.season_id
                and record["action_type"] == "transfer"
            )
            can_submit_or_update = (
                rule_transfer_count < active_transfer_rule.max_transfers_per_team
                or team_transfer is not None
            )
            can_make_transfer_now = (
                rule_transfer_count < active_transfer_rule.max_transfers_per_team
            )
            if can_submit_or_update:
                action = "update" if team_transfer is not None else "make"
                st.success(
                    f"Transfer status: open. You can {action} your transfer "
                    f"until {deadline_display}."
                )
            else:
                st.warning(
                    "Transfer status: unavailable; your transfer allowance has "
                    "been used."
                )
    else:
        st.info(
            f"Transfer status: unavailable. No transfer window is configured for "
            f"{season_id}."
        )

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
    elif (
        roster_valid
        and active_transfer_rule is not None
        and not active_transfer_rule.has_started(current_time)
    ):
        pass
    if (
        roster_valid
        and active_transfer_rule is not None
        and active_transfer_rule.is_open(current_time)
        and (can_make_transfer_now or team_transfer is not None)
    ):
        st.subheader("Update your transfer" if team_transfer else "Make a transfer")
        st.caption(
            f"{active_transfer_rule.max_transfers_per_team} transfers per team in "
            f"{active_transfer_rule.season_id} for GW"
            f"{active_transfer_rule.gameweek}."
        )
        transfer_selection_roster_ids = list(current_player_ids)
        if (
            team_transfer is not None
            and int(team_transfer["effective_gameweek"]) <= current_gameweek
            and team_transfer["player_in_id"] in transfer_selection_roster_ids
        ):
            transfer_selection_roster_ids[
                transfer_selection_roster_ids.index(team_transfer["player_in_id"])
            ] = team_transfer["player_out_id"]
        elif team_transfer is not None and not transfer_is_active:
            transfer_selection_roster_ids = initial_team_player_ids

        available_players = player_reference[
            ~player_reference["player_id"].isin(transfer_selection_roster_ids)
        ].sort_values("full_name")

        with st.form("transfer_submission"):
            outgoing_player_id = st.selectbox(
                "Player to remove",
                options=transfer_selection_roster_ids,
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
            submitted = st.form_submit_button(
                "Update transfer" if team_transfer else "Save transfer"
            )

        if submitted:
            if outgoing_player_id is None or incoming_player_id is None:
                st.error("Choose one player to remove and one player to add.")
            else:
                submitted_at = datetime.now(timezone.utc)
                if not active_transfer_rule.is_open(submitted_at):
                    st.error("The transfer window has closed.")
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
                            if team_transfer is None:
                                record_transfer(
                                    TRANSFER_LEDGER_PATH,
                                    team_name=selected_team,
                                    current_player_ids=transfer_selection_roster_ids,
                                    player_out_id=outgoing_player_id,
                                    player_out_name=outgoing["full_name"],
                                    player_in_id=incoming_player_id,
                                    player_in_name=incoming["full_name"],
                                    player_in_club=incoming["team"],
                                    effective_gameweek=active_transfer_rule.gameweek,
                                    rule=active_transfer_rule,
                                )
                            else:
                                record_correction(
                                    TRANSFER_LEDGER_PATH,
                                    team_name=selected_team,
                                    current_player_ids=transfer_selection_roster_ids,
                                    player_out_id=outgoing_player_id,
                                    player_out_name=outgoing["full_name"],
                                    player_in_id=incoming_player_id,
                                    player_in_name=incoming["full_name"],
                                    player_in_club=incoming["team"],
                                    correction_of_transfer_id=team_transfer["transfer_id"],
                                    correction_reason="Updated by team during transfer window",
                                    effective_gameweek=active_transfer_rule.gameweek,
                                    rule=active_transfer_rule,
                                )
                        except ValueError as error:
                            st.error(str(error))
                        else:
                            st.rerun()

    if st.button("Sign out"):
        st.session_state["team_pics_team_name"] = None
        st.session_state.pop("team_pics_outgoing_player_id", None)
        st.session_state.pop("team_pics_incoming_player_id", None)
        st.rerun()
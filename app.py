import streamlit as st
import pandas as pd

st.title("WSL Fantasy Game")

st.write("Welcome to the WSL Fantasy Game!")

st.header("Leaderboard")

pdf_results = pd.read_csv("data/output/actual/results.csv")

pdf_pics = pd.read_csv("data/output/actual/player_pics.csv")

pdf_goals_agg = pd.read_csv("data/output/actual/pdf_goals_agg.csv")

pdf_manager_ownership = pd.read_csv("data/output/actual/manager_ownership.csv")
st.write("Results coming soon...")

st.write(pdf_results)

st.write(pdf_pics)

st.write(pdf_goals_agg)

st.write(pdf_manager_ownership)
import streamlit as st


pages = [
    st.Page("pages/0_Overall_Results.py", title="Overall Results", default=True),
    st.Page("pages/1_Team_Pics.py", title="Team Pics"),
]

st.navigation(pages).run()

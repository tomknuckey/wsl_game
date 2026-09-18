CHECK THAT PEOPLE CAN ACTUALLY INPUT THEIR PICS ON THIS


Web App Hosting




The WSL game results will be displayed through a Streamlit web application, hosted using Streamlit Community Cloud and connected to a GitHub repository.

Setup
GitHub – stores the Python code and game data (e.g. CSV files).
Streamlit – builds the interactive web application using Python.
Streamlit Community Cloud – hosts the application and provides a public URL.
Public access – players can access the app through a normal web browser without needing GitHub, Python, or Streamlit installed.
Data Updates

Game results and player data can be updated in the GitHub repository. Changes can then be reflected in the live Streamlit application.

The intended workflow is:

Update data → Push to GitHub → Streamlit updates → Players view latest results

This provides a simple, low-cost way of maintaining a permanently accessible WSL game website.
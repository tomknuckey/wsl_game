# Web App Plan

## Current App

The Streamlit app is hosted on Streamlit Community Cloud and displays generated results reports. It is read-only: participants cannot currently submit or change their player picks through the app. See `readme.md` for the live URL and local run instructions.

The app also provides cumulative gameweek line charts for selected goal scorers and managers, defaulting to the top five of each. Manager weekly scores use the existing submitted picks for every gameweek and the same ownership-weighted scoring as the results report.

## Planned Participant Workflow

The app should eventually let participants enter their picks through a normal web browser, without needing GitHub, Python, or Streamlit installed. Before treating that work as complete, verify that a participant can actually submit a valid set of picks and that the submission is incorporated into the results pipeline.

## Data Updates And Hosting

The repository stores the Python code and game data. Updates pushed to GitHub can be deployed by Streamlit Community Cloud, allowing players to view the latest published results:

Update data and reports -> Push changes to GitHub -> Streamlit deploys -> Players view results
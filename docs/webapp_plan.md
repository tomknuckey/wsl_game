# Web App Plan

## Current App

The Streamlit app has a public Overall Results page and a Team Pics page protected by a unique team access code. Team Pics displays the team's roster and allows one one-for-one transfer, which is written to `data/team_transfers.csv` and reflected in that page's roster. The current results pipeline does not yet score transfers by gameweek, and Streamlit Community Cloud's local filesystem is not durable across restarts or redeploys. See `readme.md` for run instructions and limitations.

## Planned Participant Workflow

The transfer workflow is an initial file-backed implementation. Before treating transfer support as production-ready, move the ledger to persistent transactional storage, define the effective gameweek and deadline, and incorporate the active roster into gameweek-level scoring. Initial team creation and transfer history are still not fully modeled in persistent storage.

## Data Updates And Hosting

The repository stores the Python code and game data. Updates pushed to GitHub can be deployed by Streamlit Community Cloud, allowing players to view the latest published results:

Update data and reports -> Push changes to GitHub -> Streamlit deploys -> Players view results
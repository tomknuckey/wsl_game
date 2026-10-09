# Web App Plan

## Current App

The Streamlit app has a public Overall Results page and a Team Pics page protected by a unique team access code. Team Pics displays the team's current gameweek roster, allows one one-for-one transfer per team for the configured season, and records the transfer in `data/team_transfers.csv`. Transfers are effective from the configured gameweek and can be corrected before the deadline while preserving the original transfer as an audit row. Results are scored from gameweek-level rosters and shared goal ownership.

The CSV ledger is suitable for local inspection and testing, but Streamlit Community Cloud's local filesystem is not durable across restarts or redeploys. Transfers must not be treated as production data until the ledger moves to persistent transactional storage with backups and recovery.

## Planned Participant Workflow

The participant signs in with the team access code, views the current gameweek roster, submits one outgoing and one incoming player, and receives the effective gameweek and transfer status. The server validates roster membership, eligibility, the deadline, and the configured season transfer limit. A correction may be recorded before the deadline with a reason, but the original transfer remains in the audit ledger.

Before production use, define the persistent identity-to-team mapping, move the ledger to managed PostgreSQL or another transactional store, add deployment secrets for access codes and database credentials, and document backup and recovery procedures.

## Data Updates And Hosting

The repository stores the Python code and game data. Updates pushed to GitHub can be deployed by Streamlit Community Cloud, allowing players to view the latest published results:

Update data and reports -> Push changes to GitHub -> Streamlit deploys -> Players view results
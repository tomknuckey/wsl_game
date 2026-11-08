# Google Sheets Transfer Storage Scope

## Goal

Allow the hosted app to use a private Google Sheet for the transfer ledger, so
accepted transfers persist across Streamlit restarts and redeploys.

## In Scope

- Read and write transfer records in a configured Google Sheet.
- Store only transfer records in the Sheet. Player picks, access codes, results,
  and other data continue to use their existing files.
- Preserve the current transfer record fields, validation, transfer windows,
  limits, and correction/audit history.
- Use the Sheet as the source of truth when Google Sheets storage is enabled.
- Report a clear error if the Sheet cannot be read or written. Do not silently
  fall back to the local CSV, and report a transfer as successful only after
  the write has been confirmed.
- Keep the local CSV workflow for local development where practical, with the
  selected storage backend made explicit.
- Add the necessary dependency, focused tests using a mocked Sheets client, and
  setup and troubleshooting instructions to the README.
- Document that Google Sheets does not provide transactional guarantees for
  simultaneous submissions.

## Configuration and Credentials

- The spreadsheet must be private and shared with a Google service account.
- Store service-account credentials and spreadsheet/tab configuration in
  Streamlit secrets, not in source code or committed files.
- The project changes will not create the spreadsheet, configure a Google
  account, or handle production credentials. Those steps are performed by the
  app owner during deployment setup.
- Transfer changes stored in Google Sheets will not automatically update
  `data/input/actual/team_transfers.csv` in the GitHub repository. If the
  repository CSV should reflect the latest transfers, the app owner must
  periodically export or copy the Sheet data into that CSV and commit/push the
  update to GitHub manually.

## Out of Scope

- Using GitHub commits as the live transfer storage mechanism.
- Migrating existing CSV records automatically to Google Sheets.
- Providing database-style locking or guarantees against concurrent writes.
- Changing transfer rules, the transfer workflow, or other app behavior.

## Acceptance Criteria

- The app can load, append, and correct transfer records through the Sheets
  backend while retaining existing transfer behavior.
- Tests cover successful reads and writes, correction/audit behavior, and
  Sheets failures.
- A Sheets failure is visible to the user and cannot produce a false success or
  an unannounced local-CSV write.
- Local CSV use remains available for local development where practical.
- The README explains how to create and share the Sheet, configure Streamlit
  secrets, and diagnose common setup failures.

## Implementation Notes

- The backend is selected per source through Streamlit secrets, for example
  `actual_transfer_storage = "google_sheets"`. If not set, that source keeps
  using its local CSV.
- Existing CSV records are not imported automatically. Copy any records that
  need to remain active into the worksheet before switching backends.
- If the repository CSV needs to reflect future Sheet changes, the app owner
  must export/copy the rows to the CSV and commit/push the update manually.

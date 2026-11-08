## WSL Fantasy Game

The project processes form submissions and weekly player goals into CSV reports, then displays them in a public Overall Results page. A separate Team Pics page lets each participant enter their team name and unique four-digit access code to view that team's picks and save a one-player-out/one-player-in transfer during its configured UTC start-to-deadline window.

Actual and test access-code files are kept separately at `data/input/actual/team_access_codes.csv` and `data/input/test/team_access_codes.csv`. They are tracked in Git; anyone with repository access can read them, so they should be considered low-assurance access codes, not private credentials. For Streamlit secrets, use separate `[actual_team_access_codes]` and `[test_team_access_codes]` tables; the legacy `[team_access_codes]` table remains supported for actual only. Transfer windows, limits, and effective gameweeks are configured in `config.py`. Transfer records can use the local CSV ledger at `data/input/<data_source>/team_transfers.csv` or, when configured, a private Google Sheet. CSV writes on Streamlit Community Cloud may be discarded on restart or redeploy; Google Sheets persists records but does not provide transactional protection against simultaneous submissions. Configure the storage backend and migrate any existing CSV rows before relying on hosted transfers; setup steps are below. Run tests with `python -m unittest discover -s tests`.

Live app: <https://wslplayerpics.streamlit.app/>

## Setup

From the repository root in PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run Locally

To display the latest reports already present in `data/output/<data_source>/`
(using the `data_source` selected in `config.py`):

```powershell
streamlit run app.py
```

To regenerate reports, run the pipeline stages in order:

```powershell
python 1_prepare_forms.py
python 2_output_results.py
```

To prepare and regenerate the isolated test data without changing `config.py` or
the actual reports:

```powershell
python 1_prepare_forms.py --data-source test
python 2_output_results.py --data-source test
```

The first stage reads form responses and player reference data from `data/input/<data_source>/` and writes cleaned picks to `data/intermediate/<data_source>/`. The second stage reads those picks and the weekly goals, then writes reports to `data/output/<data_source>/`.

The selected data source and other pipeline options are in `config.py`; it currently selects `actual`. The optional `--data-source` argument overrides only the source for that pipeline run. Check the selected output directory before running the pipeline: its generated CSVs may be replaced.

## Persistent Transfer Storage With Google Sheets

Only the transfer ledger is stored in Google Sheets. Player picks, access codes,
results, and other project data continue to use their existing CSV files.
Without an `actual_transfer_storage` setting, the app uses the local actual
transfer CSV. To enable the Sheet for the hosted actual game, set
`actual_transfer_storage = "google_sheets"` in Streamlit Cloud's app secrets.
The test source remains on its CSV unless `test_transfer_storage` is separately
configured.

Follow these steps to enable persistent storage for the hosted actual game:

1. **Deploy the integration code.** Commit the code changes, open a pull
   request, merge it into the branch used by Streamlit Cloud, and wait for the
   app to deploy. The live app cannot use Sheets until this code is deployed.
2. **Create the spreadsheet.** Create a private Google spreadsheet and name its
   first worksheet tab `Transfers`. Keep general access restricted. Copy the
   spreadsheet ID from its URL (the text between `/d/` and `/edit`).
3. **Set up Google API access.** In Google Cloud Console, select or create a
   project, enable the **Google Sheets API**, and create a service account.
   Create a JSON key for the account and save it somewhere private. Do not
   commit or share the JSON key. This integration only needs the Sheets API.
4. **Share the spreadsheet with the service account.** Find the service
   account's `client_email` in its JSON key. In the spreadsheet's **Share**
   dialog, add that email as an **Editor**, while keeping general access
   restricted.
5. **Preserve any existing transfers if needed.** If the local
   `data/input/actual/team_transfers.csv` has records that should be kept, copy
   its header and rows into the `Transfers` worksheet before switching storage.
   The integration does not migrate CSV records automatically. If there are no
   transfers to preserve, leave the worksheet empty; the app creates the
   header row when it first connects.
6. **Add secrets in Streamlit Cloud.** Open the app's **Manage app → Settings
   → Secrets** and add the following TOML, replacing every placeholder with
   the corresponding value from the spreadsheet URL and service-account JSON.
   Do not add these credentials to a repository file or pull request:

```toml
actual_transfer_storage = "google_sheets"

[google_sheets]
spreadsheet_id = "YOUR_SPREADSHEET_ID"
worksheet = "Transfers"

[google_service_account]
type = "service_account"
project_id = "YOUR_PROJECT_ID"
private_key_id = "YOUR_PRIVATE_KEY_ID"
private_key = """-----BEGIN PRIVATE KEY-----
PASTE_THE_COMPLETE_PRIVATE_KEY_HERE
-----END PRIVATE KEY-----
"""
client_email = "YOUR_SERVICE_ACCOUNT_EMAIL"
client_id = "YOUR_CLIENT_ID"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "YOUR_CLIENT_CERTIFICATE_URL"
universe_domain = "googleapis.com"
```

7. **Restart and verify the app.** Save the secrets and reboot/redeploy the
   Streamlit app if it does not restart automatically. Confirm the Team Pics
   page loads without a transfer-storage error. The Sheet should now contain
   the transfer-column header. Do not submit a test transfer using a real
   participant's team unless you intend to save it.

The Sheet is the source of truth when selected. The app confirms each appended
row by reading it back and displays storage errors rather than falling back to
the CSV. If setup fails, verify the spreadsheet ID, exact worksheet tab name,
service-account JSON values, enabled Sheets API, and Editor sharing permission.
The app does not update GitHub: if the repository CSV should reflect new
transfers, periodically export/copy the Sheet rows into
`data/input/actual/team_transfers.csv` and commit/push that change manually.

Google Sheets is not a transactional database. Near-simultaneous submissions
could race during transfer-limit checks, so the app is suitable for the game's
low-volume use but does not guarantee concurrent-write serialization.

The output includes `manager_player_gameweek_points.csv` (one row per manager, rostered player, and gameweek with data) and `manager_player_points.csv` (the same player contributions summed over the season). A zero in the `goals` column means that player earned no points that week; shared goal credit is divided between managers who own the player that week.

The test source includes a sample transfer for Chelsea Dagger: Vivianne Miedema out and Océane Hurtré in, submitted during GW4 and effective from GW5. Its GW5 goals data includes Hurtré, so Tom Knuckey's player-by-week report shows the GW5 contribution.

## Optional ESPN Data

Generate prior-season scorer data from ESPN:

```powershell
python 3_generate_espn_data.py
```

The script validates ESPN's completed 2025-26 WSL match summaries and saves prior-season non-own-goal scorer totals to `data/intermediate/<data_source>/espn_goals.csv`. Check `config.py` before running it because the selected data source determines which intermediate file is replaced. Player-description generation has been retired; see [player description experiment learnings](docs/player_description_experiment.md) for the observed results and notes for any future attempt.

## Input Data

Each data source has `form_response.csv`, `player_reference.csv`, and a `player_goals/` directory under `data/input/<data_source>/`. Use the stable `player_id` from the reference data to identify players across files.

Add one goals CSV per gameweek under `data/input/<data_source>/player_goals/`, named `GW_<number>.csv` (for example, `GW_5.csv`). The filename supplies the gameweek, so no `week` column is needed. Use `player_id` and an optional `goals` column:

```csv
player_id,goals
WSL_0001,
WSL_0002,2
WSL_0003,3
```

A blank `goals` value, or an omitted `goals` column, counts as one goal. Enter `2`, `3`, or another count only when a player scored multiple goals.

## Project Notes

- [Web app plan](docs/webapp_plan.md): current app status and planned participant-input workflow.
- [Google Sheets transfer storage scope](docs/google_sheets_transfer_storage_scope.md): implementation scope and storage behavior.
- [Project plan](docs/plan_2026_09_17.md): priorities and outstanding improvements.
- [Player description experiment learnings](docs/player_description_experiment.md): what the local LLM attempt showed and how to approach it if resumed.
- [Copilot project guidance](.github/copilot-instructions.md): concise repository context and working rules.
- [Pipeline guidance](.github/instructions/data-pipeline.instructions.md) and [Streamlit guidance](.github/instructions/streamlit.instructions.md): task-scoped AI instructions.

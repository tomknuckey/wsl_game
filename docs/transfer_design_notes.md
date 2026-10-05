# Transfer Feature Design Notes

## Current Project Shape

The project currently has a batch data pipeline, a public Overall Results page, and a separate Team Pics page gated by team name and a unique four-digit access code:

1. `1_prepare_forms.py` cleans form responses and writes long-form player picks.
2. `2_output_results.py` joins picks to player reference data and gameweek goals, then writes aggregate CSV reports.
3. The Overall Results page displays public reports. The Team Pics page shows a team's picks, allows one saved one-player-out/one-player-in transfer per team, and records it in `data/team_transfers.csv`. The updated roster appears on Team Pics; scoring reports are not recalculated from the transfer yet.

Player reference data has stable `player_id` values, but submitted picks are initially represented by player names. Managers are identified by submitted name and team name, rather than stable account IDs. Goal inputs are stored separately by gameweek, but the scoring helper aggregates goals across weeks before calculating manager results.

## Incremental Delivery

Build this in three small stages, validating each before adding the next.

### 1. Let Users Sign In

The app needs a simple way to select the participant's team. After the participant signs in, immediately show that team's current roster so they can confirm they are looking at the right one. Keep the public results page available without sign-in if desired; require sign-in before showing team-specific controls.

A simple PIN or access code sent to each participant individually is likely proportionate for this low-stakes game. A two-digit PIN is easy to share and guess, so treat it as a convenience gate rather than strong identity verification; anyone who knows another person's code may be able to access their team. If that risk is acceptable, keep the first version simple. A unique code per participant is preferable to one shared code, and it can later be replaced by provider sign-in without changing the team and transfer model.

For the first stage, acceptance means a participant can enter their code, the app resolves and displays the associated team and current roster, and no transfer writes are needed yet.

### 2. Collect One Outgoing And Incoming Player

With the roster already visible, collect one player to remove and one to add. Use a selectbox for the outgoing player, limited to the current roster. For the incoming player, use Streamlit's searchable selectbox over eligible players, excluding players already on that team. This is easier and less error-prone than free-text names when the player list is large. Store or submit stable `player_id` values, while displaying player names and clubs.

Validate that the outgoing player belongs to the signed-in team's roster and the incoming player is eligible and not already selected. The current page immediately saves the explicitly submitted one-for-one transfer and allows only one transfer per team.

### 3. Save The Transfer And Use It In Results

Save the submitted transfer in the CSV ledger, tied to the team selected by the access code. Once saved, show the updated roster and transfer status back to the user. The ledger write enforces the one-transfer limit; hiding the form after submission is not the only enforcement.

For a transfer effective from GW10, preserve the roster used in each gameweek: GW1-GW9 use the original picks, and GW10 onward use the roster after the transfer. Goal inputs are already stored by gameweek, but `generate_goals()` currently aggregates them before manager scoring. Change scoring to calculate from gameweek-level goals and the roster active in that week. Ownership and differential reports may also need to use weekly rosters rather than season-wide ownership.

The existing scoring calculation shares each player's goals among managers who picked them. Decide whether sharing should be calculated separately per gameweek or whether managers should receive the full goals scored by each selected player.

## Configurable Rules

Make these settings configurable for each game or season:

- gameweek the transfer applies from (for example, GW10)
- submission deadline, including its timezone
- maximum number of transfers allowed per team

For the first version, a small settings section in `config.py` is proportionate. Keep the transfer and deadline rules in one place and pass them to validation; avoid adding a general configuration framework. Later, settings can move into a database or admin interface if they need to change while the app is running.

Clarify whether the configured transfer count is for the season or per gameweek. The initial roster and accepted transfers together should determine the roster for every week.

## Data Model And Migration Away From Google Forms

The goal is to stop using Google Forms for team creation and transfer changes. The existing form response data can be used once to create/import each team's initial roster. After that, the app should be the participant-facing path for future changes. This avoids requiring a manager to re-enter their five initial picks merely to make a transfer.

Keep the first version small and use the existing player IDs:

- `users`: stable participant ID and access-code mapping; display name is an attribute, not the team's database key. A future identity provider can map its verified subject to this stable participant ID.
- `seasons`: season identifier, to keep teams and transfers scoped to a season.
- `teams`: stable team ID, season, owner user ID, and team name. Start with one team per user per season unless the rules require otherwise.
- `players`: continue to use the existing `player_id`; the current reference sheet can remain the source during the initial transition.
- `gameweeks`: season and week number. Transfer gameweek/deadline can initially come from `config.py` rather than requiring a gameweek table.
- `initial_picks`: the five player IDs selected for a team's starting roster.
- `transfers`: team ID, outgoing player ID, incoming player ID, effective gameweek, and submission time. Enforce the configured transfer limit in the save path and, where practical, with database constraints.

For one transfer, derive each week's roster from the initial picks and the transfer record. This avoids maintaining a second, potentially inconsistent copy of the current roster. A larger roster-history model can wait until the rules require multiple or more complex transfers.

## Storage Recommendation

Continue using CSVs for gameweek goal inputs, the player reference during the transition, and generated reports. They are easy to inspect and fit the existing reporting pipeline.

The current requested transfer ledger is a CSV at `data/team_transfers.csv`. This is simple and inspectable for local use, and the app prevents a second transfer per team while running as a single process. CSV writes are not transactional across multiple app instances and Streamlit Community Cloud's local filesystem is not durable across restarts or redeploys. Before relying on transfers in the hosted game, move the ledger to persistent transactional storage such as managed PostgreSQL; do not treat the deployed CSV as durable backup.

There is no need to migrate every existing dataset into the database. A small database-backed transfer workflow can coexist with the CSV reporting pipeline.

## Authentication And Authorization

The current public app can remain read-only for everyone, with a code required for the transfer workflow. Map each code to a stable participant/team record. The chosen low-friction code is an access convenience, not strong authentication, so participants should understand that sharing or guessing a code may allow access to that team's controls.

The interim Team Pics page uses a distinct four-digit access code for each team alongside a team-name lookup. This is only a basic access barrier: four-digit codes can be guessed or shared, and it does not verify participant identity. The access-code spreadsheet is tracked in Git at the user's request, so anyone with repository access can see the codes. The public results page remains available without sign-in.

Keep database credentials in deployment secrets, not in the repository. Avoid publishing private email or contact details in output reports. To make later scaling straightforward, keep the access-code-to-team lookup and all transfer validation on the server, use stable IDs rather than names in stored records, and avoid storing writable state in local files or Streamlit session state.

The current Streamlit Community Cloud deployment can remain part of the process, but self-service transfers require an access check and a persistent write store in addition to the current CSV-only setup. The low-assurance code approach is the simplest first step; stable participant IDs and a clear storage boundary leave room to adopt stronger sign-in if the game grows.

## Likely Refactoring Areas

1. Add a simple access-code check and server-side participant-to-team mapping; show the linked team's current roster immediately after access.
2. Add a searchable incoming-player control and outgoing-player control based on the signed-in user's roster.
3. Put transfer validation and roster rules in small, testable functions, separate from Streamlit widgets and database access.
4. Add a thin persistence boundary for transfer reads and writes; keep the Streamlit page focused on presentation.
5. Replace Google Forms as the ongoing team-change mechanism, importing existing form responses as initial rosters.
6. Preserve gameweek-level goals and calculate points against the roster active in each week.
7. Add focused tests for identity/team authorization, transfer limits, deadlines, roster membership, valid incoming/outgoing players, and GW9 versus GW10 scoring.

The main scoring and dataframe helpers currently live together in `utils/general_utils.py`. Refactor the touched behavior as the transfer work is implemented; avoid a broad rewrite of unrelated pipeline code.

## Decisions To Make Before Implementation

- Does a transfer submitted before the GW10 deadline apply from GW10 onward?
- Is a submitted transfer final, or may it be edited or replaced before the deadline?
- Is the transfer limit per team per season, or per manager across seasons? It will be configurable, but its scope still needs defining.
- How are goals shared when multiple managers own the same scorer: separately per gameweek, or by another rule?
- Is the low-assurance access code acceptable for this game's privacy expectations, and should each participant have a unique code?
- What timezone defines the configured deadline?
- Are initial rosters imported from the current Google Form responses, and who verifies the identity-to-team mapping?
- Is a submitted transfer final, or may it be edited or replaced before the deadline?
- Who can correct a mistaken transfer, and how should corrections be recorded?
- What backup and recovery process is appropriate for the hosted transfer data?

## Documentation Follow-Up

Update `webapp_plan.md` to describe the authenticated transfer workflow, persistent data store, identity-to-team mapping, secrets, and backup approach. Keep the project plan's gameweek-history requirement, and link this document from the plan so the scoring and data-model decisions remain easy to find.
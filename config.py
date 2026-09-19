# Data source directory name
#data_source: str = "test"
data_source = "actual"
# Entries submitted after this deadline are excluded from the results
submission_deadline: str = "03/09/2026 20:00:00"

# If True, exclude submitters whose name starts with any of these prefixes
exclude_name_prefixes_flag: bool = True
exclude_name_prefixes: list = ["TEMP"]

manual_renaming_flag: bool = True

#If True, fill invalid picks with random players from the list below
player_fill_flag: bool = True

players_to_fill_with: list = ["Khadija Shaw", "Alessia Russo", "Kirsty Hanson",
"Stina Blackstenius", "Vivianne Miedema"]

#Maximum Number of gameweeks to filter on
max_gw = 30

# Manual mapping of player name corrections
# Use exact matches on the cleaned `full_name` field in the long-form dataframe.
MANUAL_RENAMES = {
    "Laura James": "Lauren James",
    "Bunny Shaw": "Khadija Shaw",
    "Viviane Miedema": "Vivianne Miedema",
    "Nadia krezyman": "Nadia Krezyman"
}
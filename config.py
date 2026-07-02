# Data source directory name
data_source: str = "test"

# Entries submitted after this deadline are excluded from the results
submission_deadline: str = "02/09/2026 20:00:00"

manual_renaming_flag: bool = True

#If True, fill invalid picks with random players from the list below
player_fill_flag: bool = True

players_to_fill_with: list = ["Khadija Shaw", "Alessia Russo", "Kirsty Hanson",
"Stina Blackstenius", "Vivianne Miedema"]

#Maximum Number of gameweeks to filter on
max_gw = 30
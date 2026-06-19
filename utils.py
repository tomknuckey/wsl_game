import pandas as pd
from typing import Any


def rename_form_columns(pdf: pd.DataFrame) -> pd.DataFrame:
    """Rename form response columns to standard names.
    
    Args:
        pdf: DataFrame with form response data
        
    Returns:
        DataFrame with renamed columns
    """
    return pdf.rename(
        columns={
            "Player 1 \r\nEnter full player name exactly as shown in the reference sheet (INSERT LINK)": "player_1",
            "Player 2": "player_2",
            "Player 3": "player_3",
            "Player 4": "player_4",
            "Player 5": "player_5",
            "Your Full Name": "name",
            "Timestamp": "timestamp",
        }
    )


def form_to_long(pdf: pd.DataFrame) -> pd.DataFrame:
    """Convert form data from wide to long format.
    
    Args:
        pdf: DataFrame in wide format with player picks
        
    Returns:
        DataFrame in long format with one pick per row
    """
    return pdf.melt(
        id_vars=["timestamp", "name"],
        value_vars=["player_1", "player_2", "player_3", "player_4", "player_5"],
        var_name="pick_slot",
        value_name="full_name",
    )


def clean_form_data(pdf: pd.DataFrame) -> pd.DataFrame:
    """Clean form data by removing NaN values and stripping whitespace.
    
    Args:
        pdf: DataFrame with form data
        
    Returns:
        Cleaned DataFrame
    """
    pdf = pdf.dropna(subset=["full_name"])
    pdf["full_name"] = pdf["full_name"].str.strip()
    return pdf


def number_of_pics(pdf: pd.DataFrame) -> pd.DataFrame:
    """Count the number of picks per player.
    
    Args:
        pdf: DataFrame with player pick data
        
    Returns:
        DataFrame with player_id and num_picks columns
    """
    return (
        pdf.groupby("player_id")[["name"]]
        .count()
        .reset_index()
        .rename(columns={"name": "num_picks"})
    )


def adjust_goals(pdf: pd.DataFrame) -> pd.DataFrame:
    """Adjust goals by normalizing by number of picks.
    
    Args:
        pdf: DataFrame with goals and num_picks columns
        
    Returns:
        DataFrame with adjusted goals column
    """
    pdf["goals"] = pdf["goals"].fillna(0)

    pdf["adjusted_goals "] = pdf["goals"] / pdf["num_picks"]

    return pdf


def generate_results(pdf: pd.DataFrame) -> pd.DataFrame:
    """Generate summary results grouped by name and sorted by goals.
    
    Args:
        pdf: DataFrame with combined pick and goals data
        
    Returns:
        DataFrame with total goals per person, sorted descending
    """
    return (
        pdf.groupby("name")["goals"]
        .sum()
        .reset_index()
        .sort_values(by="goals", ascending=False)
    )

# -*- coding: utf-8 -*-
# !/usr/bin/env python

"""Helper functions for generating analysis from TRI data."""


import pandas as pd


def get_waste_management_summary(full_df: pd.DataFrame) -> pd.DataFrame:
    """Generate a summary DataFrame showing the total amount for incineration, landfilling, recycling, and POTW.

    Args:
        full_df (pd.DataFrame): The full DataFrame containing TRI records.

    Returns:
        pd.DataFrame: A summary DataFrame showing the total amount for each waste management type.

    """
    # Filter and summarize the data for the specified waste management types
    summary_df = (
        full_df.melt(
            id_vars=["TRIFID", "Amount [kg/yr]"],  # Retain TRIFID and amount for grouping
            value_vars=["Is Incineration", "Is Landfilling", "Is Recycling", "Is POTW"],
            var_name="Waste Management Type",
            value_name="Flag",
        )
        .query("Flag == True")  # Only include rows where the flag is True
        .groupby("Waste Management Type", as_index=False)
        .agg({"Amount [kg/yr]": "sum"})  # Aggregate the amount
    )

    # Format the waste management type names for better readability
    summary_df["Waste Management Type"] = summary_df["Waste Management Type"].str.replace("Is ", "", regex=False)

    return summary_df


def calculate_highest_potential_combinations(full_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate the highest-potential combination for each waste management type.

    Args:
        full_df (pd.DataFrame): The full DataFrame containing TRI records.

    Returns:
        pd.DataFrame: DataFrame with the highest-potential combination for each management type.

    """
    # Define waste management types and their corresponding flags
    management_types = {
        "POTW": "Is POTW",
        "Incineration": "Is Incineration",
        "Recycling": "Is Recycling",
        "Landfilling": "Is Landfilling",
    }

    # Initialize an empty list to store results
    results = []

    # Process each waste management type
    for management_name, flag in management_types.items():
        # Filter records for the current management type
        filtered_df = full_df[full_df[flag] == True]

        # Group by Chemical Activity, Generator Sector, and Waste Handler
        grouped = (
            filtered_df.groupby(
                ["Chemical Activity", "Generator NAICS Code", "Waste Handler NAICS Code"],
                as_index=False,
            )
            .agg(
                {
                    "Amount [kg/yr]": "sum",  # Total amount
                    "TRIFID": "count",  # Number of records
                }
            )
            .rename(columns={"TRIFID": "Number of Records"})
        )

        # Calculate the potential
        grouped["Potential"] = grouped["Number of Records"] * grouped["Amount [kg/yr]"]

        # Add the management type column for identification
        grouped["Waste Management Type"] = management_name

        # Select the row with the highest potential
        if not grouped.empty:
            max_potential_row = grouped.loc[grouped["Potential"].idxmax()]
            results.append(max_potential_row)

    # Combine results into a single DataFrame
    final_df = pd.DataFrame(results)

    return final_df


def select_post_recycling_use(
    recycling_df: pd.DataFrame,
    df_industrial: pd.DataFrame,
    df_commercial: pd.DataFrame,
) -> pd.DataFrame:
    """Select the most promising post-recycling use based on NAICS code reliability and potential.

    Args:
        recycling_df (pd.DataFrame): DataFrame containing recycling records.
        df_industrial (pd.DataFrame): DataFrame containing industrial records.
        df_commercial (pd.DataFrame): DataFrame containing commercial records.

    Returns:
        pd.DataFrame: DataFrame with the most promising post-recycling uses for each recycling record.

    """
    # Add "Type of Use" column to industrial uses
    df_industrial["Type of Use"] = "Industrial"

    # Combine industrial and commercial uses into a single DataFrame
    uses_df = pd.concat([df_industrial, df_commercial], ignore_index=True)

    def calculate_reliability(handler_naics, use_naics):
        """Calculate reliability score based on NAICS code match."""
        if pd.isna(handler_naics) or pd.isna(use_naics):
            return 1  # Minimal reliability if NAICS is missing

        handler_naics = str(handler_naics).zfill(6)
        use_naics = str(use_naics).zfill(6)

        # Compare NAICS codes digit by digit
        for level in range(6, 0, -1):
            if handler_naics[:level] == use_naics[:level]:
                return level
        return 1

    # Initialize results
    results = []

    # Iterate through each recycling record
    for _, recycling_row in recycling_df.iterrows():
        handler_naics = recycling_row["Waste Handler NAICS Code"]
        n_records = recycling_row["Number of Records"]
        filtered_uses = uses_df.copy()

        # Add reliability score for each use
        filtered_uses["Reliability"] = filtered_uses["Industry NAICS Code"].apply(
            lambda use_naics: calculate_reliability(handler_naics, use_naics)
        )

        # Calculate potential for each use
        filtered_uses["Percentage"] = filtered_uses["Percentage"].fillna(1)  # Default percentage
        filtered_uses["Potential"] = filtered_uses["Reliability"] * n_records * filtered_uses["Percentage"]

        # Find the most promising use
        if not filtered_uses.empty:
            max_potential_row = filtered_uses.loc[filtered_uses["Potential"].idxmax()]
            max_potential_row["Waste Handler NAICS Code"] = handler_naics
            max_potential_row["Number of Records"] = n_records
            results.append(max_potential_row)

    # Combine results into a single DataFrame
    final_df = pd.DataFrame(results)

    # Select relevant columns for the final output
    relevant_columns = [
        "Waste Handler NAICS Code",
        "Industry NAICS Code",
        "Reliability",
        "Percentage",
        "Number of Records",
        "Potential",
        "Type of Use",
        "Industrial Process Type",  # If applicable
        "Product Category",  # If applicable
        "Function Category",  # If applicable
    ]
    return final_df[relevant_columns]

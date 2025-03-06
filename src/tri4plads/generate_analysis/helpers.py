# -*- coding: utf-8 -*-
# !/usr/bin/env python

"""Helper functions for generating analysis from TRI data."""

import os
import random
from typing import List, Optional, Tuple

import matplotlib.cm as cm
import pandas as pd
import requests
from dotenv import load_dotenv
from plotly import graph_objects as go


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
    selected_additives: Optional[List[str]],
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

    # Filter uses based on selected additives
    if selected_additives:
        uses_df = uses_df[uses_df["TRI Chemical ID"].isin(selected_additives)]

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
        filtered_uses["Percentage"] = filtered_uses["Percentage"].fillna(filtered_uses["Percentage"].mean())
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


def identify_preferred_entities(df: pd.DataFrame) -> Tuple[str, str]:
    # Create an auxiliary column "Number of Records"
    df["Number of Records"] = 1

    print(df["Is Recycling"].value_counts())

    df.loc[df["Is On-Site"] == 1, "Waste Handler NAICS Title"] = df.loc[df["Is On-Site"] == 1, "Generator NAICS Title"]

    # Compute sum("Amount [kg/yr]") * sum("Number of Records") for each category
    chemical_activity_potential = df.groupby("Chemical Activity").agg({"Amount [kg/yr]": "sum", "Number of Records": "sum"})
    chemical_activity_potential["Potential"] = (
        chemical_activity_potential["Amount [kg/yr]"] * chemical_activity_potential["Number of Records"]
    )

    waste_handler_naics_title_potential = (
        df.loc[df["Is Recycling"] == 1]
        .groupby("Waste Handler NAICS Title")
        .agg({"Amount [kg/yr]": "sum", "Number of Records": "sum"})
    )
    waste_handler_naics_title_potential["Potential"] = (
        waste_handler_naics_title_potential["Amount [kg/yr]"] * waste_handler_naics_title_potential["Number of Records"]
    )

    # Get the most important category based on max potential
    most_important_chemical_activity = chemical_activity_potential["Potential"].idxmax()
    most_important_waste_handler_naics_title = waste_handler_naics_title_potential["Potential"].idxmax()

    return most_important_chemical_activity, most_important_waste_handler_naics_title  # type: ignore [reportReturnType]


def identify_most_important_graph_elements(
    df: pd.DataFrame,
    plastic_related_code: List[str],
) -> pd.DataFrame:
    """Processes the input DataFrame to update specified columns based on conditions.

    Parameters:
    - df (pd.DataFrame): Input DataFrame with required columns.

    Returns:
    - pd.DataFrame: Updated DataFrame with transformations applied.
    - List[str]: List of plastic related NAICS codes.

    """
    management_types = {
        "POTW": "Is POTW",
        "Incineration": "Is Incineration",
        "Recycling": "Is Recycling",
        "Landfilling": "Is Landfilling",
    }

    most_important_chemical_activity, most_important_waste_handler_naics_title = identify_preferred_entities(df)

    # Update "Chemical Activity" column
    df["Chemical Activity"] = df["Chemical Activity"].apply(
        lambda x: x if x == most_important_chemical_activity else "Other conditions of use"
    )

    # Update "Generator NAICS Title" column
    df["Generator NAICS Title"] = df["Generator NAICS Code"].apply(
        lambda x: "Plastic-related sectors" if x in plastic_related_code else "Other generator sectors"
    )

    # Handle "Waste Handler NAICS Title" based on "Is Recycling" column

    df["Waste Handler NAICS Title"] = df.apply(  # type: ignore [reportCallIssue]
        lambda row: (  # type: ignore [reportArgumentType]
            "Other recycling sectors"
            if row["Is Recycling"] == 1 and row["Waste Handler NAICS Title"] != most_important_waste_handler_naics_title
            else None if row["Is Recycling"] == 0 else row["Waste Handler NAICS Title"]
        ),
        axis=1,
    )

    def assign_management_type(row):
        for management_type, column in management_types.items():
            if row[column] == 1:
                return management_type
        if row["Management Type"] == "Treatment":
            return "Other treatment"
        return "Other disposal"

    df["Management Type"] = df.apply(assign_management_type, axis=1)

    selected_columns = [
        "Generator NAICS Title",
        "Waste Handler NAICS Title",
        "Management Type",
        "Amount [kg/yr]",
        "Chemical Activity",
    ]

    return df[selected_columns]


def generate_sankey(df: pd.DataFrame):
    """
    Generates a Sankey diagram where the edge color corresponds to the source node's color.
    """

    labels = []
    source = []
    target = []
    values = []
    colors = {}
    source_label_tracker = {}
    link_colors = []

    colormap = cm.get_cmap("tab20c", 20)  # Use a larger qualitative colormap (tab20)
    used_colors = set()  # Keep track of used colors to ensure uniqueness

    def generate_label(target_label, value):
        percentage = (value / total) * 100
        formatted_target_label = f"""{target_label}<br>({percentage:.2e} %)"""
        return formatted_target_label

    def get_unique_color(index):
        available_indices = list(set(range(20)) - used_colors)
        if not available_indices:
            used_colors.clear()  # Reset if exhausted
            available_indices = list(range(20))
        chosen_index = random.choice(available_indices)
        used_colors.add(chosen_index)
        rgba = colormap(chosen_index)
        return f"rgba({int(rgba[0] * 255)}, {int(rgba[1] * 255)}, {int(rgba[2] * 255)}, 0.6)"

    def add_link(
        source_label,
        target_label,
        value,
        is_cou=False,
    ):
        source_label = (
            source_label.replace("_", " ").capitalize()
            if "POTW" not in source_label and "PMMA" not in source_label
            else source_label
        )
        target_label = (
            target_label.replace("_", " ").capitalize()
            if "POTW" not in target_label and "PMMA" not in target_label
            else target_label
        )

        if source_label not in colors:
            colors[source_label] = get_unique_color(len(colors))

        if target_label not in colors:
            colors[target_label] = get_unique_color(len(colors))

        if source_label not in labels:
            labels.append(source_label)

        if target_label not in labels:
            labels.append(target_label)

        if target_label not in source_label_tracker:
            source_label_tracker[target_label] = value
        else:
            source_label_tracker[target_label] += value

        if is_cou:
            if source_label not in source_label_tracker:
                source_label_tracker[source_label] = value
            else:
                source_label_tracker[source_label] += value

        source.append(labels.index(source_label))
        target.append(labels.index(target_label))
        values.append(value)
        link_colors.append(colors[source_label])  # Edge color based on source node color

    min_value = df["Amount [kg/yr]"].min()
    max_value = df["Amount [kg/yr]"].max()
    df["Amount [kg/yr]"] = (df["Amount [kg/yr]"] - min_value) / (max_value - min_value)
    total = df["Amount [kg/yr]"].sum()

    for (chemical_activity, generator_naics), group in df.groupby(["Chemical Activity", "Generator NAICS Title"]):
        add_link(
            chemical_activity,
            generator_naics,
            group["Amount [kg/yr]"].sum(),
            is_cou=True,
        )

    recycling_df = df[df["Management Type"] == "Recycling"]
    for (generator_naics, waste_handler), group in recycling_df.groupby(["Generator NAICS Title", "Waste Handler NAICS Title"]):
        if pd.notna(waste_handler):
            add_link(generator_naics, waste_handler, group["Amount [kg/yr]"].sum())

    non_recycling_df = df[df["Management Type"] != "Recycling"]
    for (generator_naics, management_type), group in non_recycling_df.groupby(["Generator NAICS Title", "Management Type"]):
        add_link(generator_naics, management_type, group["Amount [kg/yr]"].sum())

    for (waste_handler, management_type), group in recycling_df.groupby(["Waste Handler NAICS Title", "Management Type"]):
        if pd.notna(waste_handler):
            add_link(waste_handler, management_type, group["Amount [kg/yr]"].sum())

    total_potw_mass = df[df["Management Type"] == "POTW"]["Amount [kg/yr]"].sum()
    potw_to_landfill_mass = total_potw_mass * 0.011095
    if total_potw_mass > 0:
        landfill_from_potw_label = "Landfilling (from POTW)"
        add_link("POTW", landfill_from_potw_label, potw_to_landfill_mass)

    plastic_recycling_df = df[
        (df["Generator NAICS Title"] == "Plastic-related sectors") & (df["Management Type"] == "Recycling")
    ]
    for _, row in plastic_recycling_df.iterrows():
        mass_mma = row["Amount [kg/yr]"]
        pmma_recycling_label = "PMMA Recycling"
        potw_from_pmma_label = "POTW (from PMMA Recycling)"
        post_recycling_use = "Used as multipurpose adhesive"

        mma_to_potw_mass = 0.000081 * mass_mma
        add_link("Recycling", pmma_recycling_label, mass_mma)
        add_link(pmma_recycling_label, potw_from_pmma_label, mma_to_potw_mass)
        post_recycling_mass = (2 / 3) * mass_mma
        add_link(pmma_recycling_label, post_recycling_use, post_recycling_mass)

    non_plastic_recycling_df = df[
        (df["Generator NAICS Title"] != "Plastic-related sectors") & (df["Management Type"] == "Recycling")
    ]
    for _, row in non_plastic_recycling_df.iterrows():
        recycling_mass = row["Amount [kg/yr]"]
        plastics_sector_label = "Plastics material and resin manufacturing sector"
        processing_reactant_label = "Processing as a reactant"
        monomers_label = "Monomers"

        add_link("Recycling", plastics_sector_label, recycling_mass)
        add_link(plastics_sector_label, processing_reactant_label, recycling_mass)
        add_link(processing_reactant_label, monomers_label, recycling_mass)

    fig = go.Figure(
        go.Sankey(
            valueformat=".0f",
            valuesuffix="kg/yr",
            node=dict(
                pad=15,
                thickness=15,
                line=dict(color="black", width=0.5),
                label=[generate_label(label, source_label_tracker[label]) for label in labels],
                color=[colors[label] for label in labels],
                hoverlabel=dict(font=dict(size=15, family="Arial", weight="bold")),
            ),
            link=dict(arrowlen=15, source=source, target=target, value=values, color=link_colors),
        )
    )

    fig.update_layout(font=dict(size=18, family="Arial", weight="bold"))
    fig.show()


class EPAProductDataClient:
    """Client to interact with the EPA CompTox Exposure Data API."""

    BASE_URL = "https://api-ccte.epa.gov/exposure/product-data"

    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("COMPTOX_API_KEY")
        self.headers = {"accept": "application/json", "x-api-key": self.api_key}

    def get_product_data_by_dtxsid(self, dtxsid: str) -> dict:
        """
        Retrieve product data for a given DTXSID.

        :param dtxsid: The DTXSID to search for.
        :return: The API response as a dictionary.
        """
        url = f"{self.BASE_URL}/search/by-dtxsid/{dtxsid}"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data for DTXSID {dtxsid}: {e}")
            return {}


if __name__ == "__main__":

    client = EPAProductDataClient()

    dtxsid = "DTXSID1042152"  # Example DTXSID for testing
    data = client.get_product_data_by_dtxsid(dtxsid)

    if data:
        print("Product Data:", data)
    else:
        print("No data found or an error occurred.")

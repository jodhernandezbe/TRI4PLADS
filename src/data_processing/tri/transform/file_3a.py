# -*- coding: utf-8 -*-
# !/usr/bin/env python

"""Module for transforming TRI Form R (3A) data files.

This module defines the `TriFile3aTransformer` class, which inherits from the `TriFileNumericalTransformer`
base class. The transformer is specifically designed to process and transform TRI Form R (3A) data files,
which detail off-site transfers of materials to various facilities. This class leverages both the FRS
(Facility Registry Service) and Census APIs to enrich the data with NAICS (North American Industry
Classification System) codes and descriptions for facilities.

Classes:
    TriFile3aTransformer: Handles the extraction, transformation, and enrichment of TRI Form R (3A) data.

Attributes:
    file_name (str): The name of the TRI data file.
    file_type (str): The type of TRI data file.
    config (DictConfig): Configuration object for setting parameters.
    data (pd.DataFrame): The main DataFrame containing raw or processed TRI data.

Methods:
    __init__(file_name: str, config: DictConfig): Initializes the transformer with file name, file type,
        and configuration settings.
    look_for_offsite_naics_code(): Searches for offsite NAICS codes using the FRS and Census APIs.
        Filters results to exclude null NAICS codes (e.g., for facilities located outside the U.S.),
        merges enriched data into the management DataFrame, and updates the main data.
    process(): Orchestrates the transformation pipeline by selecting required columns, handling missing
        values, converting units, separating release and management records, formatting management
        data, and calling the `look_for_offsite_naics_code` method for data enrichment.

Example Usage:
    ```
    import hydra
    from omegaconf import DictConfig

    # Load configuration using Hydra
    with hydra.initialize(config_path="."):
        cfg = hydra.compose(config_name="main")

    # Instantiate and process data
    transformer = TriFile3aTransformer("US_3a_2022.txt", cfg)
    transformer.process()
    ```

Notes:
    - The `look_for_offsite_naics_code` method relies on asynchronous API calls to the FRS and Census APIs
      to fetch and merge relevant NAICS codes, helping provide comprehensive information on off-site facilities.
    - The `process` method utilizes modularized methods from the `TriFileNumericalTransformer` to ensure
      clean and well-structured data transformation.

"""


import textwrap

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from omegaconf import DictConfig

from src.data_processing.frs_api_queries import FrsDataFetcher
from src.data_processing.naics_api_queries import NaicsDataFetcher
from src.data_processing.tri.transform.base import TriFileNumericalTransformer


class TriFile3aTransformer(TriFileNumericalTransformer):
    """Class for transforming TRI Form R (3A) data files.

    Attributes:
        file_name (str): The name of the TRI data file.
        file_type (str): The type of TRI data file.
        config (DictConfig): The configuration object.
        data (pd.DataFrame): The data from the TRI data file.

    """

    def __init__(
        self,
        file_name: str,
        config: DictConfig,
    ):
        super().__init__(file_name, "file_3a", False, config)
        self.frs_fether = FrsDataFetcher(config)
        self.census_fetcher = NaicsDataFetcher(config)

    def look_for_offsite_naics_code(self):
        """Look for offsite NAICS code in the data."""
        off_site_frs_id_column = self.config.tri_files.file_3a.off_site_frs_id_column
        self.df_management[off_site_frs_id_column] = self.df_management[off_site_frs_id_column].astype(int).astype(str)

        # Some times it could return a null naics code because the offsite is located outside the U.S.
        frs_results = self.frs_fether.process_registry_ids(
            self.df_management,
            off_site_frs_id_column,
        )
        frs_results.rename(columns={"naics_code": "off_site_naics_code"}, inplace=True)
        frs_results.dropna(
            subset=["off_site_naics_code"],
            inplace=True,
        )
        naics_results = self.census_fetcher.process_naics_codes(frs_results, "off_site_naics_code")
        naics_results.rename(
            columns={
                "naics_code": "off_site_naics_code",
                "naics_title": "off_site_naics_title",
            },
            inplace=True,
        )

        merged_df = self.df_management.merge(
            frs_results,
            left_on=off_site_frs_id_column,
            right_on="registry_id",
            how="left",
        )

        merged_df = merged_df.merge(
            naics_results,
            on="off_site_naics_code",
            how="left",
        )
        merged_df = merged_df.drop(columns=["registry_id"])
        self.df_management = merged_df

    def process(self):
        """Process the TRI data file."""
        needed_columns = self._get_needed_columns()
        self.data = self.select_columns(needed_columns)
        self.data = self.filter_desired_chemicals()
        self.fill_missing_values()
        self.data = self.prepare_unpivot_columns()
        self.to_kilogram()
        self.data[self.naics_code_column] = self.data[self.naics_code_column].fillna(0).astype(int).astype(str)
        self.look_for_facility_naics_code()
        self.df_releases, self.df_management = self.separate_releases_and_management()
        self.df_releases = self.organize_resealse_dataframe(self.df_releases)
        self.df_management = self.organize_management_dataframe(self.df_management)
        self.look_for_offsite_naics_code()

    def get_flowing_ratio(self):
        self.config.tri_files[self.file_type].needed_columns.append(
            {
                "name": "chemical_name",
                "is_general_info": True,
            }
        )
        needed_columns = self._get_needed_columns()
        self.data = self.select_columns(needed_columns)
        self.fill_missing_values()
        self.data = self.prepare_unpivot_columns()
        self.to_kilogram()
        self.df_releases, self.df_management = self.separate_releases_and_management()
        self.df_management = self.organize_management_dataframe(self.df_management)
        management_type = self._management_type()
        self.df_management["is_recycling"] = self.df_management["eol_name"].replace(management_type)
        result = self.calculate_recycling_ratios("0000080626")
        result = self.filter_by_platic_related(result)
        self.generate_plot(result)

    def _management_type(self) -> dict[str, bool]:
        return {
            self._normalize_column_name(x["name"]): x.get("is_recycling", False)
            for x in self.config.tri_files[self.file_type].needed_columns
            if x.get("management_type", False)
        }

    def calculate_recycling_ratios(self, tri_chem_id: str) -> pd.DataFrame:
        df_recycling = self.df_management[self.df_management["is_recycling"] == True]
        target_records = df_recycling[df_recycling["tri_chem_id"] == tri_chem_id]
        target_records = target_records[target_records["amount"] > 0]
        merged_df = df_recycling.merge(
            target_records[["trifid", "off_site_frs_id", "amount", "eol_name"]],
            on=["trifid", "off_site_frs_id", "eol_name"],
            suffixes=("", "_target"),
        )
        merged_df = merged_df[merged_df["amount"] > 0]
        merged_df["amount_ratio"] = merged_df["amount"] / merged_df["amount_target"]
        merged_df = merged_df[merged_df["tri_chem_id"] != tri_chem_id]
        result = merged_df[["chemical_name", "amount_ratio", "primary_naics_code"]]
        return result

    def filter_by_platic_related(self, result: pd.DataFrame) -> pd.DataFrame:
        naics_code = self.config.industry_sectors.naics_code
        naics_code = {x["code"]: x["name"] for x in naics_code}
        result = result[result["primary_naics_code"].isin(naics_code.keys())]
        result["primary_naics_title"] = result["primary_naics_code"].replace(naics_code)
        return result

    def generate_plot(self, result: pd.DataFrame):

        result["log_amount_ratio"] = np.log(result["amount_ratio"])
        df_grouped = result.groupby(["chemical_name", "primary_naics_title"], as_index=False)["log_amount_ratio"].mean()
        df_grouped["count"] = result.groupby(["chemical_name", "primary_naics_title"]).size().values
        heatmap_data = df_grouped.pivot(index="chemical_name", columns="primary_naics_title", values="log_amount_ratio")
        count_data = df_grouped.pivot(index="chemical_name", columns="primary_naics_title", values="count").fillna(0)

        fig = go.Figure(
            data=go.Heatmap(
                z=heatmap_data.values,
                x=heatmap_data.columns.tolist(),
                y=heatmap_data.index.tolist(),
                xgap=1,
                ygap=1,
                colorscale="Viridis",
                colorbar=dict(
                    title=dict(
                        text="Log(Mass Chemical / Mass MMA)",
                        side="right",
                        font=dict(
                            size=20,
                            family="Arial",
                            weight="bold",
                        ),
                    ),
                    tickfont=dict(size=16, family="Arial", color="black"),
                ),
            )
        )

        # Add text annotations at the center of each square
        for i, row in enumerate(heatmap_data.index):
            for j, col in enumerate(heatmap_data.columns):
                if count_data.iloc[i, j] > 0:
                    fig.add_annotation(
                        text=str(int(count_data.iloc[i, j])),  # Convert count to int
                        x=col,
                        y=row,
                        showarrow=False,
                        font=dict(size=12, color="white"),
                    )

        fig.update_layout(
            title={
                "text": "Heatmap of Amount Ratio by Chemical and Industry",
                "font": {"size": 25, "family": "Arial", "color": "black", "weight": "bold"},
            },
            xaxis={
                "type": "category",
                "showgrid": False,
                "title": {
                    "text": "Primary NAICS Title",
                    "font": {"size": 25, "family": "Arial", "color": "black", "weight": "bold"},
                },
                "tickfont": {"size": 18.5, "family": "Arial", "color": "black"},
                "tickangle": 0,
                "tickmode": "array",
                "tickvals": fig.data[0].x,  # type: ignore [reportAttributeAccessIssue]
                "ticktext": [self.split_long_labels(label) for label in fig.data[0].x],  # type: ignore [reportAttributeAccessIssue]
            },
            yaxis={
                "type": "category",
                "showgrid": False,
                "title": {"text": "Chemical Name", "font": {"size": 25, "family": "Arial", "color": "black", "weight": "bold"}},
                "tickfont": {"size": 18.5, "family": "Arial", "color": "black"},
            },
        )

        fig.show()

    def split_long_labels(self, label, max_length=15):
        """Splits a string into multiple lines without breaking words, keeping max segment length."""
        return " <br> ".join(textwrap.wrap(label, width=max_length, break_long_words=False))


if __name__ == "__main__":
    # This is only used for smoke testing
    import hydra

    with hydra.initialize(
        version_base=None,
        config_path="../../../../conf",
        job_name="smoke-testing-tri",
    ):
        cfg = hydra.compose(config_name="main")
        transformer = TriFile3aTransformer("US_3a_2022.txt", cfg)
        # transformer.process()
        # print(transformer.df_management.info())
        # print(transformer.df_releases.info())

        transformer.get_flowing_ratio()

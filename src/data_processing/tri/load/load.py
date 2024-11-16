# -*- coding: utf-8 -*-
# !/usr/bin/env python

"""Load data into the database.

This module defines the `TriDataLoader` class, which is responsible for loading various types
of environmental and chemical data into a TRI (Toxics Release Inventory) database. It utilizes
SQLAlchemy for database interactions and pandas for efficient data manipulation and bulk loading.

Classes:
    TriDataLoader: A data loader class that provides methods for loading data related to
        chemical activities, plastic additives, release management types, and records.

Methods:
    __init__(self, config: DictConfig, session: Session): Initializes the TriDataLoader class.
    load_chemical_activity(self): Loads chemical activities into the database.
    load_plastic_additives(self): Loads plastic additives into the database.
    load_release_management_type(self, df: pd.DataFrame, table_name: str): Loads release and
        management types into the database from a DataFrame.
    merge_with_1b(self, df_main: pd.DataFrame) -> pd.DataFrame: Merges main DataFrame with
        filtered 1b data on 'trifid' and 'tri_chem_id'.
    get_inserted_record_ids(self, records_df: pd.DataFrame, eol_name_list: List[str]) -> pd.DataFrame:
        Retrieves record IDs from the database and merges them with the original DataFrame.
    load_records(self, df: pd.DataFrame, record_type: str, handler_columns: Optional[Tuple[str, str]] = None):
        Loads records into the Record table based on the type and enriched DataFrame.
    _get_waste_handler_industry_sector_id(self, off_site_naics_code: Union[str, None], off_site_naics_title: Union[str, None]) -> Optional[int]:
        Fetches or creates an IndustrySector for the waste handler and returns its ID.
    _get_end_of_life_activity_id(self, eol_name: Union[str, None]) -> Optional[int]: Fetches
        or creates an EndOfLifeActivity and returns its ID if record type is management.
    _get_release_type_id(self, eol_name: Union[str, None]) -> Optional[int]: Fetches or creates
        a ReleaseType and returns its ID if record type is release.
    _load_record_chemical_activity(self, df: pd.DataFrame): Loads associations between records
        and chemical activities using a DataFrame.
    load_all_records(self, transformer_1a, transformer_3a, transformer_3c): Loads records from
        different transformers into the Record table after merging with 1b.
    set_1b(self, df: pd.DataFrame): Sets the 1b DataFrame for use in merging and enrichment.

Usage:
    This module can be run independently for smoke testing purposes. When executed directly,
    it initializes the configuration using Hydra, sets up the database, and loads chemical
    activities and plastic additives into the database.

Example:
    >>> from src.data_processing.create_sqlite_db import create_database
    >>> session = create_database()
    >>> loader = TriDataLoader(config, session)
    >>> loader.load_chemical_activity()
    >>> loader.load_plastic_additives()

"""

from typing import Dict, List, Optional, Tuple, Union

import pandas as pd
from omegaconf import DictConfig
from sqlalchemy.orm import Session
from sqlalchemy.sql import text

from src.data_processing.base import BaseDataLoader
from src.data_processing.data_models import (
    Additive,
    ChemicalActivity,
    EndOfLifeActivity,
    IndustrySector,
    ReleaseType,
)


class TriDataLoader(BaseDataLoader):
    """Class for loading data into the TRI database.

    Attributes:
        config (DictConfig): The configuration object.
        session (Session): The database session object.

    """

    def __init__(
        self,
        config: DictConfig,
        session: Session,
    ):
        super().__init__(config, session)
        self.cache_additive_id: Dict[Tuple, int] = {}
        self.cache_industry_sector_id: Dict[Tuple, int] = {}
        self.cache_end_of_life_activity_id: Dict[Tuple, int] = {}
        self.cache_release_type_id: Dict[Tuple, int] = {}
        self.cache_chemical_activity_id: Dict[Tuple, int] = {}

    def load_chemical_activity(self):
        """Load chemical activities into the database."""
        chemical_activities = [col for col in self.config.tri_files.file_1b.needed_columns if "is_general_info" not in col]

        for activity in chemical_activities:
            if (dependency_name := activity.get("depends_on")) is not None:
                dependency = self.get_or_create(
                    ChemicalActivity,
                    name=dependency_name,
                )
                dependency_id = dependency.id if dependency else None
            else:
                dependency_id = None

            if not self.element_exists(
                ChemicalActivity,
                name=activity["name"],
            ):
                self.create_element(
                    ChemicalActivity,
                    name=activity["name"],
                    description=activity.get("description", None),
                    parent_chemical_activity_id=dependency_id,
                )

    def load_plastic_additives(self):
        """Load plastic additives into the database."""
        plastic_additives = self.config.plastic_additives.tri_chem_id

        for additive in plastic_additives:
            if not self.element_exists(
                Additive,
                tri_chemical_id=additive["CASRN"],
            ):
                self.create_element(
                    Additive,
                    name=additive["name"],
                    tri_chemical_id=additive["CASRN"],
                )

    def load_release_management_type(
        self,
        df: pd.DataFrame,
        table_name: str,
    ):
        """Load release and management types into the database.

        Args:
            df (pd.DataFrame): The DataFrame containing the release types.
            table_name (str): The name of the table in the database.

        """
        existing_names = pd.read_sql(
            text("SELECT name FROM :table_name"),
            con=self.session.get_bind(),
            params={"table_name": table_name},
        )["name"].tolist()

        df_filtered = df[~df["name"].isin(existing_names)]
        df_filtered.to_sql(
            table_name,
            self.session.get_bind(),
            if_exists="append",
            index=False,
        )

    def merge_with_1b(
        self,
        df_main: pd.DataFrame,
    ) -> pd.DataFrame:
        """Merge main DataFrame with filtered 1b data on 'trifid' and 'tri_chem_id'."""
        # Merge main DataFrame with filtered 1b on 'trifid'
        df_enriched = df_main.merge(
            self.df_1b[
                [
                    "trifid",
                    "tri_chem_id",
                    "chemical_activity",
                    "is_performed",
                ]
            ],
            on=["trifid", "tri_chem_id"],
            how="left",  # Keep all rows in the main DataFrame
        )
        return df_enriched

    def get_inserted_record_ids(
        self,
        records_df: pd.DataFrame,
        eol_name_list: List[str],
    ) -> pd.DataFrame:
        """Fetch the record IDs from the database and merge them with the original DataFrame."""
        sql_query = text(
            """
            SELECT record.id AS record_id,
                record.trifid,
                additive.tri_chemical_id AS tri_chem_id,
                end_of_life_activity.name AS management_name,
                release_type.name AS release_name
            FROM record
            LEFT JOIN additive ON record.additive_id = additive.id
            LEFT JOIN end_of_life_activity ON record.end_of_life_activity_id = end_of_life_activity.id
            LEFT JOIN release_type ON record.release_type_id = release_type.id
        """
        )
        inserted_records = pd.read_sql(
            sql_query,
            con=self.session.get_bind(),
        )
        inserted_records = inserted_records[
            (inserted_records["management_name"].isin(eol_name_list)) | (inserted_records["release_name"].isin(eol_name_list))
        ]
        inserted_records.drop(
            columns=["management_name", "release_name"],
            inplace=True,
        )

        merged_df = records_df.merge(
            inserted_records,
            on=[
                "trifid",
                "tri_chem_id",
            ],
            how="left",
        )

        return merged_df

    def load_records(
        self,
        df: pd.DataFrame,
        record_type: str,
        handler_columns: Optional[Tuple[str, str]] = None,
    ):
        """Load records into the Record table based on enriched DataFrame and type."""
        columns_needed = ["tri_chem_id", "trifid", "amount", "eol_name", "naics_code", "naics_title"]
        if handler_columns:
            columns_needed.extend(handler_columns)

        eol_name_list = df["eol_name"].unique().tolist()
        records_df = df[columns_needed].drop_duplicates()

        records_df["additive_id"] = records_df["tri_chem_id"].apply(  # type: ignore [reportAttributeAccessIssue]
            lambda row: self._cache_get_or_create(
                self.cache_additive_id,
                self._get_additive_id,
                tri_chem_id=row,
            ),
        )
        records_df["waste_generator_industry_sector_id"] = records_df.apply(
            lambda row: self._cache_get_or_create(
                self.cache_industry_sector_id,
                self._get_industry_sector_id,
                **{
                    "naics_code": row["naics_code"],
                    "naics_title": row["naics_title"],
                },
            ),
            axis=1,
        )
        if handler_columns:
            records_df["waste_handler_industry_sector_id"] = records_df.apply(
                lambda row: (
                    self._cache_get_or_create(
                        self.cache_industry_sector_id,
                        self._get_waste_handler_industry_sector_id,
                        **{col: row[col] for col in handler_columns},
                    )
                    if all(pd.notnull(row[col]) for col in handler_columns)
                    else None
                ),  # type: ignore [reportCallIssue]
                axis=1,
            )
        else:
            records_df["waste_handler_industry_sector_id"] = None
        records_df["end_of_life_activity_id"] = (
            records_df.apply(
                lambda row: self._cache_get_or_create(
                    self.cache_end_of_life_activity_id,
                    self._get_end_of_life_activity_id,
                    **{
                        "eol_name": row["eol_name"],
                    },
                ),
                axis=1,
            )
            if record_type == "management"
            else None
        )
        records_df["release_type_id"] = (
            records_df.apply(
                lambda row: self._cache_get_or_create(
                    self.cache_release_type_id,
                    self._get_release_type_id,
                    **{
                        "eol_name": row["eol_name"],
                    },
                ),
                axis=1,
            )
            if record_type == "release"
            else None
        )

        record_columns = [
            "additive_id",
            "waste_generator_industry_sector_id",
            "amount",
            "trifid",
            "end_of_life_activity_id",
            "release_type_id",
            "waste_handler_industry_sector_id",
        ]
        insert_df = records_df[record_columns].drop_duplicates()

        insert_df.to_sql(
            name="record",
            con=self.session.get_bind(),
            if_exists="append",
            index=False,
            method="multi",
            chunksize=200,
        )

        df_activity = df[["trifid", "tri_chem_id", "chemical_activity", "is_performed"]].drop_duplicates()
        df_activity = self.get_inserted_record_ids(df_activity, eol_name_list)[
            ["record_id", "chemical_activity", "is_performed"]
        ]
        df_activity.drop_duplicates(inplace=True)

        self._load_record_chemical_activity(df_activity)

        self.session.commit()

    def _get_waste_handler_industry_sector_id(
        self,
        off_site_naics_code: Union[str, None],
        off_site_naics_title: Union[str, None],
    ):
        """Fetch or create IndustrySector for the waste handler and return its id."""
        if off_site_naics_code and off_site_naics_title:
            sector = self.get_or_create(
                IndustrySector,
                naics_code=off_site_naics_code,
                naics_title=off_site_naics_title,
            )
            if sector:
                return sector.id
        return None

    def _get_end_of_life_activity_id(
        self,
        eol_name: Union[str, None],
    ):
        """Fetch or create EndOfLifeActivity and return its id if record_type is management."""
        if eol_name:
            activity = self.session.query(EndOfLifeActivity).filter_by(name=eol_name).first()
            if activity:
                return activity.id
        return None

    def _get_release_type_id(
        self,
        eol_name: Union[str, None],
    ):
        """Fetch or create ReleaseType and return its id if record_type is release."""
        if eol_name:
            release_type = self.session.query(ReleaseType).filter_by(name=eol_name).first()
            if release_type:
                return release_type.id
        return None

    def _load_record_chemical_activity(self, df: pd.DataFrame):
        """Loading of record-chemical activity associations using apply."""
        # Filter the DataFrame for relevant rows where 'is_performed' is 'Yes'
        filtered_df = df[(pd.notnull(df["chemical_activity"])) & (df["is_performed"] == "Yes")][
            ["record_id", "chemical_activity"]
        ].drop_duplicates()

        # Apply the caching method to get chemical activity IDs
        filtered_df["chemical_activity_id"] = filtered_df["chemical_activity"].apply(
            lambda activity: self._cache_get_or_create(
                self.cache_chemical_activity_id,
                self.get_or_create,
                **{
                    "model": ChemicalActivity,
                    "name": activity,
                },
            )
        )

        association_df = filtered_df[["record_id", "chemical_activity_id"]]

        if not association_df.empty:
            association_df.to_sql(
                name="record_chemical_activity",
                con=self.session.get_bind(),
                if_exists="append",
                index=False,
                method="multi",
                chunksize=200,
            )

    def load_all_records(
        self,
        transformer_1a,
        transformer_3a,
        transformer_3c,
    ):
        """Load records from different transformers into the Record table after merging with 1b."""
        # Merge 1b data with 1a, 3a, and 3c using both trifid and tri_chem_id
        df_1a_management = self.merge_with_1b(transformer_1a.df_management)
        df_3a_management = self.merge_with_1b(transformer_3a.df_management)
        df_3c_management = self.merge_with_1b(transformer_3c.df_management)
        df_1a_releases = self.merge_with_1b(transformer_1a.df_releases)
        df_3a_releases = self.merge_with_1b(transformer_3a.df_releases)

        # Load records with appropriate handler columns for 3a and 3c
        self.load_records(
            df_1a_management,
            record_type="management",
        )
        self.load_records(
            df_1a_releases,
            record_type="release",
        )
        self.load_records(
            df_3a_management,
            record_type="management",
            handler_columns=(
                "off_site_naics_code",
                "off_site_naics_title",
            ),
        )
        self.load_records(
            df_3a_releases,
            record_type="release",
        )
        self.load_records(
            df_3c_management,
            record_type="management",
            handler_columns=(
                "off_site_naics_code",
                "off_site_naics_title",
            ),
        )

        self.session.close()

    def set_1b(
        self,
        df: pd.DataFrame,
    ):
        """Set the 1b DataFrame."""
        self.df_1b = df


if __name__ == "__main__":
    # This is only used for smoke testing
    import hydra

    with hydra.initialize(
        version_base=None,
        config_path="../../../../conf",
        job_name="smoke-testing-tri",
    ):
        config = hydra.compose(config_name="main")
        from src.data_processing.create_sqlite_db import create_database

        session = create_database()
        loader = TriDataLoader(config, session)
        loader.load_chemical_activity()
        loader.load_plastic_additives()

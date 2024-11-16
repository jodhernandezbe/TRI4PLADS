# -*- coding: utf-8 -*-
# !/usr/bin/env python

"""Database queries module.

Module for querying the TRI database and storing results.

"""

import os
import textwrap
from typing import List, Optional

import pandas as pd
from sqlalchemy import create_engine


class ResultsStorage:
    """Class for storing and retrieving query results."""

    @classmethod
    def get_documents_folder(cls) -> str:
        """Get the path to the user's Documents folder using os."""
        return os.path.join(os.path.expanduser("~"), "Documents")

    @classmethod
    def get_default_file_path(cls) -> str:
        """Get the path to the results folder."""
        documents_folder = ResultsStorage.get_documents_folder()
        default_file_path = os.path.join(documents_folder, "query_results.xlsx")
        return default_file_path

    @classmethod
    def save_dataframe_to_excel(
        cls,
        df: pd.DataFrame,
        filename: str,
    ) -> None:
        """Save a DataFrame to an Excel file.

        Args:
            df (pd.DataFrame): DataFrame to save.
            filename (str): Name of the Excel file to save to.

        """
        df.to_excel(filename, index=False)


class TriDatabaseFilter:
    """Class for querying the TRI database."""

    def __init__(self):
        self._create_engine()

    def _create_engine(self):
        current_dir = os.getcwd()
        db_path = os.path.join(
            current_dir,
            "data",
            "processed",
            "tri_eol_additives.sqlite",
        )
        DATABASE_URL = f"sqlite:///{db_path}"
        self.engine = create_engine(DATABASE_URL, echo=False)

    def _wrap_text(
        self,
        text: str,
        width: int,
    ) -> str:
        return "\n".join(textwrap.wrap(text, width=width, break_long_words=False))

    def _preprocess_dataframe(
        self,
        df: pd.DataFrame,
        wrap_width: int,
    ) -> pd.DataFrame:
        return df.applymap(lambda x: self._wrap_text(str(x), wrap_width) if isinstance(x, str) else x)  # type: ignore [reportCallIssue]

    def _generate_query(
        self,
        query_string: str,
    ) -> pd.DataFrame:
        df = pd.read_sql_query(query_string, self.engine)
        return self._preprocess_dataframe(df, wrap_width=25)

    def get_records_stats_by_end_of_life_activity(
        self,
        selected_conditions: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """Get records stats by end of life activity.

        Args:
            selected_conditions (Optional[List[str]], optional): A list of conditions to filter records by. Defaults to None.

        """
        base_query = """SELECT
            end_of_life_activity.name AS 'End-of-life',
            end_of_life_activity.management_type AS "Management type",
            COUNT(record.amount) AS 'Number of records',
            SUM(record.amount) AS 'Total Amount [kg/yr]'
        FROM record
        LEFT JOIN end_of_life_activity
            ON end_of_life_activity.id = record.end_of_life_activity_id
        WHERE record.amount != 0
            AND record.end_of_life_activity_id IS NOT NULL"""

        # Add optional conditions
        if selected_conditions:
            conditions_clause = " OR ".join(selected_conditions)
            base_query += f" AND ({conditions_clause})"

        # Finalize query with GROUP BY and ORDER BY
        base_query += """
        GROUP BY end_of_life_activity.name,
                 end_of_life_activity.management_type
        ORDER BY SUM(record.amount) DESC;"""

        df = self._generate_query(base_query)
        return df

    def get_records_stats_by_additive_related_use(
        self,
        use_query: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """Get records stats by additive related use.

        Args:
            use_query (Optional[List[str]], optional): A list of conditions to filter records by. Defaults
                to None.

        """
        query = """SELECT
            chemical_activity.name AS 'Condition of Use',
            COUNT(record.amount) AS 'Number of records',
            SUM(record.amount) AS 'Total Amount [kg/yr]'
        FROM record
        LEFT JOIN record_chemical_activity
            ON record_chemical_activity.record_id = record.id
        LEFT JOIN chemical_activity
            ON chemical_activity.id = record_chemical_activity.chemical_activity_id
        WHERE record.amount != 0
            AND chemical_activity.parent_chemical_activity_id IS NOT NULL
        """

        if use_query:
            uses = ", ".join(f"'{code}'" for code in use_query)
            query += f" AND chemical_activity.name IN ({uses})"

        query += """
        GROUP BY chemical_activity.name
        ORDER BY SUM(record.amount) DESC;"""

        df = self._generate_query(query)
        return df

    def get_records_stats_by_additive(
        self,
        additive_query: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """Get records statistics by additive.

        Args:
            additive_query (Optional[List[str]], optional): A list of conditions to filter records by. Defaults
                to None.

        """
        query = """SELECT
            additive.name AS 'Additive',
            COUNT(record.amount) AS 'Number of records',
            SUM(record.amount) AS 'Total Amount [kg/yr]'
        FROM record
        LEFT JOIN additive
            ON additive.id = record.additive_id
        WHERE record.amount != 0"""

        if additive_query:
            casrns = ", ".join(f"'{code}'" for code in additive_query)
            query += f" AND additive.tri_chemical_id IN ({casrns})"

        # Finalize the query with GROUP BY and ORDER BY
        query += """
        GROUP BY record.additive_id
        ORDER BY SUM(record.amount) DESC;"""

        df = self._generate_query(query)

        return df

    def get_records_stats_by_naics_code(
        self,
        industry_sector_query: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """Get records statistics by NAICS code.

        Args:
            industry_sector_query (Optional[List[str]], optional): A list of NAICS codes to filter records by. Defaults to None.

        Returns:
            pd.DataFrame: A DataFrame containing records statistics by NAICS code.

        """
        # Base query
        query = """SELECT
            industry_sector.naics_code AS '6-digit NAICS code',
            industry_sector.naics_title AS 'NAICS description',
            COUNT(record.amount) AS 'Number of records',
            SUM(record.amount) AS 'Total Amount [kg/yr]'
        FROM record
        LEFT JOIN industry_sector
            ON industry_sector.id = record.waste_generator_industry_sector_id
        WHERE record.amount != 0"""

        # If sectors are selected, add a WHERE condition for `naics_code`
        if industry_sector_query:
            naics_codes = ", ".join(f"'{code}'" for code in industry_sector_query)
            query += f" AND industry_sector.naics_code IN ({naics_codes})"

        # Finalize the query with GROUP BY and ORDER BY
        query += """
        GROUP BY industry_sector.naics_code, industry_sector.naics_title
        ORDER BY SUM(record.amount) DESC;"""

        df = self._generate_query(query)

        return df

    def get_records_stats_by_all_filters(
        self,
        industry_sector_query: Optional[List[str]] = None,
        additive_query: Optional[List[str]] = None,
        use_query: Optional[List[str]] = None,
        eol_conditions: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """Generate a complex query combining multiple filtering criteria.

        Args:
            industry_sector_query (Optional[List[str]], optional): A list of NAICS codes to filter records by. Defaults to None.
            additive_query (Optional[List[str]], optional): A list of additives to filter records by. Defaults to None.
            use_query (Optional[List[str]], optional): A list of conditions of use to filter records by. Defaults to None.
            eol_conditions (Optional[List[str]], optional): A list of end-of-life conditions to filter records by. Defaults to None.

        Returns:
            pd.DataFrame: A DataFrame containing records statistics by all filters.

        """
        base_query = """
        SELECT
            industry_sector.naics_code AS 'NAICS Code',
            industry_sector.naics_title AS 'NAICS Description',
            additive.name AS 'Additive',
            chemical_activity.name AS 'Condition of Use',
            end_of_life_activity.name AS 'End-of-life',
            end_of_life_activity.management_type AS 'Management Type',
            COUNT(record.amount) AS 'Number of Records',
            SUM(record.amount) AS 'Total Amount [kg/yr]'
        FROM record
        LEFT JOIN industry_sector
            ON industry_sector.id = record.waste_generator_industry_sector_id
        LEFT JOIN additive
            ON additive.id = record.additive_id
        LEFT JOIN record_chemical_activity
            ON record_chemical_activity.record_id = record.id
        LEFT JOIN chemical_activity
            ON chemical_activity.id = record_chemical_activity.chemical_activity_id
        LEFT JOIN end_of_life_activity
            ON end_of_life_activity.id = record.end_of_life_activity_id
        WHERE record.amount != 0
            AND record.end_of_life_activity_id IS NOT NULL
        """

        # Add filtering for NAICS codes
        if industry_sector_query:
            naics_codes = ", ".join(f"'{code}'" for code in industry_sector_query)
            base_query += f" AND industry_sector.naics_code IN ({naics_codes})"

        # Add filtering for additives
        if additive_query:
            casrns = ", ".join(f"'{code}'" for code in additive_query)
            base_query += f" AND additive.tri_chemical_id IN ({casrns})"

        # Add filtering for conditions of use
        if use_query:
            uses = ", ".join(f"'{code}'" for code in use_query)
            base_query += f" AND chemical_activity.name IN ({uses})"

        # Add filtering for end-of-life conditions
        if eol_conditions:
            conditions_clause = " OR ".join(eol_conditions)
            base_query += f" AND ({conditions_clause})"

        base_query += """
        GROUP BY industry_sector.naics_code, industry_sector.naics_title,
                 additive.name, chemical_activity.name,
                 end_of_life_activity.name, end_of_life_activity.management_type
        ORDER BY SUM(record.amount) DESC;
        """

        # Execute and return the results
        return self._generate_query(base_query)

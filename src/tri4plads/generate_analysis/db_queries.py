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

    chemical_activity_lookup = {}

    def __init__(self):
        self._create_engine()

    def _create_engine(self):
        current_dir = os.getcwd()
        db_path = os.path.join(
            current_dir,
            os.pardir,
            os.pardir,
            os.pardir,
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
        return df.map(lambda x: self._wrap_text(str(x), wrap_width) if isinstance(x, str) else x)  # type: ignore [reportCallIssue]

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
            COUNT(DISTINCT record.id) AS 'Number of Records',  -- Count unique records
            SUM(record.amount) AS 'Total Amount [kg/yr]'      -- Sum amounts, avoiding duplicates
        FROM record
        LEFT JOIN (
            SELECT DISTINCT record_id, chemical_activity_id
            FROM record_chemical_activity
        ) AS unique_activities  -- Remove duplicates in the many-to-many relationship
            ON unique_activities.record_id = record.id
        LEFT JOIN chemical_activity
            ON chemical_activity.id = unique_activities.chemical_activity_id
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
        SELECT DISTINCT
            industry_sector.naics_code AS 'NAICS Code',
            industry_sector.naics_title AS 'NAICS Description',
            additive.name AS 'Additive',
            chemical_activity.name AS 'Condition of Use',
            end_of_life_activity.name AS 'End-of-life',
            end_of_life_activity.management_type AS 'Management Type',
            COUNT(DISTINCT record.id) AS 'Number of Records',
            SUM(record.amount) AS 'Total Amount [kg/yr]'
        FROM record
        LEFT JOIN industry_sector
            ON industry_sector.id = record.waste_generator_industry_sector_id
        LEFT JOIN additive
            ON additive.id = record.additive_id
        LEFT JOIN (
            SELECT DISTINCT record_id, chemical_activity_id
            FROM record_chemical_activity
        ) AS unique_activities
            ON unique_activities.record_id = record.id
        LEFT JOIN chemical_activity
            ON chemical_activity.id = unique_activities.chemical_activity_id
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

    def get_tri_records_for_report(
        self,
        on_site_activities: bool,
        generator_industry_sectors: Optional[List[str]] = None,
        additive_tri_ids: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """Generate a TRI report focusing on waste management activities.

        Args:
            on_site_activities (bool): Include only on-site waste management activities if True.
            generator_industry_sectors (Optional[List[str]]): NAICS codes of the generator industry sectors. Defaults to None.
            additive_tri_ids (Optional[List[str]]): TRI chemical IDs of additives to filter by. Defaults to None.

        Returns:
            pd.DataFrame: DataFrame containing the filtered and processed TRI records.
        """
        # Base query focused on waste management activities
        query = """
        SELECT DISTINCT
            record.trifid AS 'TRIFID',
            additive.name AS 'Additive',
            additive.tri_chemical_id AS 'TRI Chemical ID',
            industry_sector.naics_code AS 'Generator NAICS Code',
            industry_sector.naics_title AS 'Generator NAICS Title',
            waste_handler_sector.naics_code AS 'Waste Handler NAICS Code',
            waste_handler_sector.naics_title AS 'Waste Handler NAICS Title',
            chemical_activity.id AS 'Chemical Activity ID',
            chemical_activity.name AS 'Chemical Activity',
            end_of_life_activity.name AS 'Waste Management Activity',
            end_of_life_activity.management_type AS 'Management Type',
            end_of_life_activity.is_incineration AS 'Is Incineration',
            end_of_life_activity.is_potw AS 'Is POTW',
            end_of_life_activity.is_landfilling AS 'Is Landfilling',
            end_of_life_activity.is_recycling AS 'Is Recycling',
            record.amount AS 'Amount [kg/yr]',
            end_of_life_activity.is_on_site AS 'Is On-Site'
        FROM record
        LEFT JOIN additive ON additive.id = record.additive_id
        LEFT JOIN industry_sector ON industry_sector.id = record.waste_generator_industry_sector_id
        LEFT JOIN industry_sector AS waste_handler_sector ON waste_handler_sector.id = record.waste_handler_industry_sector_id
        LEFT JOIN record_chemical_activity ON record_chemical_activity.record_id = record.id
        LEFT JOIN chemical_activity ON chemical_activity.id = record_chemical_activity.chemical_activity_id
        LEFT JOIN end_of_life_activity ON end_of_life_activity.id = record.end_of_life_activity_id
        WHERE record.amount != 0
        AND record.end_of_life_activity_id IS NOT NULL
        AND record.release_type_id IS NULL
        """

        # Apply additional filters if specified
        if not on_site_activities:
            query += " AND end_of_life_activity.is_on_site != 1"

        if generator_industry_sectors:
            naics_codes = ", ".join(f"'{code}'" for code in generator_industry_sectors)
            query += f" AND industry_sector.naics_code IN ({naics_codes})"

        if additive_tri_ids:
            tri_ids = ", ".join(f"'{tri_id}'" for tri_id in additive_tri_ids)
            query += f" AND additive.tri_chemical_id IN ({tri_ids})"

        # Add ORDER BY clause at the end
        query += " ORDER BY record.trifid, chemical_activity.name;"

        # Retrieve raw data
        raw_df = self._generate_query(query)

        # Populate the lookup table
        self._populate_chemical_activity_lookup(raw_df)

        # Organize data using a private method
        return self._organize_report_data(raw_df)

    def _populate_chemical_activity_lookup(self, raw_df: pd.DataFrame) -> None:
        """Populate the class-level chemical activity lookup table.

        Args:
            raw_df (pd.DataFrame): The raw DataFrame retrieved from the query.
        """
        if not raw_df.empty:
            unique_activities = raw_df[["Chemical Activity ID", "Chemical Activity"]].drop_duplicates()
            self.chemical_activity_lookup = dict(
                zip(unique_activities["Chemical Activity ID"], unique_activities["Chemical Activity"])
            )

    def _organize_report_data(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """Organize the raw DataFrame by grouping and sorting chemical activities.

        Args:
            raw_df (pd.DataFrame): The raw DataFrame retrieved from the query.

        Returns:
            pd.DataFrame: The organized DataFrame with grouped chemical activities.
        """
        if raw_df.empty:
            return raw_df  # Return empty DataFrame if no data is retrieved

        # Group by unique record attributes and aggregate chemical activities
        processed_df = (
            raw_df.groupby(
                [
                    "TRIFID",
                    "Additive",
                    "TRI Chemical ID",
                    "Generator NAICS Code",
                    "Generator NAICS Title",
                    "Waste Handler NAICS Code",
                    "Waste Handler NAICS Title",
                    "Waste Management Activity",
                    "Management Type",
                    "Is Incineration",
                    "Is POTW",
                    "Is Landfilling",
                    "Is Recycling",
                    "Amount [kg/yr]",
                    "Is On-Site",
                ],
                dropna=False,
            )
            .agg(
                {
                    "Chemical Activity": lambda x: "; ".join(sorted(set(x))),
                    "Chemical Activity ID": lambda x: "; ".join(sorted(map(str, set(x)))),
                }
            )
            .reset_index()
        )

        return processed_df

    def get_industrial_uses(self) -> pd.DataFrame:
        """Query all industrial uses of additives, including industry use sector and NAICS details.

        Returns:
            pd.DataFrame: DataFrame containing all industrial use records with industry use sector and NAICS details.
        """
        query = """
        SELECT
            industrial_use.id AS 'Industrial Use ID',
            additive.tri_chemical_id AS 'TRI Chemical ID',
            additive.name AS 'Additive',
            industrial_type_of_process_or_use.name AS 'Industrial Process Type',
            industry_function_category.name AS 'Function Category',
            industry_sector.naics_code AS 'Industry NAICS Code',
            industry_sector.naics_title AS 'Industry NAICS Title',
            industry_use_sector.id AS 'Industry Use Sector ID',
            industry_use_sector.code AS 'Industry Use Sector Code',
            industry_use_sector.name AS 'Industry Use Sector Name',
            industry_sector_ref.naics_code AS 'Related NAICS Code',
            industry_sector_ref.naics_title AS 'Related NAICS Title',
            industrial_use.percentage AS 'Percentage'
        FROM industrial_use
        LEFT JOIN additive ON additive.id = industrial_use.additive_id
        LEFT JOIN industrial_type_of_process_or_use ON industrial_type_of_process_or_use.id = industrial_use.industrial_type_of_process_or_use_id
        LEFT JOIN industry_function_category ON industry_function_category.id = industrial_use.industry_function_category_id
        LEFT JOIN industry_sector ON industry_sector.id = industrial_use.industry_sector_id
        LEFT JOIN industry_use_sector ON industry_use_sector.id = industrial_use.industry_use_sector_id
        LEFT JOIN industry_use_sector_naics ON industry_use_sector_naics.industry_use_sector_id = industry_use_sector.id
        LEFT JOIN industry_sector AS industry_sector_ref ON industry_sector_ref.id = industry_use_sector_naics.industry_sector_id
        ORDER BY industrial_use.id;
        """
        return self._generate_query(query)

    def get_consumer_commercial_uses(self) -> pd.DataFrame:
        """Query all consumer and commercial uses of additives.

        Returns:
            pd.DataFrame: DataFrame containing all consumer and commercial use records.
        """
        query = """
        SELECT
            consumer_commercial_use.id AS 'Consumer/Commercial Use ID',
            additive.tri_chemical_id AS 'TRI Chemical ID',
            additive.name AS 'Additive',
            consumer_commercial_product_category.name AS 'Product Category',
            consumer_commercial_function_category.name AS 'Function Category',
            industry_sector.naics_code AS 'Industry NAICS Code',
            industry_sector.naics_title AS 'Industry NAICS Title',
            consumer_commercial_use.type_of_use AS 'Type of Use',
            consumer_commercial_use.percentage AS 'Percentage'
        FROM consumer_commercial_use
        LEFT JOIN additive ON additive.id = consumer_commercial_use.additive_id
        LEFT JOIN consumer_commercial_product_category ON consumer_commercial_product_category.id = consumer_commercial_use.product_category_id
        LEFT JOIN consumer_commercial_function_category ON consumer_commercial_function_category.id = consumer_commercial_use.function_category_id
        LEFT JOIN industry_sector ON industry_sector.id = consumer_commercial_use.industry_sector_id
        ORDER BY consumer_commercial_use.id;
        """
        return self._generate_query(query)

# -*- coding: utf-8 -*-
# !/usr/bin/env python

"""Interactive CLI module.

Module for handling interactive CLI operations, such as displaying prompts and tables
and handling user input.

"""

from typing import Dict, List, Optional

import pandas as pd
import questionary
from omegaconf import DictConfig
from rich.console import Console
from rich.table import Table

from src.tri4plads.generate_analysis.db_queries import ResultsStorage, TriDatabaseFilter


class InteractiveCLI:
    """Class for handling interactive CLI operations.

    This class provides an interface for interacting with the user through the command line.
    It uses the questionary library to create interactive prompts and the rich library to display
    tables and other formatted text.

    """

    def __init__(self, config: DictConfig) -> None:
        self.config = config
        self._available_plastic_sectors: Optional[Dict[str, str]] = None
        self._available_plastic_additives: Optional[Dict[str, str]] = None
        self._available_additive_related_uses: Optional[Dict[str, str]] = None
        self.tri_db_filter = TriDatabaseFilter()
        self.console = Console()

    def _get_available_plastic_sectors(self) -> Dict[str, str]:
        """Fetch available plastic sectors from the config."""
        if self._available_plastic_sectors is None:
            try:
                self._available_plastic_sectors = {
                    naics["code"]: naics["name"] for naics in self.config.industry_sectors.naics_code
                }
            except (AttributeError, KeyError, TypeError) as e:
                self.console.print("[bold red]Error loading plastic sectors. Please check the configuration.[/bold red]")
                raise e
        return self._available_plastic_sectors

    def _get_available_plastic_additives(self) -> Dict[str, str]:
        """Fetch available plastic additives from the config."""
        if self._available_plastic_additives is None:
            try:
                self._available_plastic_additives = {
                    additive["CASRN"]: additive["name"] for additive in self.config.plastic_additives.tri_chem_id
                }
            except (AttributeError, KeyError, TypeError) as e:
                self.console.print("[bold red]Error loading plastic additives. Please check the configuration.[/bold red]")
                raise e
        return self._available_plastic_additives

    def _get_available_additive_related_uses(self) -> Dict[str, str]:
        """Fetch available additive-related uses from the config."""
        if self._available_additive_related_uses is None:
            try:
                self._available_additive_related_uses = {
                    use["name"]: use["description"]
                    for use in self.config.tri_files.file_1b.needed_columns
                    if "description" in use
                }
            except (AttributeError, KeyError, TypeError) as e:
                self.console.print("[bold red]Error loading additive-related uses. Please check the configuration.[/bold red]")
                raise e
        return self._available_additive_related_uses

    def _select_items(self, title: str, items: Dict[str, str], key_column: str, value_column: str) -> Optional[List[str]]:
        """Generic method to display a selection menu and return selected keys.

        Args:
            title (str): The title for the selection table.
            items (Dict[str, str]): The items to select from.
            key_column (str): The label for the key column in the table.
            value_column (str): The label for the value column in the table.

        Returns:
            Optional[List[str]]: A list of selected keys.

        """
        choices = [f"{key}: {value}" for key, value in items.items()]
        selected = questionary.checkbox(f"Select one or more {title}:", choices=choices).ask()

        if not selected:
            self.console.print(f"[bold red]No selection was made for {title}. No filter would be used.[/bold red]")
            return None

        selected_keys = [choice.split(":")[0].strip() for choice in selected]

        table = Table(title=f"Selected {title}")
        table.add_column(key_column, style="cyan", no_wrap=True)
        table.add_column(value_column, style="magenta")

        for key in selected_keys:
            table.add_row(key, items[key])

        self.console.print(table)
        return selected_keys

    def select_end_of_life_activities(self) -> List[str]:
        """Allow the user to select optional conditions.

        Returns:
            List[str]: A list of selected conditions.

        """
        condition_mapping = {
            "Publicly Owned Treatment Works (POTW)": "end_of_life_activity.is_potw",
            "Recycling": "end_of_life_activity.is_recycling",
            "Landfilling": "end_of_life_activity.is_landfilling",
            "Incineration": "end_of_life_activity.is_incineration",
        }

        selected_human_readable = questionary.checkbox(
            "Select conditions to filter by:",
            choices=list(condition_mapping.keys()),
        ).ask()

        if selected_human_readable:
            return [condition_mapping[option] for option in selected_human_readable]
        else:
            return []

    def select_plastic_sector(self) -> Optional[List[str]]:
        """Display a menu to select a plastic sector and return the selected NAICS codes.

        Returns:
            Optional[List[str]]: A list of selected NAICS codes.

        """
        sectors = self._get_available_plastic_sectors()
        return self._select_items(title="Plastic Sectors", items=sectors, key_column="NAICS Code", value_column="Description")

    def select_additives(self) -> Optional[List[str]]:
        """Display a menu to select plastic additives and return the selected CASRNs.

        Returns:
            Optional[List[str]]: A list of selected CASRNs.

        """
        additives = self._get_available_plastic_additives()
        return self._select_items(title="Plastic Additives", items=additives, key_column="CASRN", value_column="Name")

    def select_additive_related_uses(self) -> Optional[List[str]]:
        """Display a menu to select additive-related uses and return the selected uses.

        Returns:
            Optional[List[str]]: A list of selected uses.

        """
        uses = self._get_available_additive_related_uses()
        return self._select_items(title="Additive-Related Uses", items=uses, key_column="Use", value_column="Description")

    def _display_records_stats(self, df: pd.DataFrame) -> None:

        if df.empty:
            self.console.print("[bold red]No records found for the selected criteria.[/bold red]")
        else:
            self._print_dataframe_as_table_with_save_option(df)

    def _save_dataframe_to_excel(self, df: pd.DataFrame) -> None:
        export = questionary.confirm(
            "Would you like to save these results to an Excel file?",
        ).ask()

        if export:
            default_file_path = ResultsStorage.get_default_file_path()
            file_path = questionary.text(
                f"Enter the path to save the Excel file (default: {default_file_path}):",
                default=default_file_path,
            ).ask()
            try:
                ResultsStorage.save_dataframe_to_excel(df, file_path)
                self.console.print(f"[bold green]Results successfully exported to {file_path}.[/bold green]")
            except Exception as e:
                self.console.print(f"[bold red]Failed to save Excel file: {e}[/bold red]")

    def _print_dataframe_as_table_with_save_option(self, df: pd.DataFrame) -> None:
        table = Table(title="Query Results")

        for column in df.columns:
            table.add_column(column, style="cyan", no_wrap=True)

        for _, row in df.iterrows():
            table.add_row(*[str(cell) for cell in row])

        try:
            with self.console.pager():
                self.console.print(table)
                self.console.print(
                    "\n[bold yellow]Use arrow keys to scroll and 'q' to exit.[/bold yellow]",
                    overflow="fold",
                    justify="left",
                )
        finally:
            self._save_dataframe_to_excel(df)

    def initial_record_exploration(self):
        """Display a menu to select the initial record exploration options."""
        choice = questionary.select(
            "What would you like to do?",
            choices=[
                "Select Plastic Sector",
                "Select Additives",
                "Select Additive-Related Uses",
                "Select End-of-Life Activities",
                "Select All Filters",
                "Exit",
            ],
        ).ask()

        if choice == "Select Plastic Sector":
            selected_code = cli.select_plastic_sector()
            df = self.tri_db_filter.get_records_stats_by_naics_code(selected_code)
            self._display_records_stats(df)
        elif choice == "Select Additives":
            selected_additives = cli.select_additives()
            df = self.tri_db_filter.get_records_stats_by_additive(selected_additives)
            self._display_records_stats(df)
        elif choice == "Select Additive-Related Uses":
            selected_uses = cli.select_additive_related_uses()
            df = self.tri_db_filter.get_records_stats_by_additive_related_use(selected_uses)
            self._display_records_stats(df)
        elif choice == "Select End-of-Life Activities":
            selected_activities = cli.select_end_of_life_activities()
            df = self.tri_db_filter.get_records_stats_by_end_of_life_activity(selected_activities)
            self._display_records_stats(df)
        elif choice == "Select All Filters":
            selected_code = cli.select_plastic_sector()
            selected_additives = cli.select_additives()
            selected_uses = cli.select_additive_related_uses()
            selected_activities = cli.select_end_of_life_activities()

            df = self.tri_db_filter.get_records_stats_by_all_filters(
                selected_code, selected_additives, selected_uses, selected_activities
            )
            self._display_records_stats(df)

        elif choice == "Exit":
            cli.console.print("[bold green]Goodbye![/bold green]")


if __name__ == "__main__":
    # This is only used for smoke testing
    import hydra

    with hydra.initialize(
        version_base=None,
        config_path="../../../conf",
        job_name="smoke-testing-tri",
    ):
        cfg = hydra.compose(config_name="main")
        cli = InteractiveCLI(cfg)

        selected_options = cli.initial_record_exploration()

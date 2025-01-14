# -*- coding: utf-8 -*-
# !/usr/bin/env python

"""Main module for generating analysis reports on plastic additives data.

This module provides a class, `Tri4PlasticAdditives`, which initializes the configuration settings
and generates the analysis report on plastic additives data.

"""

from importlib.resources import as_file, files

import hydra

from src.tri4plads.generate_analysis.interactive_cli import InteractiveCLI


class Tri4PlasticAdditives:
    """Class for generating analysis reports on plastic additives data.

    This class provides an interface for generating analysis reports on plastic additives data
    using the Tri4PlasticAdditives dataset. It initializes the configuration settings and
    runs the analysis using the specified settings.

    """

    def __init__(self):
        self._start_config()
        self.cli = InteractiveCLI(self.cfg)

    def _get_conf_path(self) -> str:
        try:
            return "../../../conf"
        except ImportError:
            conf_path = files("tri4plads") / "conf"
            with as_file(conf_path) as path:
                return str(path)

    def _start_config(self):
        config_path = self._get_conf_path()
        with hydra.initialize(
            version_base=None,
            config_path=config_path,
            job_name="tri-4-plastic-additives",
        ):
            self.cfg = hydra.compose(config_name="main")

    def run(self):
        """Run the top-level menu for the CLI."""
        try:
            self.cli.main_menu()
        except Exception as e:
            self.cli.console.print(f"[bold red]An error occurred: {e}[/bold red]")


if __name__ == "__main__":
    try:
        app = Tri4PlasticAdditives()
        app.run()
    except Exception as e:
        print(f"[bold red]Failed to start the application: {e}[/bold red]")

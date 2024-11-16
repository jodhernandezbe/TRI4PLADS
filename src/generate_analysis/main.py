# -*- coding: utf-8 -*-
# !/usr/bin/env python

"""Main module for generating analysis reports on plastic additives data.

This module provides a class, `Tri4PlasticAdditives`, which initializes the configuration settings
and generates the analysis report on plastic additives data.

"""

import hydra

from src.generate_analysis.interactive_cli import InteractiveCLI


class Tri4PlasticAdditives:
    """Class for generating analysis reports on plastic additives data.

    This class provides an interface for generating analysis reports on plastic additives data
    using the Tri4PlasticAdditives dataset. It initializes the configuration settings and
    runs the analysis using the specified settings.

    """

    def __init__(self):
        self._start_config()
        self.cli = InteractiveCLI(self.cfg)

    def _start_config(self):
        with hydra.initialize(
            version_base=None,
            config_path="../../conf",
            job_name="tri-4-plastic-additives",
        ):
            self.cfg = hydra.compose(config_name="main")

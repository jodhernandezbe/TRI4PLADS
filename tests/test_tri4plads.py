import pytest

from src import Tri4PlasticAdditives


def test_initialization():

    tri = Tri4PlasticAdditives()
    assert tri.cli is not None
    assert tri.cfg is not None

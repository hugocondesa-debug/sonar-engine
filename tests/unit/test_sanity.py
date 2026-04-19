"""Sanity checks — baseline package importability."""

import sonar


def test_import_sonar() -> None:
    assert sonar is not None

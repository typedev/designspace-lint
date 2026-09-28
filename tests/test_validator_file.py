# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
0.0: the document itself cannot be read -- missing, or not a designspace.

Everything else depends on this, so it is structural and stops the run.
"""

from designspace_lint.checkers.file import FILE_CANNOT_READ, FileChecker


def _results(path):
    return list(FileChecker(path=path).check())


def test_a_missing_file_is_reported(tmp_path):
    results = _results(tmp_path / "Nope.designspace")
    assert [r.code for r in results] == [FILE_CANNOT_READ]
    assert results[0].is_structural


def test_a_file_that_is_not_xml_is_reported(tmp_path):
    path = tmp_path / "Broken.designspace"
    path.write_text("<designspace format='5.0'><axes>")
    assert [r.code for r in _results(path)] == [FILE_CANNOT_READ]


def test_a_readable_file_is_fine(tmp_path):
    path = tmp_path / "Fine.designspace"
    path.write_text(
        '<?xml version="1.0"?><designspace format="5.0"><axes>'
        '<axis tag="wght" name="Weight" minimum="100" default="400" maximum="900"/>'
        "</axes></designspace>"
    )
    assert _results(path) == []

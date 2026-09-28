# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Every finding any test produces is checked against the public code catalogue.

`designspace_lint.codes.CODES` promises consumers a title, a severity and the
`raw_data` keys ("locators") of each code. Rather than a separate fixture per
code, this watches every result the whole suite makes and fails the test that
made one the catalogue does not describe.
"""

import pytest

from designspace_lint.checkers import base
from designspace_lint.codes import CODES
from designspace_lint.model import effective_severity


@pytest.fixture(autouse=True)
def _results_match_the_catalogue(monkeypatch):
    problems = []
    original = base.BaseChecker._make_result

    def recording(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        info = CODES.get((result.category, result.code))
        where = f"{result.category}.{result.code}"
        if info is None:
            problems.append(f"{where} is not in CODES")
        elif info.retired:
            problems.append(f"{where} is marked retired but was emitted")
        else:
            if effective_severity(result) not in info.severities:
                problems.append(
                    f"{where} emitted at severity {effective_severity(result)}, "
                    f"catalogue says {info.severities}"
                )
            missing = [key for key in info.locators if key not in result.raw_data]
            if missing:
                problems.append(f"{where} lacks locator(s) {missing}")
        return result

    monkeypatch.setattr(base.BaseChecker, "_make_result", recording)
    yield
    assert not problems, "; ".join(sorted(set(problems)))

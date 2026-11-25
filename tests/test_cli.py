# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""The command line: exit codes, and `--json` carrying what a fixer acts on."""

import json

from designspace_lint import cli
from dsxml import WEIGHT, source, xml


def test_json_carries_the_raw_data(tmp_path, capsys):
    path = tmp_path / "test.designspace"
    path.write_text(xml(WEIGHT, source("Missing.ufo", Weight=400)))
    assert cli.main([str(path), "--json"]) == 1
    findings = json.loads(capsys.readouterr().out)

    assert findings and all("raw_data" in f for f in findings)
    missing = [f for f in findings if f["code"] == "2.1"]
    assert missing and missing[0]["raw_data"]["sourceName"] == "Missing.ufo"


def test_values_json_cannot_write_are_written_as_lists_or_text():
    assert cli._jsonable({"b", "a"}) == ["a", "b"]
    assert cli._jsonable(frozenset()) == []
    assert cli._jsonable(object()).startswith("<object")

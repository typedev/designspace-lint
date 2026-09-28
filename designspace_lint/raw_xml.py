# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
What the designspace file says before fontTools has read it.

fontTools' reader drops a location dimension that names an axis the document
does not declare -- a log warning, and the value is gone
(`designspaceLib.BaseDocReader.readLocationElement`). Checks that look at the
parsed document therefore never see it: a source written for an axis that was
later renamed quietly moves to that axis' default. The only place the mistake
is still visible is the file itself, so this reads it again, as plain XML.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StrayDimension:
    """A `<dimension>` naming an axis the document does not have."""

    #: "source", "instance" or "label"
    kind: str
    #: The element's name attribute, or its position when it has none.
    owner: str
    #: The axis the dimension names.
    axis: str


def undeclared_axis_dimensions(path) -> list[StrayDimension]:
    """Every location dimension in the file that names an undeclared axis.

    Empty when there is no file to read or it does not parse: whether the
    document can be read at all is 0.0's business, not this.
    """
    if not path:
        return []
    try:
        root = ET.parse(Path(path)).getroot()
    except (OSError, ET.ParseError) as exc:
        logger.debug(f"cannot re-read {path}: {exc}")
        return []

    # Discrete axes are <axis values="..."> too.
    axes = {axis.get("name") for axis in root.iterfind("axes/axis")}

    found = []
    for kind, xpath in (
        ("source", "sources/source"),
        ("instance", "instances/instance"),
        ("label", "labels/label"),
    ):
        for index, element in enumerate(root.iterfind(xpath)):
            styled = " ".join(n for n in (element.get("familyname"), element.get("stylename")) if n)
            owner = element.get("name") or element.get("filename") or styled or f"#{index + 1}"
            for dimension in element.iterfind("location/dimension"):
                axis = dimension.get("name")
                if axis and axis not in axes:
                    found.append(StrayDimension(kind, owner, axis))
    return found

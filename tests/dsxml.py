# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Designspace documents written as XML, for the checks that need only the document.

The cases here come from the September 2026 audit (`docs/audit/2026-09-coverage`),
and the XML is the form they were reported in: writing the document out keeps
the test honest about what fontTools' reader does with it -- dropping an axis it
does not know, keeping a label it cannot resolve -- which building descriptors
by hand would skip.
"""

from fontTools.designspaceLib import DesignSpaceDocument

WEIGHT = '<axis tag="wght" name="Weight" minimum="100" default="400" maximum="900"/>'
ITALIC = '<axis tag="ital" name="Italic" values="0 1" default="0"/>'


def source(filename, **location):
    dims = "".join(f'<dimension name="{k}" xvalue="{v}"/>' for k, v in location.items())
    return f'<source filename="{filename}" name="{filename}"><location>{dims}</location></source>'


def xml(
    axes,
    sources="",
    *,
    instances="",
    rules="",
    mappings="",
    labels="",
    variable_fonts="",
    fmt="5.0",
):
    """The document's text, from its parts, each a string of XML elements."""
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><designspace format="{fmt}">'
        f"<axes>{axes}{mappings}</axes>"
        + (f"<labels>{labels}</labels>" if labels else "")
        + (f"<rules>{rules}</rules>" if rules else "")
        + f"<sources>{sources}</sources>"
        + (f"<instances>{instances}</instances>" if instances else "")
        + (f"<variable-fonts>{variable_fonts}</variable-fonts>" if variable_fonts else "")
        + "</designspace>"
    )


def ds(*parts, **kwargs):
    """The document, read by fontTools from `xml(...)`; its path goes nowhere."""
    doc = DesignSpaceDocument.fromstring(xml(*parts, **kwargs))
    doc.path = "/tmp/fake/test.designspace"
    return doc


def written(tmp_path, *parts, **kwargs):
    """The document written to disk first, for the checks that re-read the file."""
    path = tmp_path / "test.designspace"
    path.write_text(xml(*parts, **kwargs))
    return DesignSpaceDocument.fromfile(str(path))

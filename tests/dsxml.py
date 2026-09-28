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


def ds(axes, sources="", *, instances="", rules="", mappings="", labels="", fmt="5.0"):
    """A document from its parts, each a string of XML elements."""
    xml = (
        f'<?xml version="1.0" encoding="UTF-8"?><designspace format="{fmt}">'
        f"<axes>{axes}{mappings}</axes>"
        + (f"<labels>{labels}</labels>" if labels else "")
        + (f"<rules>{rules}</rules>" if rules else "")
        + f"<sources>{sources}</sources>"
        + (f"<instances>{instances}</instances>" if instances else "")
        + "</designspace>"
    )
    doc = DesignSpaceDocument.fromstring(xml)
    doc.path = "/tmp/fake/test.designspace"
    return doc

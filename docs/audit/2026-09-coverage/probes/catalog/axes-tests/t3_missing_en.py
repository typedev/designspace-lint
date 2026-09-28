import sys
from fontTools.ttLib import TTFont, newTable
import fontTools.otlLib.builder as otl

font = TTFont()
font["name"] = newTable("name")
font["name"].names = []

axes = [dict(tag="wght", name={"de": "Gewicht"}, ordering=0, values=[
    dict(name={"de": "Fett"}, value=700, flags=0)
])]
otl.buildStatTable(font, axes)
for rec in font["name"].names:
    print(rec.nameID, rec.platformID, rec.langID, rec.toUnicode())

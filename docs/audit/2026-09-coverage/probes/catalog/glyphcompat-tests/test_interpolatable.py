"""
Confirm concrete claims about fontTools.varLib.interpolatable using two
minimal, hand-built glyphsets (dicts of drawable glyph-like objects), no
UFO/TTF files needed.
"""
from fontTools.varLib.interpolatable import test as interpolatable_test
from fontTools.pens.recordingPen import RecordingPen


class SimpleGlyph:
    """Minimal glyph-like object: has .draw(pen)."""

    def __init__(self, contours):
        # contours: list of list of ('moveTo',[pt]) etc, replayed via RecordingPen semantics
        self._contours = contours

    def draw(self, pen, outputImpliedClosingLine=False):
        for contour in self._contours:
            for op, args in contour:
                getattr(pen, op)(*args)


def contour_square():
    return [
        ("moveTo", ((0, 0),)),
        ("lineTo", ((0, 100),)),
        ("lineTo", ((100, 100),)),
        ("lineTo", ((100, 0),)),
        ("closePath", ()),
    ]


def contour_triangle():
    return [
        ("moveTo", ((0, 0),)),
        ("lineTo", ((50, 100),)),
        ("lineTo", ((100, 0),)),
        ("closePath", ()),
    ]


# --- Test 1: PATH_COUNT mismatch (different number of contours) ---
master_a = {"A": SimpleGlyph([contour_square()])}
master_b = {"A": SimpleGlyph([contour_square(), contour_square()])}  # 2 contours

problems = interpolatable_test(
    [master_a, master_b], glyphs=["A"], names=["master_a", "master_b"]
)
print("=== Test 1: contour count mismatch ===")
for glyphname, plist in problems.items():
    for p in plist:
        print(" ", glyphname, p["type"], {k: v for k, v in p.items() if k != "type"})

# --- Test 2: NODE_COUNT mismatch (same contour count, different node count) ---
master_c = {"B": SimpleGlyph([contour_square()])}
master_d = {"B": SimpleGlyph([contour_triangle()])}
problems2 = interpolatable_test(
    [master_c, master_d], glyphs=["B"], names=["master_c", "master_d"]
)
print("=== Test 2: node count mismatch (square vs triangle) ===")
for glyphname, plist in problems2.items():
    for p in plist:
        print(" ", glyphname, p["type"], {k: v for k, v in p.items() if k != "type"})

# --- Test 3: MISSING glyph in one master ---
master_e = {"C": SimpleGlyph([contour_square()]), "D": SimpleGlyph([contour_square()])}
master_f = {"C": SimpleGlyph([contour_square()]), "D": None}  # "D" missing (as real glyphsets represent it)
problems3 = interpolatable_test(
    [master_e, master_f], glyphs=["C", "D"], names=["master_e", "master_f"]
)
print("=== Test 3: missing glyph in non-default master ===")
for glyphname, plist in problems3.items():
    for p in plist:
        print(" ", glyphname, p["type"], {k: v for k, v in p.items() if k != "type"})

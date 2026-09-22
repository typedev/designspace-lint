# Copyright 2026 Alexander Lubovenko
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Reading and repairing a font's glyphOrder.

The reading half now lives in `designspace_lint.glyph_order`, because the
checks need it too and two copies of a function this subtle would drift. It is
re-exported here so the thirty-odd call sites in font-rover keep their import.
`normalize_glyph_order` stays: it *writes* to the font, which a lint library
has no business doing.
"""

import logging
from typing import Any

from designspace_lint.glyph_order import (
    _first_wins,
    _raw_glyph_order,
    duplicate_glyph_order_names,
    safe_glyph_order,
)

logger = logging.getLogger(__name__)

__all__ = [
    "safe_glyph_order",
    "duplicate_glyph_order_names",
    "normalize_glyph_order",
]


def normalize_glyph_order(font: Any) -> int:
    """Rewrite a font's glyphOrder without repeats, in place.

    Unlike `safe_glyph_order` this changes the font, so the next writer puts a
    clean list on disk. A font whose order is already clean is left untouched
    and is *not* marked dirty.

    Args:
        font: fontParts (or defcon) font object.

    Returns:
        How many entries were removed; 0 when there was nothing to repair.
    """
    raw = _raw_glyph_order(font)
    if not raw:
        return 0

    kept = _first_wins(raw)
    removed = len(raw) - len(kept)
    if not removed:
        return 0

    font.glyphOrder = kept
    logger.info(
        "Removed %d duplicate name(s) from glyphOrder: %s",
        removed,
        ", ".join(duplicate_glyph_order_names(raw)),
    )
    return removed

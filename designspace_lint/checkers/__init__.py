"""
DesignSpace validation checkers.

Each checker validates a specific category of problems.

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from .axes import AxesChecker
from .base import BaseChecker
from .features import FeaturesChecker
from .file import FileChecker
from .fontinfo import FontInfoChecker
from .glyphorder import GlyphOrderChecker
from .glyphs import GlyphsChecker
from .instances import InstancesChecker
from .kerning import KerningChecker
from .rules import RulesChecker
from .sources import SourcesChecker

__all__ = [
    "BaseChecker",
    "FileChecker",
    "AxesChecker",
    "SourcesChecker",
    "InstancesChecker",
    "GlyphsChecker",
    "KerningChecker",
    "FontInfoChecker",
    "RulesChecker",
    "FeaturesChecker",
    "GlyphOrderChecker",
]

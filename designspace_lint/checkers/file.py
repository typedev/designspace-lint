"""
File checker - validates designspace file can be loaded.

Category 0: File validation
- 0.0: File cannot be read/parsed

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

import logging
from typing import Iterator

from ..model import CATEGORY_FILE, CheckResult
from .base import BaseChecker

logger = logging.getLogger(__name__)

# Error codes
FILE_CANNOT_READ = 0


class FileChecker(BaseChecker):
    """
    Validates that the designspace file can be read.

    Checks:
    - 0.0: File exists and can be parsed as valid XML
    """

    CATEGORY = CATEGORY_FILE

    def check(self) -> Iterator[CheckResult]:
        """Check file can be read."""
        try:
            # Try to access the doc - this will load it if needed
            doc = self.doc
            if doc is None:
                yield self._make_result(
                    code=FILE_CANNOT_READ,
                    description="DesignSpace file could not be loaded",
                    is_structural=True,
                )
                return

            # Check basic structure
            if not hasattr(doc, "axes") or not hasattr(doc, "sources"):
                yield self._make_result(
                    code=FILE_CANNOT_READ,
                    description="DesignSpace file has invalid structure",
                    is_structural=True,
                )

        except FileNotFoundError:
            yield self._make_result(
                code=FILE_CANNOT_READ,
                description="DesignSpace file not found",
                location=str(self.path) if self.path else "",
                is_structural=True,
            )
        except Exception as e:
            yield self._make_result(
                code=FILE_CANNOT_READ,
                description=f"DesignSpace file cannot be read: {e}",
                location=str(self.path) if self.path else "",
                is_structural=True,
            )

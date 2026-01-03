"""
Logging utilities for apflow

DEPRECATED: This module location is deprecated for backward compatibility.
New code should use: from apflow.logger import get_logger

Rationale:
- Avoids circular imports (core depends on logger, but logger was in core)
- Improves CLI startup performance (doesn't load apflow.core)
- Cleaner import path: apflow.logger instead of apflow.core.utils.logger
"""

# Re-export from top-level logger to maintain backward compatibility
from apflow.logger import get_logger, ColoredFormatter

__all__ = ["get_logger", "ColoredFormatter"]





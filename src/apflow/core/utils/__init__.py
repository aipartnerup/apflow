"""
Utility functions for apflow

Note: Do NOT re-export get_logger here to avoid triggering apflow.core.__init__.py
Users should import directly: from apflow.logger import get_logger
"""

__all__ = [
    "get_logger",
]


def __getattr__(name):
    """Lazy import to avoid loading parent package apflow.core"""
    if name == "get_logger":
        from apflow.logger import get_logger
        return get_logger
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")



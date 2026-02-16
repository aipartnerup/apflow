"""Skip performance tests when psutil is not installed."""

import pytest

psutil = pytest.importorskip("psutil", reason="psutil not installed")

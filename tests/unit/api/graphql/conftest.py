"""Skip all GraphQL tests when strawberry-graphql is not installed."""

import pytest

strawberry = pytest.importorskip("strawberry", reason="strawberry-graphql not installed")

"""Tests for PlacementEngine constraint evaluation."""

from datetime import datetime, timezone

from apflow.core.distributed.placement import PlacementEngine, PlacementResult
from apflow.core.storage.sqlalchemy.models import DistributedNode


def _make_node(
    node_id: str,
    executor_types: list[str] | None = None,
    capabilities: dict | None = None,
    status: str = "healthy",
) -> DistributedNode:
    """Helper to create a DistributedNode for testing."""
    return DistributedNode(
        node_id=node_id,
        executor_types=executor_types or ["a2a"],
        capabilities=capabilities or {},
        status=status,
        heartbeat_at=datetime.now(timezone.utc),
    )


class TestPlacementEngine:
    """Test PlacementEngine.find_eligible_nodes with various constraints."""

    def test_no_constraints_returns_all_healthy_nodes(self) -> None:
        """Tasks without placement_constraints match all healthy nodes."""
        engine = PlacementEngine()
        nodes = [_make_node("node-1"), _make_node("node-2"), _make_node("node-3")]

        result = engine.find_eligible_nodes(
            placement_constraints=None,
            healthy_nodes=nodes,
            active_leases_by_node={},
            max_parallel_per_node=4,
        )

        assert len(result) == 3
        assert {n.node_id for n in result} == {"node-1", "node-2", "node-3"}

    def test_requires_executors_filters_nodes(self) -> None:
        """Only nodes with matching executor_types are eligible."""
        engine = PlacementEngine()
        nodes = [
            _make_node("node-1", executor_types=["a2a", "mcp"]),
            _make_node("node-2", executor_types=["a2a"]),
            _make_node("node-3", executor_types=["mcp"]),
        ]

        result = engine.find_eligible_nodes(
            placement_constraints={"require_executors": ["a2a", "mcp"]},
            healthy_nodes=nodes,
            active_leases_by_node={},
            max_parallel_per_node=4,
        )

        assert len(result) == 1
        assert result[0].node_id == "node-1"

    def test_requires_capabilities_filters_nodes(self) -> None:
        """Only nodes with matching capabilities entries are eligible."""
        engine = PlacementEngine()
        nodes = [
            _make_node("node-1", capabilities={"gpu": True, "memory": "high"}),
            _make_node("node-2", capabilities={"gpu": False, "memory": "high"}),
            _make_node("node-3", capabilities={"memory": "high"}),
        ]

        result = engine.find_eligible_nodes(
            placement_constraints={"require_capabilities": {"gpu": True}},
            healthy_nodes=nodes,
            active_leases_by_node={},
            max_parallel_per_node=4,
        )

        assert len(result) == 1
        assert result[0].node_id == "node-1"

    def test_allowed_nodes_whitelist(self) -> None:
        """Only nodes in allowed_nodes list are eligible."""
        engine = PlacementEngine()
        nodes = [_make_node("node-1"), _make_node("node-2"), _make_node("node-3")]

        result = engine.find_eligible_nodes(
            placement_constraints={"allowed_nodes": ["node-1", "node-3"]},
            healthy_nodes=nodes,
            active_leases_by_node={},
            max_parallel_per_node=4,
        )

        assert len(result) == 2
        assert {n.node_id for n in result} == {"node-1", "node-3"}

    def test_forbidden_nodes_blacklist(self) -> None:
        """Nodes in forbidden_nodes list are excluded."""
        engine = PlacementEngine()
        nodes = [_make_node("node-1"), _make_node("node-2"), _make_node("node-3")]

        result = engine.find_eligible_nodes(
            placement_constraints={"forbidden_nodes": ["node-2"]},
            healthy_nodes=nodes,
            active_leases_by_node={},
            max_parallel_per_node=4,
        )

        assert len(result) == 2
        assert {n.node_id for n in result} == {"node-1", "node-3"}

    def test_allowed_and_forbidden_combined(self) -> None:
        """forbidden_nodes takes precedence over allowed_nodes."""
        engine = PlacementEngine()
        nodes = [_make_node("node-1"), _make_node("node-2"), _make_node("node-3")]

        result = engine.find_eligible_nodes(
            placement_constraints={
                "allowed_nodes": ["node-1", "node-2"],
                "forbidden_nodes": ["node-2"],
            },
            healthy_nodes=nodes,
            active_leases_by_node={},
            max_parallel_per_node=4,
        )

        assert len(result) == 1
        assert result[0].node_id == "node-1"

    def test_max_parallel_per_node_enforcement(self) -> None:
        """Nodes at max_parallel_per_node active leases are excluded."""
        engine = PlacementEngine()
        nodes = [_make_node("node-1"), _make_node("node-2")]

        result = engine.find_eligible_nodes(
            placement_constraints=None,
            healthy_nodes=nodes,
            active_leases_by_node={"node-1": 4, "node-2": 2},
            max_parallel_per_node=4,
        )

        assert len(result) == 1
        assert result[0].node_id == "node-2"

    def test_empty_eligible_nodes_returns_empty_list(self) -> None:
        """When no nodes match, returns empty list."""
        engine = PlacementEngine()
        nodes = [_make_node("node-1"), _make_node("node-2")]

        result = engine.find_eligible_nodes(
            placement_constraints={"require_executors": ["grpc"]},
            healthy_nodes=nodes,
            active_leases_by_node={},
            max_parallel_per_node=4,
        )

        assert result == []

    def test_none_constraints_same_as_empty(self) -> None:
        """None constraints treated same as no constraints."""
        engine = PlacementEngine()
        nodes = [_make_node("node-1"), _make_node("node-2")]

        result_none = engine.find_eligible_nodes(
            placement_constraints=None,
            healthy_nodes=nodes,
            active_leases_by_node={},
            max_parallel_per_node=4,
        )
        result_empty = engine.find_eligible_nodes(
            placement_constraints={},
            healthy_nodes=nodes,
            active_leases_by_node={},
            max_parallel_per_node=4,
        )

        assert len(result_none) == len(result_empty) == 2


class TestPlacementResult:
    """Test PlacementResult dataclass."""

    def test_placement_result_defaults(self) -> None:
        """PlacementResult has correct default values."""
        result = PlacementResult(node_id="node-1", eligible=True)
        assert result.reason == ""

    def test_placement_result_with_reason(self) -> None:
        """PlacementResult stores reason for ineligibility."""
        result = PlacementResult(node_id="node-1", eligible=False, reason="at max parallel limit")
        assert not result.eligible
        assert result.reason == "at max parallel limit"


class TestCheckExecutorTypes:
    """Test PlacementEngine._check_executor_types."""

    def test_node_with_all_required_executors(self) -> None:
        """Returns True when node has all required executor types."""
        engine = PlacementEngine()
        node = _make_node("node-1", executor_types=["a2a", "mcp", "grpc"])
        assert engine._check_executor_types(node, ["a2a", "mcp"]) is True

    def test_node_missing_some_executors(self) -> None:
        """Returns False when node is missing required executor types."""
        engine = PlacementEngine()
        node = _make_node("node-1", executor_types=["a2a"])
        assert engine._check_executor_types(node, ["a2a", "mcp"]) is False

    def test_empty_required_executors(self) -> None:
        """Returns True when no executors are required."""
        engine = PlacementEngine()
        node = _make_node("node-1", executor_types=["a2a"])
        assert engine._check_executor_types(node, []) is True


class TestCheckCapabilities:
    """Test PlacementEngine._check_capabilities."""

    def test_node_with_all_required_capabilities(self) -> None:
        """Returns True when node has all required capabilities."""
        engine = PlacementEngine()
        node = _make_node("node-1", capabilities={"gpu": True, "memory": "high"})
        assert engine._check_capabilities(node, {"gpu": True}) is True

    def test_node_with_wrong_capability_value(self) -> None:
        """Returns False when capability value doesn't match."""
        engine = PlacementEngine()
        node = _make_node("node-1", capabilities={"gpu": False})
        assert engine._check_capabilities(node, {"gpu": True}) is False

    def test_node_missing_capability_key(self) -> None:
        """Returns False when capability key is missing from node."""
        engine = PlacementEngine()
        node = _make_node("node-1", capabilities={})
        assert engine._check_capabilities(node, {"gpu": True}) is False


class TestCheckParallelLimit:
    """Test PlacementEngine._check_parallel_limit."""

    def test_under_limit(self) -> None:
        """Returns True when node is under parallel limit."""
        engine = PlacementEngine()
        assert engine._check_parallel_limit("node-1", {"node-1": 2}, 4) is True

    def test_at_limit(self) -> None:
        """Returns False when node is at parallel limit."""
        engine = PlacementEngine()
        assert engine._check_parallel_limit("node-1", {"node-1": 4}, 4) is False

    def test_over_limit(self) -> None:
        """Returns False when node is over parallel limit."""
        engine = PlacementEngine()
        assert engine._check_parallel_limit("node-1", {"node-1": 5}, 4) is False

    def test_no_leases_recorded(self) -> None:
        """Returns True when node has no recorded leases."""
        engine = PlacementEngine()
        assert engine._check_parallel_limit("node-1", {}, 4) is True

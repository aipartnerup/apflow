"""Placement constraint evaluation for distributed task assignment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from apflow.core.storage.sqlalchemy.models import DistributedNode
from apflow.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PlacementResult:
    """Result of placement evaluation for a single node."""

    node_id: str
    eligible: bool
    reason: str = ""


class PlacementEngine:
    """Evaluates placement constraints and filters eligible nodes.

    Constraints dict format:
    {
        "require_executors": ["a2a", "mcp"],  # node must support all listed
        "require_capabilities": {"gpu": True},  # node capabilities must match
        "allowed_nodes": ["node-1", "node-2"],  # whitelist (optional)
        "forbidden_nodes": ["node-3"],  # blacklist (optional)
    }
    """

    def find_eligible_nodes(
        self,
        placement_constraints: dict[str, Any] | None,
        healthy_nodes: list[DistributedNode],
        active_leases_by_node: dict[str, int],
        max_parallel_per_node: int,
    ) -> list[DistributedNode]:
        """Evaluate constraints and return eligible nodes.

        Filters healthy nodes through each constraint check in order:
        1. Parallel limit (capacity check)
        2. Forbidden nodes blacklist
        3. Allowed nodes whitelist
        4. Required executor types
        5. Required capabilities
        """
        constraints = placement_constraints or {}
        eligible: list[DistributedNode] = []

        for node in healthy_nodes:
            result = self._evaluate_node(
                node, constraints, active_leases_by_node, max_parallel_per_node
            )
            if result.eligible:
                eligible.append(node)
            else:
                logger.info(
                    "Node %s excluded from placement: %s",
                    result.node_id,
                    result.reason,
                )

        return eligible

    def _evaluate_node(
        self,
        node: DistributedNode,
        constraints: dict[str, Any],
        active_leases: dict[str, int],
        max_per_node: int,
    ) -> PlacementResult:
        """Evaluate all constraints for a single node."""
        node_id = str(node.node_id)

        if not self._check_parallel_limit(node_id, active_leases, max_per_node):
            return PlacementResult(node_id=node_id, eligible=False, reason="at max parallel limit")

        forbidden = constraints.get("forbidden_nodes", [])
        if forbidden and node_id in forbidden:
            return PlacementResult(node_id=node_id, eligible=False, reason="in forbidden_nodes")

        allowed = constraints.get("allowed_nodes")
        if allowed is not None and node_id not in allowed:
            return PlacementResult(node_id=node_id, eligible=False, reason="not in allowed_nodes")

        required_executors = constraints.get("require_executors", [])
        if required_executors and not self._check_executor_types(node, required_executors):
            return PlacementResult(
                node_id=node_id,
                eligible=False,
                reason="missing required executor types",
            )

        required_capabilities = constraints.get("require_capabilities", {})
        if required_capabilities and not self._check_capabilities(node, required_capabilities):
            return PlacementResult(
                node_id=node_id,
                eligible=False,
                reason="missing required capabilities",
            )

        return PlacementResult(node_id=node_id, eligible=True)

    def _check_executor_types(self, node: DistributedNode, required: list[str]) -> bool:
        """Check if node supports all required executor types."""
        node_executors = set(cast(list[str], node.executor_types or []))
        return all(executor in node_executors for executor in required)

    def _check_capabilities(self, node: DistributedNode, required: dict[str, Any]) -> bool:
        """Check if node capabilities satisfy requirements."""
        node_caps = node.capabilities or {}
        return all(key in node_caps and node_caps[key] == value for key, value in required.items())

    def _check_parallel_limit(
        self, node_id: str, active_leases: dict[str, int], max_per_node: int
    ) -> bool:
        """Check if node hasn't reached max parallel tasks."""
        current_count = active_leases.get(node_id, 0)
        return current_count < max_per_node

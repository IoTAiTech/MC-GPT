# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.6.0-beta.3 | Date: 2026-08-06
from __future__ import annotations

import unittest

from iot_ai.graph_runtime import (
    ExecutionGraph,
    GraphEdge,
    GraphNode,
    GraphValidationError,
    compile_graph,
    execute_graph,
    resource_waves,
    topological_layers,
    validate_graph,
)
from iot_ai.roles import ROLE_CATALOG, select_roles

from tests.common import IsolatedHomeTestCase


class RoleGraphTests(IsolatedHomeTestCase):
    def test_role_selection_is_perspective_diverse(self) -> None:
        roles = {r.role_id for r in select_roles("Improve dashboard security, UX and performance", include_implementation=True)}
        self.assertTrue({"domain-architect", "security-challenger", "operator-ux-reviewer", "performance-engineer", "implementation-engineer"}.issubset(roles))

    def test_role_contract_has_authority_and_output(self) -> None:
        value = ROLE_CATALOG["security-challenger"].to_dict()
        self.assertIn("forbidden_actions", value["authority"])
        self.assertTrue(value["expected_output"]["independent_review"])

    def test_compiled_graph_is_valid(self) -> None:
        graph = compile_graph("Review dashboard security and performance", include_implementation=True)
        result = validate_graph(graph)
        self.assertEqual(result["decision"], "pass")
        self.assertIn("plan-acceptance", {node.node_id for node in graph.nodes})
        self.assertIn("final-audit", {node.node_id for node in graph.nodes})

    def test_graph_has_explicit_edge_types(self) -> None:
        graph = compile_graph("Review dashboard security", include_implementation=True)
        edge_types = {edge.edge_type for edge in graph.edges}
        self.assertIn("data", edge_types)
        self.assertIn("approval", edge_types)
        self.assertIn("control", edge_types)

    def test_topological_layers_cover_all_nodes(self) -> None:
        graph = compile_graph("Plan a secure API")
        layers = topological_layers(graph)
        self.assertEqual(sum(len(layer) for layer in layers), len(graph.nodes))

    def test_cycle_is_rejected(self) -> None:
        graph = ExecutionGraph("g", "c", "goal", "R1", "D0", 2, 1000, 30, 2)
        graph.nodes = [GraphNode("a", "requirements-analyst", "a", depends_on=("b",)), GraphNode("b", "requirements-analyst", "b", depends_on=("a",))]
        graph.edges = [GraphEdge("a", "b"), GraphEdge("b", "a")]
        with self.assertRaises(GraphValidationError):
            validate_graph(graph)

    def test_resource_waves_serialize_conflicts(self) -> None:
        nodes = [
            GraphNode("a", "requirements-analyst", "a", resources=("write:x",)),
            GraphNode("b", "requirements-analyst", "b", resources=("write:x",)),
            GraphNode("c", "requirements-analyst", "c", resources=("write:y",)),
        ]
        waves = resource_waves(nodes)
        self.assertGreaterEqual(len(waves), 2)
        self.assertFalse(any({"a", "b"}.issubset({n.node_id for n in wave}) for wave in waves))

    def test_execute_graph_blocks_required_failure(self) -> None:
        graph = ExecutionGraph("g", "c", "goal", "R1", "D0", 2, 10000, 60, 4)
        graph.nodes = [GraphNode("a", "requirements-analyst", "a", output_schema=("x",))]
        result = execute_graph(self.home, graph, lambda node, inputs, runtime: {"status": "failed", "failure_class": "test", "output": {}})
        self.assertEqual(result["decision"], "blocked")

    def test_execute_graph_records_metrics(self) -> None:
        graph = ExecutionGraph("g2", "c2", "goal", "R1", "D0", 2, 10000, 60, 4)
        graph.nodes = [GraphNode("a", "requirements-analyst", "a", output_schema=("x",))]
        result = execute_graph(self.home, graph, lambda node, inputs, runtime: {"status": "pass", "output": {"x": 1}})
        self.assertIn("parallel_efficiency", result["metrics"])
        self.assertEqual(result["metrics"]["passed_nodes"], 1)


if __name__ == "__main__":
    unittest.main()

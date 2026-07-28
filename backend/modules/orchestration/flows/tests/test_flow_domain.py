from __future__ import annotations

import pytest

from modules.orchestration.flows.application.dto import FlowEdgeDTO, FlowNodeDTO
from modules.orchestration.flows.domain import MappingError, resolve_mapping, validate_dag


def _node(key: str) -> FlowNodeDTO:
    return FlowNodeDTO(
        id=f"node_{key}",
        flow_version_id="flv_1",
        key=key,
        name=key,
        node_type="automation",
        automation_version_id=1,
        configuration={},
        input_mapping={},
        output_mapping={},
        condition=None,
        retry_policy={},
        timeout_policy={},
        failure_policy="fail_flow",
        execution_policy={},
        position_metadata={},
        created_at=None,
    )


def _edge(source: str, target: str) -> FlowEdgeDTO:
    return FlowEdgeDTO(
        id=f"edge_{source}_{target}",
        flow_version_id="flv_1",
        source_node_id=f"node_{source}",
        target_node_id=f"node_{target}",
        edge_type="success",
        condition=None,
        mapping={},
        created_at=None,
    )


def test_validate_dag_rejects_cycles() -> None:
    result = validate_dag([_node("a"), _node("b")], [_edge("a", "b"), _edge("b", "a")])

    assert not result.valid
    assert any(issue.code == "FLOW_CYCLE_DETECTED" for issue in result.issues)


def test_validate_dag_returns_topological_order() -> None:
    result = validate_dag([_node("a"), _node("b"), _node("c")], [_edge("a", "b"), _edge("a", "c")])

    assert result.valid
    assert result.topological_order[0] == "node_a"
    assert set(result.topological_order[1:]) == {"node_b", "node_c"}


def test_resolve_mapping_reads_flow_input_and_node_output() -> None:
    context = {
        "flow": {"input": {"company_id": 7}},
        "nodes": {"download": {"output": {"artifact_id": "art_1"}}},
    }

    assert resolve_mapping(
        {
            "company_id": {"source": "flow.input", "path": "$.company_id"},
            "artifact_id": {"source": "node.download.output", "path": "$.artifact_id"},
            "mode": {"value": "complete"},
        },
        context,
    ) == {"company_id": 7, "artifact_id": "art_1", "mode": "complete"}


def test_resolve_mapping_blocks_private_path_segments() -> None:
    with pytest.raises(MappingError):
        resolve_mapping({"secret": {"source": "flow.input", "path": "$.__token"}}, {"flow": {"input": {"__token": "x"}}})

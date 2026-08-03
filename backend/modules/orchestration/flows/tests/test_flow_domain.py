from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from modules.orchestration.flows.application.dto import FlowEdgeDTO, FlowNodeDTO, FlowVersionDTO
from modules.orchestration.flows.application.use_cases import ValidateFlowVersion
from modules.orchestration.flows.domain import MappingError, evaluate_condition, resolve_mapping, resolve_value, validate_dag


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


# ---- If / Else (bloco novo do catalogo lateral) ----
#
# O bloco "If / Else" nao usa node.condition (isso deixaria o proprio no "skipped" e
# quebraria as duas saidas — ver comentario em use_cases.ValidateFlowVersion). Em vez
# disso, a UI monta duas arestas "conditional": uma com a regra escolhida pelo usuario e
# outra com a mesma regra envolvida em {"operator": "not", ...}. Estes testes fixam esse
# contrato no dominio, que e a parte que o backend realmente garante.


def test_evaluate_condition_not_operator_negates_inner_condition() -> None:
    always_true = {"operator": "exists", "left": {"value": True}}
    context: dict = {"flow": {"input": {}}, "nodes": {}}

    assert evaluate_condition(always_true, context)["matched"] is True
    assert evaluate_condition({"operator": "not", "condition": always_true}, context)["matched"] is False


def test_evaluate_condition_if_else_branches_are_mutually_exclusive() -> None:
    rule = {"operator": "equals", "left": {"source": "flow.input", "path": "$.status"}, "right": {"value": "ok"}}
    false_branch = {"operator": "not", "condition": rule}

    matched_context = {"flow": {"input": {"status": "ok"}}, "nodes": {}}
    unmatched_context = {"flow": {"input": {"status": "erro"}}, "nodes": {}}

    assert evaluate_condition(rule, matched_context)["matched"] is True
    assert evaluate_condition(false_branch, matched_context)["matched"] is False
    assert evaluate_condition(rule, unmatched_context)["matched"] is False
    assert evaluate_condition(false_branch, unmatched_context)["matched"] is True


# ---- Switch (varios casos + saida padrao, todos via arestas "conditional") ----


def test_evaluate_condition_switch_case_and_default_are_mutually_exclusive() -> None:
    subject = {"source": "flow.input", "path": "$.tipo"}
    case_a = {"operator": "equals", "left": subject, "right": {"value": "a"}}
    case_b = {"operator": "equals", "left": subject, "right": {"value": "b"}}
    default = {"operator": "and", "conditions": [{"operator": "not", "condition": case_a}, {"operator": "not", "condition": case_b}]}

    context_a = {"flow": {"input": {"tipo": "a"}}, "nodes": {}}
    context_other = {"flow": {"input": {"tipo": "c"}}, "nodes": {}}

    assert evaluate_condition(case_a, context_a)["matched"] is True
    assert evaluate_condition(case_b, context_a)["matched"] is False
    assert evaluate_condition(default, context_a)["matched"] is False

    assert evaluate_condition(case_a, context_other)["matched"] is False
    assert evaluate_condition(case_b, context_other)["matched"] is False
    assert evaluate_condition(default, context_other)["matched"] is True


# ---- Transform Data ----


def test_resolve_value_applies_single_transform() -> None:
    context = {"flow": {"input": {"nome": "  ana silva  "}}, "nodes": {}}
    spec = {"source": "flow.input", "path": "$.nome", "transform": "trim"}
    assert resolve_value(spec, context) == "ana silva"


def test_resolve_value_chains_transforms_in_order() -> None:
    context = {"flow": {"input": {"nome": "  ana silva  "}}, "nodes": {}}
    spec = {"source": "flow.input", "path": "$.nome", "transform": ["trim", "uppercase"]}
    assert resolve_value(spec, context) == "ANA SILVA"


def test_resolve_value_to_number_and_round() -> None:
    context = {"flow": {"input": {"total": "12.6"}}, "nodes": {}}
    assert resolve_value({"source": "flow.input", "path": "$.total", "transform": "to_number"}, context) == 12.6
    assert resolve_value({"source": "flow.input", "path": "$.total", "transform": "round"}, context) == 13


def test_resolve_value_unknown_transform_raises() -> None:
    with pytest.raises(MappingError):
        resolve_value({"value": "x", "transform": "nao_existe"}, {"flow": {"input": {}}, "nodes": {}})


# ---- Validacao aceita os novos node_types do catalogo, preservando compatibilidade ----


class _FakeVersionsRepo:
    def __init__(self, version: FlowVersionDTO) -> None:
        self._version = version

    def get(self, flow_version_id: str) -> FlowVersionDTO | None:
        return self._version if flow_version_id == self._version.id else None

    def list_for_flow(self, flow_id: str) -> list[FlowVersionDTO]:
        return [self._version]


class _FakeNodesRepo:
    def __init__(self, nodes: list[FlowNodeDTO]) -> None:
        self._nodes = nodes

    def list_for_version(self, flow_version_id: str) -> list[FlowNodeDTO]:
        return list(self._nodes)


class _FakeEdgesRepo:
    def __init__(self, edges: list[FlowEdgeDTO]) -> None:
        self._edges = edges

    def list_for_version(self, flow_version_id: str) -> list[FlowEdgeDTO]:
        return list(self._edges)


class _FakeAutomationVersionsReader:
    def get_published_snapshot(self, automation_version_id: int):  # pragma: no cover - sem nos "automation" nestes testes
        return object()


def _flow_version() -> FlowVersionDTO:
    return FlowVersionDTO(
        id="flv_1",
        flow_id="flo_1",
        version="1.0.0",
        status="draft",
        definition={},
        input_schema=None,
        output_schema=None,
        release_notes=None,
        created_by=None,
        created_at=datetime(2026, 7, 28, 12, 0),
    )


def _non_automation_node(key: str, node_type: str) -> FlowNodeDTO:
    return replace(_node(key), node_type=node_type, automation_version_id=None)


def test_validate_flow_version_accepts_new_catalog_node_types() -> None:
    version = _flow_version()
    nodes = [_non_automation_node(key, node_type) for key, node_type in [
        ("if", "if_else"),
        ("sw", "switch"),
        ("mg", "merge"),
        ("sv", "set_variable"),
        ("mf", "map_fields"),
        ("td", "transform_data"),
    ]]
    result = ValidateFlowVersion(_FakeVersionsRepo(version), _FakeNodesRepo(nodes), _FakeEdgesRepo([]), _FakeAutomationVersionsReader()).execute(version.id)

    assert result.valid, result.issues


def test_validate_flow_version_still_accepts_legacy_condition_and_join() -> None:
    """Flows existentes com os tipos antigos ("condition"/"join") continuam validando normalmente."""
    version = _flow_version()
    nodes = [_non_automation_node("c", "condition"), _non_automation_node("j", "join")]
    result = ValidateFlowVersion(_FakeVersionsRepo(version), _FakeNodesRepo(nodes), _FakeEdgesRepo([]), _FakeAutomationVersionsReader()).execute(version.id)

    assert result.valid, result.issues


def test_validate_flow_version_rejects_unknown_node_type() -> None:
    version = _flow_version()
    nodes = [_non_automation_node("x", "totally_unknown")]
    result = ValidateFlowVersion(_FakeVersionsRepo(version), _FakeNodesRepo(nodes), _FakeEdgesRepo([]), _FakeAutomationVersionsReader()).execute(version.id)

    assert not result.valid
    assert any(issue.code == "FLOW_NODE_TYPE_INVALID" for issue in result.issues)

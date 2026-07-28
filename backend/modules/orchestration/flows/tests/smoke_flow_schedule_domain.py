from __future__ import annotations

from datetime import datetime

from modules.orchestration.flows.application.dto import FlowEdgeDTO, FlowNodeDTO
from modules.orchestration.flows.domain import MappingError, resolve_mapping, validate_dag
from modules.orchestration.scheduling.domain import RecurrenceError, RecurrenceInput, build_cron_expression, calculate_next_run


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
        created_at=datetime(2026, 7, 28, 12, 0),
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
        created_at=datetime(2026, 7, 28, 12, 0),
    )


def main() -> None:
    cycle = validate_dag([_node("a"), _node("b")], [_edge("a", "b"), _edge("b", "a")])
    assert not cycle.valid
    assert any(issue.code == "FLOW_CYCLE_DETECTED" for issue in cycle.issues)

    dag = validate_dag([_node("a"), _node("b"), _node("c")], [_edge("a", "b"), _edge("a", "c")])
    assert dag.valid
    assert dag.topological_order[0] == "node_a"
    assert set(dag.topological_order[1:]) == {"node_b", "node_c"}

    mapped = resolve_mapping(
        {
            "company_id": {"source": "flow.input", "path": "$.company_id"},
            "artifact_id": {"source": "node.download.output", "path": "$.artifact_id"},
            "mode": {"value": "complete"},
        },
        {"flow": {"input": {"company_id": 7}}, "nodes": {"download": {"output": {"artifact_id": "art_1"}}}},
    )
    assert mapped == {"company_id": 7, "artifact_id": "art_1", "mode": "complete"}

    try:
        resolve_mapping({"secret": {"source": "flow.input", "path": "$.__token"}}, {"flow": {"input": {"__token": "x"}}})
    except MappingError:
        pass
    else:
        raise AssertionError("private path segment should fail")

    assert build_cron_expression(RecurrenceInput(recurrence_type="weekly", time_of_day="08:30", weekdays=[0, 6])) == "30 8 * * 0,1"
    assert calculate_next_run(
        schedule_type="once",
        cron_expression=None,
        timezone="America/Sao_Paulo",
        after=datetime(2026, 7, 28, 12, 0),
        recurrence_type="once",
        time_of_day="08:00",
        specific_date=datetime(2026, 7, 28).date(),
    ) is None
    try:
        calculate_next_run(schedule_type="interval", cron_expression=None, timezone="UTC", after=datetime(2026, 7, 28, 12, 0), interval_seconds=30)
    except RecurrenceError:
        pass
    else:
        raise AssertionError("short interval should fail")
    assert calculate_next_run(
        schedule_type="interval",
        cron_expression=None,
        timezone="UTC",
        after=datetime(2026, 7, 28, 12, 0),
        interval_seconds=900,
    ).replace(tzinfo=None) == datetime(2026, 7, 28, 12, 15)
    print("flow/schedule domain smoke ok")


if __name__ == "__main__":
    main()

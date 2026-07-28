from __future__ import annotations

from collections import defaultdict, deque

from modules.orchestration.flows.application.dto import FlowEdgeDTO, FlowNodeDTO, FlowValidationIssueDTO, FlowValidationResultDTO


def validate_dag(nodes: list[FlowNodeDTO], edges: list[FlowEdgeDTO]) -> FlowValidationResultDTO:
    issues: list[FlowValidationIssueDTO] = []
    node_ids = {node.id for node in nodes}
    node_keys = [node.key for node in nodes]
    duplicate_keys = sorted({key for key in node_keys if node_keys.count(key) > 1})
    if duplicate_keys:
        issues.append(FlowValidationIssueDTO("FLOW_NODE_KEY_DUPLICATED", "Ha chaves de no duplicadas.", {"keys": duplicate_keys}))

    edge_pairs: set[tuple[str, str, str]] = set()
    adjacency: dict[str, list[str]] = defaultdict(list)
    indegree = {node.id: 0 for node in nodes}
    for edge in edges:
        if edge.source_node_id not in node_ids:
            issues.append(FlowValidationIssueDTO("FLOW_EDGE_SOURCE_MISSING", "A aresta referencia um no de origem inexistente.", {"edge_id": edge.id, "source_node_id": edge.source_node_id}))
        if edge.target_node_id not in node_ids:
            issues.append(FlowValidationIssueDTO("FLOW_EDGE_TARGET_MISSING", "A aresta referencia um no de destino inexistente.", {"edge_id": edge.id, "target_node_id": edge.target_node_id}))
        if edge.source_node_id == edge.target_node_id:
            issues.append(FlowValidationIssueDTO("FLOW_SELF_LOOP", "Aresta nao pode apontar para o proprio no.", {"edge_id": edge.id, "node_id": edge.source_node_id}))
        pair = (edge.source_node_id, edge.target_node_id, edge.edge_type)
        if pair in edge_pairs:
            issues.append(FlowValidationIssueDTO("FLOW_EDGE_DUPLICATED", "Aresta duplicada sem justificativa.", {"edge_id": edge.id}))
        edge_pairs.add(pair)
        if edge.source_node_id in node_ids and edge.target_node_id in node_ids and edge.source_node_id != edge.target_node_id:
            adjacency[edge.source_node_id].append(edge.target_node_id)
            indegree[edge.target_node_id] += 1

    initial_nodes = [node.id for node in nodes if indegree.get(node.id, 0) == 0]
    if nodes and not initial_nodes:
        issues.append(FlowValidationIssueDTO("FLOW_INITIAL_NODE_MISSING", "O DAG nao possui no inicial.", {}))

    order = topological_order(nodes, edges)
    if len(order) != len(nodes):
        issues.append(FlowValidationIssueDTO("FLOW_CYCLE_DETECTED", "O fluxo contem um ciclo.", {"resolved_nodes": order}))

    return FlowValidationResultDTO(valid=not issues, issues=issues, topological_order=order)


def topological_order(nodes: list[FlowNodeDTO], edges: list[FlowEdgeDTO]) -> list[str]:
    node_ids = {node.id for node in nodes}
    adjacency: dict[str, list[str]] = defaultdict(list)
    indegree = {node.id: 0 for node in nodes}
    for edge in edges:
        if edge.source_node_id in node_ids and edge.target_node_id in node_ids and edge.source_node_id != edge.target_node_id:
            adjacency[edge.source_node_id].append(edge.target_node_id)
            indegree[edge.target_node_id] += 1
    ready = deque(sorted([node_id for node_id, degree in indegree.items() if degree == 0]))
    order: list[str] = []
    while ready:
        node_id = ready.popleft()
        order.append(node_id)
        for target in sorted(adjacency.get(node_id, [])):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    return order

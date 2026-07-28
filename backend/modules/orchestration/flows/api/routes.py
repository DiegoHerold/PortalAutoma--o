from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from modules.orchestration.application.dto import ActorDTO
from modules.orchestration.flows.api.schemas import (
    FlowCancelRequest,
    FlowCreateRequest,
    FlowEdgeRequest,
    FlowExecutionCreateRequest,
    FlowNodeRequest,
    FlowUpdateRequest,
    FlowVersionCreateRequest,
    FlowVersionUpdateRequest,
)
from modules.orchestration.flows.application import (
    AddFlowEdge,
    AddFlowNode,
    ArchiveFlow,
    BlockFlowVersion,
    CancelFlowExecution,
    CreateFlow,
    CreateFlowExecution,
    CreateFlowVersion,
    DeprecateFlowVersion,
    GetFlow,
    GetFlowExecution,
    ListFlowExecutions,
    ListFlows,
    PublishFlowVersion,
    RemoveFlowEdge,
    RemoveFlowNode,
    UpdateDraftFlowVersion,
    UpdateFlowMetadata,
    UpdateFlowNode,
    ValidateFlowVersion,
)
from modules.orchestration.flows.application.dto import to_payload
from modules.orchestration.flows.infrastructure.adapters import build_flow_adapters
from modules.telemetry.application.dto import to_payload as telemetry_payload
from modules.telemetry.application.use_cases import GetExecutionTimeline
from modules.telemetry.infrastructure.adapters import build_telemetry_adapters

router = APIRouter()


@router.get("/flows")
def list_flows(limit: int = 100, offset: int = 0, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return [to_payload(item) for item in ListFlows(build_flow_adapters(db).flows).execute(limit=limit, offset=offset)]


@router.post("/flows", status_code=status.HTTP_201_CREATED)
def create_flow(payload: FlowCreateRequest, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    adapters = build_flow_adapters(db)
    try:
        return to_payload(CreateFlow(adapters.flows, adapters.outbox, adapters.audit, adapters.transaction).execute(key=payload.key, name=payload.name, description=payload.description, category_id=payload.category_id, tags=payload.tags, actor=_actor(user, request)))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/flows/{flow_id}")
def get_flow(flow_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    try:
        return to_payload(GetFlow(build_flow_adapters(db).flows).execute(flow_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/flows/{flow_id}")
def update_flow(flow_id: str, payload: FlowUpdateRequest, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    adapters = build_flow_adapters(db)
    try:
        return to_payload(UpdateFlowMetadata(adapters.flows, adapters.outbox, adapters.audit, adapters.transaction).execute(flow_id, actor=_actor(user, request), payload=payload.model_dump(exclude_unset=True)))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/flows/{flow_id}/archive")
def archive_flow(flow_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    adapters = build_flow_adapters(db)
    try:
        return to_payload(ArchiveFlow(adapters.flows, adapters.outbox, adapters.audit, adapters.transaction).execute(flow_id, actor=_actor(user, request)))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/flows/{flow_id}/versions")
def list_flow_versions(flow_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    adapters = build_flow_adapters(db)
    return [to_payload(item) for item in adapters.versions.list_for_flow(flow_id)]


@router.post("/flows/{flow_id}/versions", status_code=status.HTTP_201_CREATED)
def create_flow_version(flow_id: str, payload: FlowVersionCreateRequest, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    adapters = build_flow_adapters(db)
    try:
        return to_payload(CreateFlowVersion(adapters.flows, adapters.versions, adapters.outbox, adapters.audit, adapters.transaction).execute(flow_id, version=payload.version, definition=payload.definition, input_schema=payload.input_schema, output_schema=payload.output_schema, release_notes=payload.release_notes, actor=_actor(user, request)))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/flow-versions/{flow_version_id}")
def get_flow_version(flow_version_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    adapters = build_flow_adapters(db)
    version = adapters.versions.get(flow_version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="FlowVersion not found.")
    return to_payload(version)


@router.patch("/flow-versions/{flow_version_id}")
def update_flow_version(flow_version_id: str, payload: FlowVersionUpdateRequest, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    adapters = build_flow_adapters(db)
    try:
        return to_payload(UpdateDraftFlowVersion(adapters.versions, adapters.transaction).execute(flow_version_id, payload.model_dump(exclude_unset=True)))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/flow-versions/{flow_version_id}/validate")
def validate_flow_version(flow_version_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    adapters = build_flow_adapters(db)
    try:
        return to_payload(ValidateFlowVersion(adapters.versions, adapters.nodes, adapters.edges, adapters.automation_versions).execute(flow_version_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/flow-versions/{flow_version_id}/publish")
def publish_flow_version(flow_version_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    adapters = build_flow_adapters(db)
    try:
        return to_payload(PublishFlowVersion(adapters.flows, adapters.versions, adapters.nodes, adapters.edges, adapters.automation_versions, adapters.outbox, adapters.audit, adapters.transaction).execute(flow_version_id, actor=_actor(user, request)))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/flow-versions/{flow_version_id}/deprecate")
def deprecate_flow_version(flow_version_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    adapters = build_flow_adapters(db)
    return to_payload(DeprecateFlowVersion(adapters.versions, adapters.transaction).execute(flow_version_id))


@router.post("/flow-versions/{flow_version_id}/block")
def block_flow_version(flow_version_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    adapters = build_flow_adapters(db)
    return to_payload(BlockFlowVersion(adapters.versions, adapters.transaction).execute(flow_version_id))


@router.post("/flow-versions/{flow_version_id}/nodes", status_code=status.HTTP_201_CREATED)
def add_flow_node(flow_version_id: str, payload: FlowNodeRequest, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    adapters = build_flow_adapters(db)
    try:
        return to_payload(AddFlowNode(adapters.versions, adapters.nodes, adapters.transaction).execute(flow_version_id, payload.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/flow-nodes/{node_id}")
def update_flow_node(node_id: str, payload: FlowNodeRequest, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    adapters = build_flow_adapters(db)
    try:
        return to_payload(UpdateFlowNode(adapters.versions, adapters.nodes, adapters.transaction).execute(node_id, payload.model_dump(exclude_unset=True)))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/flow-nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def remove_flow_node(node_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)) -> None:
    adapters = build_flow_adapters(db)
    RemoveFlowNode(adapters.versions, adapters.nodes, adapters.edges, adapters.transaction).execute(node_id)


@router.post("/flow-versions/{flow_version_id}/edges", status_code=status.HTTP_201_CREATED)
def add_flow_edge(flow_version_id: str, payload: FlowEdgeRequest, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    adapters = build_flow_adapters(db)
    try:
        return to_payload(AddFlowEdge(adapters.versions, adapters.nodes, adapters.edges, adapters.transaction).execute(flow_version_id, payload.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/flow-edges/{edge_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def remove_flow_edge(edge_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)) -> None:
    adapters = build_flow_adapters(db)
    RemoveFlowEdge(adapters.versions, adapters.edges, adapters.transaction).execute(edge_id)


@router.post("/flow-executions", status_code=status.HTTP_201_CREATED)
def create_flow_execution(payload: FlowExecutionCreateRequest, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    adapters = build_flow_adapters(db)
    try:
        return CreateFlowExecution(adapters.flows, adapters.versions, adapters.nodes, adapters.edges, adapters.flow_executions, adapters.node_executions, adapters.executions, adapters.tasks, adapters.automation_versions, adapters.outbox, adapters.audit, adapters.transaction).execute(flow_version_id=payload.flow_version_id, actor=_actor(user, request), input=payload.input, origin=payload.origin).to_payload()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/flow-executions")
def list_flow_executions(limit: int = 100, offset: int = 0, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    adapters = build_flow_adapters(db)
    return [to_payload(item) for item in ListFlowExecutions(adapters.flow_executions).execute(limit=limit, offset=offset)]


@router.get("/flow-executions/{flow_execution_id}")
def get_flow_execution(flow_execution_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    adapters = build_flow_adapters(db)
    try:
        return GetFlowExecution(adapters.versions, adapters.nodes, adapters.edges, adapters.flow_executions, adapters.node_executions, adapters.executions).execute(flow_execution_id).to_payload()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/flow-executions/{flow_execution_id}/timeline")
def get_flow_execution_timeline(
    flow_execution_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    limit: int = Query(default=300, ge=1, le=1000),
    cursor: str | None = None,
):
    adapters = build_flow_adapters(db)
    try:
        flow_execution = adapters.flow_executions.get(flow_execution_id)
        if flow_execution is None:
            raise ValueError("FlowExecution not found.")
        telemetry = build_telemetry_adapters(db)
        return telemetry_payload(GetExecutionTimeline(telemetry.events).execute(flow_execution.execution_id, limit=limit, cursor=cursor))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/flow-executions/{flow_execution_id}/stream")
def stream_flow_execution(flow_execution_id: str, token: str = Query(...), db: Session = Depends(get_db)) -> RedirectResponse:
    adapters = build_flow_adapters(db)
    flow_execution = adapters.flow_executions.get(flow_execution_id)
    if flow_execution is None:
        raise HTTPException(status_code=404, detail="FlowExecution not found.")
    return RedirectResponse(
        url=f"/api/v1/executions/{flow_execution.execution_id}/stream?{urlencode({'token': token})}",
        status_code=307,
    )


@router.post("/flow-executions/{flow_execution_id}/cancel")
def cancel_flow_execution(flow_execution_id: str, payload: FlowCancelRequest, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    adapters = build_flow_adapters(db)
    try:
        return to_payload(CancelFlowExecution(adapters.flow_executions, adapters.node_executions, adapters.executions, adapters.outbox, adapters.transaction).execute(flow_execution_id, reason=payload.reason))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _actor(user: User, request: Request) -> ActorDTO:
    return ActorDTO(actor_type="user", actor_id=str(user.id), actor_email=user.email, ip=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))

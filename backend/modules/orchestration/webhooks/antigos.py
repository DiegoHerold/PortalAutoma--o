"""Rotas antigas de gatilhos e webhooks: desligadas em 13/11/2026 (respondem 410).

- ``/triggers/...`` (cadastro antigo, inclusive os gatilhos em cadeia, que nunca tiveram quem os
  disparasse) e ``/triggers/invoke/...``;
- ``POST /webhooks/trigger/...`` (aceitava o segredo na URL ou no corpo).

Os webhooks de antes foram migrados para ``webhooks`` desligados e sem token (migration
``c5d6e7f8a9b1``). O webhook do GitHub (``/webhooks/github``) é outra coisa e continua.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(include_in_schema=False)

MENSAGEM = ("Os webhooks mudaram: cadastre em Operação > Webhooks e chame POST /api/v1/webhooks/{id} com "
            "Authorization: Bearer <token>.")


@router.api_route("/triggers", methods=["GET", "POST"])
@router.api_route("/triggers/{caminho:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@router.api_route("/webhooks/trigger/{caminho:path}", methods=["POST"])
def desligada(caminho: str | None = None) -> JSONResponse:
    return JSONResponse(status_code=410, content={"erro": MENSAGEM})

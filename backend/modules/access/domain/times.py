"""Times: membros e permissões por categoria (ver, executar, editar e publicar).

Desde 12/11/2026 é **só no time** que se dá acesso às automações de uma categoria: as permissões
por categoria que ficavam direto em cada pessoa passaram para times (migration ``b2c3d4e5f6a8``).
"Editar" no time são as três de antes (criar, editar e apagar o cadastro); "publicar" é a de aprovar.

Quem é membro de um time **ativo** ganha as permissões dele, somadas às suas próprias; sai do
time, perde. As concessões por automação de um time ficam em ``concessao.py`` (mesma regra).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


class TimeInvalido(ValueError):
    pass


@dataclass(frozen=True)
class PermissaoDoTime:
    """Mesmo formato da permissão por categoria do usuário: as checagens leem as duas igual."""

    category_id: int
    can_view: bool = False
    can_execute: bool = False
    can_create: bool = False
    can_edit: bool = False
    can_delete: bool = False
    can_approve: bool = False
    origem: str = "time"

    @property
    def alguma(self) -> bool:
        return any((self.can_view, self.can_execute, self.can_create, self.can_edit, self.can_delete, self.can_approve))


def validar_categorias(brutas: Any) -> list[PermissaoDoTime]:
    """``[{"category_id": 3, "can_view": true, "can_execute": false, "can_edit": false, "can_approve": false}]``.

    ``can_edit`` vale pelas três de cadastro (criar, editar, apagar), a não ser que ``can_create`` ou
    ``can_delete`` venham explícitos. Quem executa, edita ou publica também vê. Linha sem nenhuma
    permissão sai (é o mesmo que tirar a categoria do time)."""
    if not isinstance(brutas, list):
        raise TimeInvalido("categorias: envie uma lista")
    saida: dict[int, PermissaoDoTime] = {}
    for posicao, bruta in enumerate(brutas):
        if not isinstance(bruta, dict):
            raise TimeInvalido(f"categorias[{posicao}]: envie um objeto")
        categoria = bruta.get("category_id")
        if isinstance(categoria, bool) or not isinstance(categoria, int) or categoria <= 0:
            raise TimeInvalido(f"categorias[{posicao}].category_id: número da categoria")
        if categoria in saida:
            raise TimeInvalido(f"categorias[{posicao}]: categoria repetida")
        marca = {k: bruta.get(k) is True for k in ("can_view", "can_execute", "can_edit", "can_approve")}
        criar = bruta["can_create"] is True if "can_create" in bruta else marca["can_edit"]
        apagar = bruta["can_delete"] is True if "can_delete" in bruta else marca["can_edit"]
        # Quem executa, edita ou publica vê: sem ver, a automação ficaria invisível.
        ver = marca["can_view"] or marca["can_execute"] or marca["can_edit"] or marca["can_approve"] or criar or apagar
        saida[categoria] = PermissaoDoTime(categoria, ver, marca["can_execute"], criar, marca["can_edit"], apagar,
                                           marca["can_approve"])
    return [p for p in saida.values() if p.alguma]


def validar_membros(brutos: Any, o_que: str = "usuários") -> list[int]:
    if not isinstance(brutos, list) or any(isinstance(u, bool) or not isinstance(u, int) or u <= 0 for u in brutos):
        raise TimeInvalido(f"informe os {o_que} pelo número")
    return sorted(set(brutos))


def efetivas(proprias: Iterable[Any], dos_times: Iterable[Any]) -> list[Any]:
    """Permissões por categoria de uma pessoa: as dela e, depois, as dos times dela. As checagens
    perguntam "alguma permite?", então somar basta, e as permissões próprias que só a pessoa tem
    (criar, editar...) continuam intactas."""
    return [*proprias, *dos_times]

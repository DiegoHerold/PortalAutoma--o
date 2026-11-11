"""Times: membros e permissões por categoria (ver e executar).

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
    origem: str = "time"


def validar_categorias(brutas: Any) -> list[PermissaoDoTime]:
    """``[{"category_id": 3, "can_view": true, "can_execute": false}, ...]``. Linha sem nenhuma
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
        ver, executar = bruta.get("can_view") is True, bruta.get("can_execute") is True
        if executar and not ver:
            ver = True  # quem executa vê: executar sem ver deixaria a automação invisível
        saida[categoria] = PermissaoDoTime(categoria, ver, executar)
    return [p for p in saida.values() if p.can_view or p.can_execute]


def validar_membros(brutos: Any, o_que: str = "usuários") -> list[int]:
    if not isinstance(brutos, list) or any(isinstance(u, bool) or not isinstance(u, int) or u <= 0 for u in brutos):
        raise TimeInvalido(f"informe os {o_que} pelo número")
    return sorted(set(brutos))


def efetivas(proprias: Iterable[Any], dos_times: Iterable[Any]) -> list[Any]:
    """Permissões por categoria de uma pessoa: as dela e, depois, as dos times dela. As checagens
    perguntam "alguma permite?", então somar basta, e as permissões próprias que só a pessoa tem
    (criar, editar...) continuam intactas."""
    return [*proprias, *dos_times]

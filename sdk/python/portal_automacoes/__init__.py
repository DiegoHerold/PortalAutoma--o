"""SDK do Portal de Automações: eventos de etapa, item, progresso, log, passo e atenção,
iguais no modo agente e no modo direto (contracts/automation-events/v1)."""

from .automacao import VERSAO_SDK, Automacao, Etapa, ParadaSolicitada
from .eventos import EventoInvalido
from .imagens import ImagemRecusada
from .trabalhador import job_atual

__all__ = ["VERSAO_SDK", "Automacao", "Etapa", "EventoInvalido", "ImagemRecusada", "ParadaSolicitada", "job_atual"]

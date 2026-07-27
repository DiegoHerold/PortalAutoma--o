from __future__ import annotations

from dataclasses import dataclass

from gateway.agent_gateway.errors import ProtocolNegotiationFailed


SUPPORTED_PROTOCOL_VERSIONS = ("1.0",)


@dataclass(frozen=True)
class ProtocolNegotiationResult:
    selected_protocol_version: str
    supported_protocol_versions: tuple[str, ...]


def negotiate_protocol(agent_supported_versions: list[str] | tuple[str, ...]) -> ProtocolNegotiationResult:
    supported = tuple(str(version) for version in agent_supported_versions)
    for version in reversed(SUPPORTED_PROTOCOL_VERSIONS):
        if version in supported:
            return ProtocolNegotiationResult(version, SUPPORTED_PROTOCOL_VERSIONS)
    raise ProtocolNegotiationFailed("No compatible protocol version was found.")

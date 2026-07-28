from __future__ import annotations

from dataclasses import dataclass

from infrastructure.config import get_settings


@dataclass(frozen=True)
class GatewayLimits:
    max_message_bytes: int = 64 * 1024
    max_messages_per_second: int = 20
    max_heartbeat_payload_bytes: int = 24 * 1024
    max_capabilities_per_message: int = 200
    max_attribute_depth: int = 6
    max_pending_commands_per_agent: int = 50
    handshake_timeout_seconds: int = 15
    idle_timeout_seconds: int = 120


def load_gateway_limits() -> GatewayLimits:
    settings = get_settings()
    return GatewayLimits(
        max_message_bytes=settings.agent_gateway_max_message_bytes,
        max_messages_per_second=settings.agent_gateway_max_messages_per_second,
        max_heartbeat_payload_bytes=settings.agent_gateway_max_heartbeat_payload_bytes,
        max_capabilities_per_message=settings.agent_gateway_max_capabilities_per_message,
        max_attribute_depth=settings.agent_gateway_max_attribute_depth,
        max_pending_commands_per_agent=settings.agent_gateway_max_pending_commands_per_agent,
        handshake_timeout_seconds=settings.agent_gateway_handshake_timeout_seconds,
        idle_timeout_seconds=settings.agent_gateway_idle_timeout_seconds,
    )

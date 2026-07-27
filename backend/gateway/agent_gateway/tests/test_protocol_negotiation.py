from __future__ import annotations

from gateway.agent_gateway.errors import ProtocolNegotiationFailed
from gateway.agent_gateway.protocol_negotiation import negotiate_protocol


def test_protocol_negotiation_selects_supported_version() -> None:
    result = negotiate_protocol(["0.9", "1.0"])

    assert result.selected_protocol_version == "1.0"


def test_protocol_negotiation_rejects_incompatible_agent() -> None:
    try:
        negotiate_protocol(["0.8"])
    except ProtocolNegotiationFailed as exc:
        assert "compatible" in str(exc)
    else:
        raise AssertionError("Expected protocol negotiation to fail.")

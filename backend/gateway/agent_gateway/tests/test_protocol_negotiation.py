from __future__ import annotations

from gateway.agent_gateway.endpoint import _portal_envelope
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


def test_portal_error_envelope_is_versioned_and_addressed() -> None:
    envelope = _portal_envelope(
        "portal.error",
        {"code": "MISSING_MESSAGE_ID", "message": "message_id ausente."},
        "1.0",
        agent_id="agt_1",
        agent_instance_id="agi_1",
        correlation_id="msg_original",
    )

    assert envelope["protocol_version"] == "1.0"
    assert envelope["message_id"].startswith("msg_")
    assert envelope["message_type"] == "portal.error"
    assert envelope["sent_at"].endswith("Z")
    assert envelope["agent_id"] == "agt_1"
    assert envelope["agent_instance_id"] == "agi_1"
    assert envelope["correlation_id"] == "msg_original"
    assert envelope["payload"]["code"] == "MISSING_MESSAGE_ID"

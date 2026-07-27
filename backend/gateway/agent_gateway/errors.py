from __future__ import annotations


class GatewayError(ValueError):
    code = "GATEWAY_ERROR"


class AuthenticationFailed(GatewayError):
    code = "AUTHENTICATION_FAILED"


class ProtocolNegotiationFailed(GatewayError):
    code = "PROTOCOL_NEGOTIATION_FAILED"


class EnvelopeValidationFailed(GatewayError):
    code = "ENVELOPE_INVALID"


class MessageTooLarge(GatewayError):
    code = "MESSAGE_TOO_LARGE"


class MessageTypeUnsupported(GatewayError):
    code = "MESSAGE_TYPE_NOT_SUPPORTED"

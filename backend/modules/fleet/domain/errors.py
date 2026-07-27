from __future__ import annotations


class FleetError(ValueError):
    """Base exception for Fleet application and domain rules."""


class AgentNotFoundError(FleetError):
    pass


class AgentDisabledError(FleetError):
    pass


class AgentCredentialError(FleetError):
    pass


class AgentRegistrationError(FleetError):
    pass


class DuplicateAgentRegistrationError(AgentRegistrationError):
    pass


class InvalidAgentStateTransition(FleetError):
    pass


class InvalidAgentInstanceError(FleetError):
    pass


class UnsupportedProtocolError(FleetError):
    pass


class MessageValidationError(FleetError):
    pass


class MessageTypeNotSupportedError(FleetError):
    pass

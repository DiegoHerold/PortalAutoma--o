from __future__ import annotations


class DispatchError(Exception):
    """Base error for dispatch rules."""


class AgentSelectionError(DispatchError):
    """Raised when no compatible Agent can be selected."""


class ExecutionOfferNotFound(DispatchError):
    """Raised when an offer cannot be found."""


class InvalidOfferTransition(DispatchError):
    """Raised when an offer transition is not allowed."""


class OfferSecurityError(DispatchError):
    """Raised when an Agent or AgentInstance attempts to handle another offer."""


class OfferExpired(DispatchError):
    """Raised when an offer response arrives after expiration."""

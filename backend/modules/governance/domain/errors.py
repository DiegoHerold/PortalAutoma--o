from __future__ import annotations


class GovernanceError(Exception):
    """Base error for Governance domain failures."""


class GovernanceResourceNotFound(GovernanceError):
    """Requested governance resource was not found."""


class GovernanceConflict(GovernanceError):
    """Requested governance operation conflicts with existing state."""


class SecretAccessDenied(GovernanceError):
    """A secret exists but the caller is not allowed to access it."""


class InvalidGovernanceState(GovernanceError):
    """Requested state transition is not allowed."""


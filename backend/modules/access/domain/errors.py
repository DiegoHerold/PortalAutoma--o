from __future__ import annotations


class AccessError(Exception):
    code = "ACCESS_ERROR"


class AuthenticationFailed(AccessError):
    code = "AUTHENTICATION_FAILED"


class AuthorizationDenied(AccessError):
    code = "PERMISSION_DENIED"


class AccessResourceNotFound(AccessError):
    code = "NOT_FOUND"


class AccessConflict(AccessError):
    code = "CONFLICT"


class InvalidAccessState(AccessError):
    code = "STATE_TRANSITION_NOT_ALLOWED"


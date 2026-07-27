from __future__ import annotations


class CatalogError(ValueError):
    """Base class for Catalog domain and application errors."""


class DuplicateAutomationKeyError(CatalogError):
    pass


class DuplicateAutomationVersionError(CatalogError):
    pass


class InvalidCatalogStateTransition(CatalogError):
    pass


class ImmutablePublishedVersionError(CatalogError):
    pass


class CatalogValidationError(CatalogError):
    pass


class RuntimeCompatibilityError(CatalogError):
    pass


class PackageValidationError(CatalogError):
    pass

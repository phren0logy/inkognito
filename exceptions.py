"""Custom exceptions for Inkognito."""


class InkognitoError(Exception):
    """Base exception for Inkognito."""
    pass


class ExtractionError(InkognitoError):
    """Document extraction failed."""
    pass


class AnonymizationError(InkognitoError):
    """PII anonymization failed."""
    pass


class VaultError(InkognitoError):
    """Vault operation failed."""
    pass


class SegmentationError(InkognitoError):
    """Document segmentation failed."""
    pass
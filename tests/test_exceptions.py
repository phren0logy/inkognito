"""Tests for custom exception classes."""

import pytest
from exceptions import (
    InkognitoError, ExtractionError, AnonymizationError,
    VaultError, SegmentationError
)


class TestExceptionHierarchy:
    """Test the exception class hierarchy."""
    
    def test_base_exception(self):
        """Test the base InkognitoError."""
        error = InkognitoError("Base error message")
        assert str(error) == "Base error message"
        assert isinstance(error, Exception)
    
    def test_extraction_error(self):
        """Test ExtractionError inherits from InkognitoError."""
        error = ExtractionError("Failed to extract PDF")
        assert str(error) == "Failed to extract PDF"
        assert isinstance(error, InkognitoError)
        assert isinstance(error, Exception)
    
    def test_anonymization_error(self):
        """Test AnonymizationError inherits from InkognitoError."""
        error = AnonymizationError("PII detection failed")
        assert str(error) == "PII detection failed"
        assert isinstance(error, InkognitoError)
        assert isinstance(error, Exception)
    
    def test_vault_error(self):
        """Test VaultError inherits from InkognitoError."""
        error = VaultError("Vault file corrupted")
        assert str(error) == "Vault file corrupted"
        assert isinstance(error, InkognitoError)
        assert isinstance(error, Exception)
    
    def test_segmentation_error(self):
        """Test SegmentationError inherits from InkognitoError."""
        error = SegmentationError("Document too large")
        assert str(error) == "Document too large"
        assert isinstance(error, InkognitoError)
        assert isinstance(error, Exception)
    
    def test_exception_with_cause(self):
        """Test exceptions can chain causes."""
        try:
            raise ValueError("Original error")
        except ValueError as e:
            try:
                raise ExtractionError("Extraction failed") from e
            except ExtractionError as extraction_error:
                assert str(extraction_error) == "Extraction failed"
                assert extraction_error.__cause__ is not None
                assert str(extraction_error.__cause__) == "Original error"
    
    def test_exception_inheritance_check(self):
        """Test that all custom exceptions inherit from InkognitoError."""
        exceptions = [
            ExtractionError("test"),
            AnonymizationError("test"),
            VaultError("test"),
            SegmentationError("test")
        ]
        
        for exc in exceptions:
            assert isinstance(exc, InkognitoError)
    
    def test_catching_base_exception(self):
        """Test catching all custom exceptions via base class."""
        exceptions_to_test = [
            (ExtractionError, "extraction failed"),
            (AnonymizationError, "anonymization failed"),
            (VaultError, "vault failed"),
            (SegmentationError, "segmentation failed")
        ]
        
        for exception_class, message in exceptions_to_test:
            try:
                raise exception_class(message)
            except InkognitoError as e:
                # Should catch all derived exceptions
                assert str(e) == message
            except Exception:
                pytest.fail(f"{exception_class.__name__} was not caught by InkognitoError")
    
    def test_exception_repr(self):
        """Test exception representation."""
        error = ExtractionError("Test message")
        assert "ExtractionError" in repr(error)
        assert "Test message" in repr(error)
    
    def test_empty_message(self):
        """Test exceptions with empty messages."""
        error = InkognitoError("")
        assert str(error) == ""
        
        error = VaultError()
        assert str(error) == ""
    
    def test_exception_with_special_characters(self):
        """Test exception messages with special characters."""
        special_messages = [
            "Error with newline\ncharacter",
            "Error with tab\tcharacter",
            "Error with quotes: 'single' and \"double\"",
            "Error with unicode: 你好世界 🌍",
            "Error with backslash: C:\\path\\to\\file"
        ]
        
        for message in special_messages:
            error = InkognitoError(message)
            assert str(error) == message
"""Tests for PII anonymization functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import random

from anonymizer import PIIAnonymizer, LLM_GUARD_AVAILABLE


class TestPIIAnonymizer:
    """Test the PIIAnonymizer class."""
    
    def test_init(self):
        """Test PIIAnonymizer initialization."""
        anonymizer = PIIAnonymizer()
        assert anonymizer.faker is not None
        assert anonymizer.date_shift_days == 365
    
    def test_default_entity_types(self):
        """Test that all expected entity types are included."""
        anonymizer = PIIAnonymizer()
        expected_types = [
            "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", 
            "US_SSN", "PASSPORT", "US_DRIVER_LICENSE",
            "IP_ADDRESS", "PERSON", "LOCATION",
            "ORGANIZATION", "DATE_TIME", "URL",
            "US_BANK_NUMBER", "CRYPTO", "MEDICAL_LICENSE"
        ]
        assert anonymizer.DEFAULT_ENTITY_TYPES == expected_types
    
    def test_create_scanner(self):
        """Test scanner creation with proper configuration."""
        anonymizer = PIIAnonymizer()
        
        with patch('anonymizer.Anonymize') as mock_anonymize:
            with patch('anonymizer.Vault') as mock_vault:
                scanner, vault = anonymizer._create_scanner()
                
                mock_vault.assert_called_once()
                mock_anonymize.assert_called_once()
                
                call_args = mock_anonymize.call_args[1]
                assert call_args['entity_types'] == anonymizer.DEFAULT_ENTITY_TYPES
                assert call_args['threshold'] == 0.5
                assert call_args['use_faker'] is False
    
    def test_generate_faker_value_email(self, mock_faker):
        """Test faker value generation for email addresses."""
        anonymizer = PIIAnonymizer()
        anonymizer.faker = mock_faker
        
        result = anonymizer._generate_faker_value("EMAIL_ADDRESS", "test@example.com")
        assert result == "robert.johnson@example.com"
        mock_faker.email.assert_called_once()
    
    def test_generate_faker_value_phone(self, mock_faker):
        """Test faker value generation for phone numbers."""
        anonymizer = PIIAnonymizer()
        anonymizer.faker = mock_faker
        
        result = anonymizer._generate_faker_value("PHONE_NUMBER", "+1-555-1234")
        assert result == "+1-555-987-6543"
        mock_faker.phone_number.assert_called_once()
    
    def test_generate_faker_value_person(self, mock_faker):
        """Test faker value generation for person names."""
        anonymizer = PIIAnonymizer()
        anonymizer.faker = mock_faker
        
        result = anonymizer._generate_faker_value("PERSON", "John Doe")
        assert result == "Robert Johnson"
        mock_faker.name.assert_called_once()
    
    def test_generate_faker_value_ssn(self, mock_faker):
        """Test faker value generation for SSN."""
        anonymizer = PIIAnonymizer()
        anonymizer.faker = mock_faker
        
        result = anonymizer._generate_faker_value("US_SSN", "123-45-6789")
        assert result == "987-65-4321"
        mock_faker.ssn.assert_called_once()
    
    def test_generate_faker_value_passport(self, mock_faker):
        """Test faker value generation for passport numbers."""
        anonymizer = PIIAnonymizer()
        anonymizer.faker = mock_faker
        
        result = anonymizer._generate_faker_value("PASSPORT", "US12345678")
        assert result == "XX9999999"
        mock_faker.bothify.assert_called_with(text='??#######')
    
    def test_generate_faker_value_drivers_license(self, mock_faker):
        """Test faker value generation for driver's license."""
        anonymizer = PIIAnonymizer()
        anonymizer.faker = mock_faker
        
        result = anonymizer._generate_faker_value("US_DRIVER_LICENSE", "DL-12345678")
        assert result == "DL-99999999"
        mock_faker.bothify.assert_called_with(text='DL-########')
    
    def test_generate_faker_value_crypto(self, mock_faker):
        """Test faker value generation for crypto addresses."""
        anonymizer = PIIAnonymizer()
        anonymizer.faker = mock_faker
        
        result = anonymizer._generate_faker_value("CRYPTO", "0x123...")
        assert result.startswith("0x")
        assert len(result) == 42  # Ethereum address length
    
    def test_generate_faker_value_medical_license(self, mock_faker):
        """Test faker value generation for medical licenses."""
        anonymizer = PIIAnonymizer()
        anonymizer.faker = mock_faker
        
        result = anonymizer._generate_faker_value("MEDICAL_LICENSE", "MD-1234567")
        assert result == "MD-9999999"
        mock_faker.bothify.assert_called_with(text='MD-#######')
    
    def test_generate_faker_value_unknown_type(self):
        """Test faker value generation for unknown entity types."""
        anonymizer = PIIAnonymizer()
        
        result = anonymizer._generate_faker_value("UNKNOWN_TYPE", "some value")
        assert result == "REDACTED_UNKNOWN_TYPE"
    
    def test_extract_entity_type(self):
        """Test extraction of entity type from placeholder."""
        anonymizer = PIIAnonymizer()
        
        # Test standard format
        assert anonymizer._extract_entity_type("[REDACTED_PERSON_1]") == "PERSON"
        assert anonymizer._extract_entity_type("[REDACTED_EMAIL_ADDRESS_5]") == "EMAIL_ADDRESS"
        assert anonymizer._extract_entity_type("[REDACTED_PHONE_NUMBER_10]") == "PHONE_NUMBER"
        
        # Test multi-word entity types
        assert anonymizer._extract_entity_type("[REDACTED_US_SSN_2]") == "US_SSN"
        assert anonymizer._extract_entity_type("[REDACTED_US_DRIVER_LICENSE_3]") == "US_DRIVER_LICENSE"
        
        # Test edge cases
        assert anonymizer._extract_entity_type("[REDACTED_UNKNOWN]") == "UNKNOWN"  # No number
        assert anonymizer._extract_entity_type("NOT_A_PLACEHOLDER") == "UNKNOWN"
        assert anonymizer._extract_entity_type("[DIFFERENT_FORMAT]") == "UNKNOWN"
        assert anonymizer._extract_entity_type("") == "UNKNOWN"
    
    def test_generate_date_offset_default(self):
        """Test date offset generation with default range."""
        anonymizer = PIIAnonymizer()
        
        # Mock random.randint to verify the range
        with patch('random.randint') as mock_randint:
            mock_randint.return_value = 180
            offset = anonymizer.generate_date_offset()
            
            mock_randint.assert_called_once_with(-365, 365)
            assert offset == 180
    
    def test_generate_date_offset_custom(self):
        """Test date offset generation with custom range."""
        anonymizer = PIIAnonymizer()
        
        with patch('random.randint') as mock_randint:
            mock_randint.return_value = 90
            offset = anonymizer.generate_date_offset(max_days=180)
            
            mock_randint.assert_called_once_with(-180, 180)
            assert offset == 90
    
    def test_anonymize_with_vault_no_pii(self, mock_llm_guard):
        """Test anonymization when no PII is detected."""
        anonymizer = PIIAnonymizer()
        scanner, _ = mock_llm_guard
        
        # Create a mock vault
        mock_vault = Mock()
        mock_vault.get.return_value = []  # No entities found
        
        # Mock scan to return text without PII
        scanner.scan.return_value = ("No PII here", True, 0.0)
        
        with patch('anonymizer.PIIAnonymizer._create_scanner', return_value=(scanner, mock_vault)):
            text, stats, mappings = anonymizer.anonymize_with_vault("No PII here")
        
        assert text == "No PII here"
        assert stats == {}
        assert mappings == {}
    
    def test_anonymize_with_vault_new_mappings(self, mock_llm_guard, mock_faker):
        """Test anonymization creating new mappings."""
        anonymizer = PIIAnonymizer()
        anonymizer.faker = mock_faker
        scanner, _ = mock_llm_guard
        
        # Create a mock vault that will be used
        mock_vault = Mock()
        mock_vault.get.return_value = [
            ("[REDACTED_PERSON_1]", "John Smith"),
            ("[REDACTED_EMAIL_ADDRESS_1]", "john.smith@example.com")
        ]
        
        # Update the mock to handle this specific case
        scanner.scan.return_value = (
            "Contact [REDACTED_PERSON_1] at [REDACTED_EMAIL_ADDRESS_1]",
            False,
            0.95
        )
        
        with patch('anonymizer.PIIAnonymizer._create_scanner', return_value=(scanner, mock_vault)):
            text, stats, mappings = anonymizer.anonymize_with_vault(
                "Contact John Smith at john.smith@example.com"
            )
        
        # Verify statistics
        assert stats["PERSON"] == 1
        assert stats["EMAIL_ADDRESS"] == 1
        
        # Verify new mappings created
        assert len(mappings) == 2
        assert mappings["John Smith"] == "Robert Johnson"
        assert mappings["john.smith@example.com"] == "robert.johnson@example.com"
        
        # Verify text was properly anonymized
        assert "Robert Johnson" in text
        assert "robert.johnson@example.com" in text
    
    def test_anonymize_with_vault_existing_mappings(self, mock_llm_guard, mock_faker):
        """Test anonymization with existing mappings for consistency."""
        anonymizer = PIIAnonymizer()
        anonymizer.faker = mock_faker
        scanner, _ = mock_llm_guard
        
        # Create a mock vault
        mock_vault = Mock()
        mock_vault.get.return_value = [
            ("[REDACTED_PERSON_1]", "John Smith"),
            ("[REDACTED_EMAIL_ADDRESS_1]", "john.smith@example.com")
        ]
        
        # Update the mock for this test
        scanner.scan.return_value = (
            "Contact [REDACTED_PERSON_1] at [REDACTED_EMAIL_ADDRESS_1]",
            False,
            0.95
        )
        
        # Existing mappings
        existing = {
            "John Smith": "Alice Brown",
            "john.smith@example.com": "alice.brown@example.com"
        }
        
        with patch('anonymizer.PIIAnonymizer._create_scanner', return_value=(scanner, mock_vault)):
            text, stats, new_mappings = anonymizer.anonymize_with_vault(
                "Contact John Smith at john.smith@example.com",
                existing_mappings=existing
            )
        
        # Should use existing mappings, not create new ones
        assert "Alice Brown" in text
        assert "alice.brown@example.com" in text
        assert "Robert Johnson" not in text
        assert len(new_mappings) == 0  # No new mappings since we used existing ones
    
    def test_anonymize_with_vault_multiple_entity_types(
        self, mock_llm_guard, mock_faker
    ):
        """Test anonymization with multiple entity types."""
        anonymizer = PIIAnonymizer()
        anonymizer.faker = mock_faker
        scanner, _ = mock_llm_guard
        
        # Create a mock vault
        mock_vault = Mock()
        mock_vault.get.return_value = [
            ("[REDACTED_PERSON_1]", "John Smith"),
            ("[REDACTED_EMAIL_ADDRESS_1]", "john@example.com"),
            ("[REDACTED_PHONE_NUMBER_1]", "+1-555-1234"),
            ("[REDACTED_US_SSN_1]", "123-45-6789"),
            ("[REDACTED_ORGANIZATION_1]", "Acme Corp"),
            ("[REDACTED_LOCATION_1]", "New York"),
            ("[REDACTED_IP_ADDRESS_1]", "192.168.1.1"),
            ("[REDACTED_CREDIT_CARD_1]", "4111111111111111")
        ]
        
        # Mock scan result with placeholders
        scan_result = """
        [REDACTED_PERSON_1] can be reached at [REDACTED_EMAIL_ADDRESS_1]
        Phone: [REDACTED_PHONE_NUMBER_1], SSN: [REDACTED_US_SSN_1]
        Works at [REDACTED_ORGANIZATION_1] in [REDACTED_LOCATION_1]
        IP: [REDACTED_IP_ADDRESS_1], Card: [REDACTED_CREDIT_CARD_1]
        """
        scanner.scan.return_value = (scan_result, False, 0.95)
        
        with patch('anonymizer.PIIAnonymizer._create_scanner', return_value=(scanner, mock_vault)):
            text, stats, mappings = anonymizer.anonymize_with_vault("Original text")
        
        # Verify all entity types were processed
        assert len(stats) == 8
        assert all(count == 1 for count in stats.values())
        
        # Verify replacements were made
        assert "Robert Johnson" in text  # PERSON
        assert "robert.johnson@example.com" in text  # EMAIL
        assert "+1-555-987-6543" in text  # PHONE
        assert "987-65-4321" in text  # SSN
        assert "Global Industries" in text  # ORGANIZATION
        assert "Chicago" in text  # LOCATION
        assert "10.0.0.1" in text  # IP
        assert "4222" in text  # Part of CREDIT_CARD
    
    def test_anonymize_with_vault_multiple_same_entity(
        self, mock_llm_guard, mock_faker
    ):
        """Test handling multiple occurrences of same entity type."""
        anonymizer = PIIAnonymizer()
        anonymizer.faker = mock_faker
        scanner, _ = mock_llm_guard
        
        # Create a mock vault
        mock_vault = Mock()
        mock_vault.get.return_value = [
            ("[REDACTED_PERSON_1]", "John Smith"),
            ("[REDACTED_PERSON_2]", "Jane Doe"),
            ("[REDACTED_PERSON_3]", "Bob Wilson")
        ]
        
        scan_result = "[REDACTED_PERSON_1] met [REDACTED_PERSON_2] and [REDACTED_PERSON_3]"
        scanner.scan.return_value = (scan_result, False, 0.95)
        
        # Mock faker to return different values each time
        faker_names = ["Alice Brown", "Bob Green", "Carol White"]
        mock_faker.name.side_effect = faker_names
        
        with patch('anonymizer.PIIAnonymizer._create_scanner', return_value=(scanner, mock_vault)):
            text, stats, mappings = anonymizer.anonymize_with_vault("Original")
        
        # Each person should get a unique replacement
        assert stats["PERSON"] == 3
        assert len(mappings) == 3
        
        # Check that different names were used
        assert "Alice Brown" in text
        assert "Bob Green" in text
        assert "Carol White" in text
    
    def test_anonymize_consistency_across_calls(self, mock_llm_guard, mock_faker):
        """Test that same entities get same replacements across calls."""
        anonymizer = PIIAnonymizer()
        anonymizer.faker = mock_faker
        scanner, _ = mock_llm_guard
        
        # First call setup
        mock_vault1 = Mock()
        mock_vault1.get.return_value = [("[REDACTED_PERSON_1]", "John Smith")]
        scanner.scan.return_value = (
            "[REDACTED_PERSON_1] works here",
            False,
            0.95
        )
        
        # First call
        with patch('anonymizer.PIIAnonymizer._create_scanner', return_value=(scanner, mock_vault1)):
            text1, stats1, mappings1 = anonymizer.anonymize_with_vault(
                "John Smith works here"
            )
        
        # Second call setup - same entity
        mock_vault2 = Mock()
        mock_vault2.get.return_value = [("[REDACTED_PERSON_1]", "John Smith")]
        scanner.scan.return_value = (
            "[REDACTED_PERSON_1] called today",
            False,
            0.95
        )
        
        # Second call with same entity and previous mappings
        with patch('anonymizer.PIIAnonymizer._create_scanner', return_value=(scanner, mock_vault2)):
            text2, stats2, mappings2 = anonymizer.anonymize_with_vault(
                "John Smith called today",
                existing_mappings=mappings1
            )
        
        # Should use same replacement
        assert "Robert Johnson" in text1
        assert "Robert Johnson" in text2
        # Verify consistency
        assert mappings1["John Smith"] == "Robert Johnson"
        assert len(mappings2) == 0  # No new mappings since we reused existing
    
    def test_init_without_llm_guard(self):
        """Test that PIIAnonymizer raises error when llm-guard is not available."""
        with patch('anonymizer.LLM_GUARD_AVAILABLE', False):
            with pytest.raises(ImportError) as exc_info:
                PIIAnonymizer()
            assert "llm-guard is required" in str(exc_info.value)
    
    def test_custom_entity_types(self):
        """Test initialization with custom entity types."""
        custom_types = ["EMAIL_ADDRESS", "PERSON"]
        anonymizer = PIIAnonymizer(entity_types=custom_types)
        assert anonymizer.entity_types == custom_types
    
    def test_scanner_api_compatibility(self):
        """Test that scanner is created with correct API parameters."""
        anonymizer = PIIAnonymizer()
        
        with patch('anonymizer.Vault') as mock_vault_class:
            with patch('anonymizer.Anonymize') as mock_anonymize_class:
                with patch('anonymizer.DISTILBERT_AI4PRIVACY_v2_CONF', {'test': 'config'}):
                    mock_vault_instance = Mock()
                    mock_vault_class.return_value = mock_vault_instance
                    
                    scanner, vault = anonymizer._create_scanner()
                    
                    # Verify Anonymize was called with correct new API
                    mock_anonymize_class.assert_called_once_with(
                        vault=mock_vault_instance,
                        entity_types=anonymizer.DEFAULT_ENTITY_TYPES,
                        threshold=0.5,
                        use_faker=False,
                        recognizer_conf={'test': 'config'}
                    )
                    
                    # Verify it does NOT have old parameters
                    call_kwargs = mock_anonymize_class.call_args[1]
                    assert 'model_config' not in call_kwargs
                    assert 'score_threshold' not in call_kwargs
                    assert 'hide_pii' not in call_kwargs
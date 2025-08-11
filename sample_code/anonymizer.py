"""PII anonymization using LLM-Guard with consistent replacements."""

from typing import Dict, List, Tuple, Optional, Any
import logging
from datetime import timedelta
import random
from faker import Faker

from llm_guard.input_scanners import Anonymize
from llm_guard.input_scanners.anonymize_helpers import DISTILBERT_AI4PRIVACY_v2_CONF #confirm this is the best model before implementation
from llm_guard.vault import Vault

logger = logging.getLogger(__name__)


class PIIAnonymizer:
    """Handles PII detection and anonymization with consistent replacements."""
    
    # Universal PII scanners - comprehensive defaults
    DEFAULT_ENTITY_TYPES = [
        "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", 
        "US_SSN", "PASSPORT", "US_DRIVER_LICENSE",
        "IP_ADDRESS", "PERSON", "LOCATION",
        "ORGANIZATION", "DATE_TIME", "URL",
        "US_BANK_NUMBER", "CRYPTO", "MEDICAL_LICENSE"
    ]
    
    def __init__(self):
        self.faker = Faker()
        Faker.seed(random.randint(0, 10000))  # Random seed for each session
        self.date_shift_days = 365  # Default date shifting range


    
    def create_scanner(self) -> Anonymize:
        """Create LLM-Guard scanner instance with universal defaults."""
        return Anonymize(
            model_config=DISTILBERT_AI4PRIVACY_v2_CONF,
            entity_types=self.DEFAULT_ENTITY_TYPES,
            score_threshold=0.5,
            preamble="",
            use_faker=False,  # We handle faker replacements ourselves for consistency
            recognizer_config={"low_confidence_score_threshold": 0.3},
            hide_pii=True
        )
    
    def anonymize_with_vault(
        self,
        text: str,
        existing_mappings: Optional[Dict[str, str]] = None
    ) -> Tuple[str, Dict[str, int], Dict[str, str]]:
        """
        Anonymize text with consistent replacements.
        
        Args:
            text: Text to anonymize
            existing_mappings: Previous mappings for consistency
            
        Returns:
            Tuple of (anonymized_text, statistics, new_mappings)
        """
        scanner = self.create_scanner()
        vault = Vault()
        
        # First pass: detect PII with placeholders
        sanitized_prompt, is_valid, risk_score = scanner.scan(vault, text)
        
        if not is_valid:
            logger.info(f"PII detected with risk score: {risk_score}")
        
        # Apply consistent replacements
        anonymized_text = sanitized_prompt
        statistics = {}
        new_mappings = {}
        
        if existing_mappings is None:
            existing_mappings = {}
        
        # Process vault entries for consistent replacement
        for entity_type, values in vault._vault.items():
            statistics[entity_type] = len(values)
            
            for original_value in values:
                # Check if we already have a mapping
                if original_value in existing_mappings:
                    faker_value = existing_mappings[original_value]
                else:
                    # Generate new faker value based on type
                    faker_value = self._generate_faker_value(entity_type, original_value)
                    new_mappings[original_value] = faker_value
                
                # Replace placeholder with faker value
                placeholder = f"[REDACTED_{entity_type.upper()}]"
                if placeholder in anonymized_text:
                    anonymized_text = anonymized_text.replace(placeholder, faker_value, 1)
        
        return anonymized_text, statistics, new_mappings
    
    def _generate_faker_value(self, entity_type: str, original_value: str) -> str:
        """Generate appropriate faker value based on entity type."""
        faker_mappings = {
            "EMAIL_ADDRESS": self.faker.email,
            "PHONE_NUMBER": self.faker.phone_number,
            "CREDIT_CARD": self.faker.credit_card_number,
            "US_SSN": self.faker.ssn,
            "PASSPORT": lambda: self.faker.bothify(text='??#######').upper(),
            "US_DRIVER_LICENSE": lambda: self.faker.bothify(text='DL-########'),
            "IP_ADDRESS": self.faker.ipv4,
            "PERSON": self.faker.name,
            "LOCATION": self.faker.city,
            "ORGANIZATION": self.faker.company,
            "DATE_TIME": lambda: self.faker.date_time().isoformat(),
            "URL": self.faker.url,
            "US_BANK_NUMBER": self.faker.bban,
            "CRYPTO": lambda: self.faker.sha256()[:42],  # Ethereum-like address
            "MEDICAL_LICENSE": lambda: self.faker.bothify(text='MD-#######')
        }
        
        generator = faker_mappings.get(entity_type, lambda: f"REDACTED_{entity_type}")
        return generator()
    
    def generate_date_offset(self, max_days: int = None) -> int:
        """Generate random date offset for consistent date shifting."""
        if max_days is None:
            max_days = self.date_shift_days
        return random.randint(-max_days, max_days)

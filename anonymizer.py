"""PII anonymization using LLM-Guard with consistent replacements."""

from typing import Dict, List, Tuple, Optional, Any
import logging
from datetime import timedelta
import random
from faker import Faker

try:
    from llm_guard.input_scanners import Anonymize
    from llm_guard.input_scanners.anonymize_helpers import DISTILBERT_AI4PRIVACY_v2_CONF
    from llm_guard.vault import Vault
    LLM_GUARD_AVAILABLE = True
except ImportError:
    LLM_GUARD_AVAILABLE = False
    Anonymize = None
    DISTILBERT_AI4PRIVACY_v2_CONF = None
    Vault = None

logger = logging.getLogger(__name__)


class PIIAnonymizer:
    """Handles PII detection and anonymization with consistent replacements."""
    
    # Universal PII types - comprehensive defaults
    DEFAULT_ENTITY_TYPES = [
        "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", 
        "US_SSN", "PASSPORT", "US_DRIVER_LICENSE",
        "IP_ADDRESS", "PERSON", "LOCATION",
        "ORGANIZATION", "DATE_TIME", "URL",
        "US_BANK_NUMBER", "CRYPTO", "MEDICAL_LICENSE"
    ]
    
    def __init__(self, entity_types: Optional[List[str]] = None):
        """Initialize anonymizer with faker and default settings.
        
        Args:
            entity_types: List of entity types to detect. If None, uses defaults.
        """
        if not LLM_GUARD_AVAILABLE:
            raise ImportError(
                "llm-guard is required for PII anonymization. "
                "Install with: uv add 'llm-guard>=0.3.0'"
            )
        
        self.entity_types = entity_types or self.DEFAULT_ENTITY_TYPES
        self.faker = Faker()
        Faker.seed(random.randint(0, 10000))  # Random seed for each session
        self.date_shift_days = 365  # Default date shifting range
    
    def _create_scanner(self) -> Tuple[Anonymize, Vault]:
        """Create a new LLM-Guard scanner instance with a fresh vault."""
        # Always create a new vault for each scan to avoid cross-contamination
        vault = Vault()
        
        # Create scanner with new API
        scanner = Anonymize(
            vault=vault,
            entity_types=self.entity_types,
            threshold=0.5,
            use_faker=False,  # We handle faker replacements ourselves
            recognizer_conf=DISTILBERT_AI4PRIVACY_v2_CONF
        )
        return scanner, vault
    
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
        # Initialize mappings
        if existing_mappings is None:
            existing_mappings = {}
        
        # Create a fresh scanner and vault for this scan
        scanner, vault = self._create_scanner()
        
        # Run detection - new API doesn't take vault as parameter
        sanitized_prompt, is_valid, risk_score = scanner.scan(text)
        
        if not is_valid:
            logger.info(f"PII detected with risk score: {risk_score}")
        
        # Get vault entries
        vault_entries = vault.get()  # Returns list of (placeholder, original) tuples
        
        # Group entities by type for statistics
        entities_by_type = {}
        for placeholder, original_value in vault_entries:
            # Extract entity type from placeholder format [REDACTED_TYPE_NUM]
            entity_type = self._extract_entity_type(placeholder)
            if entity_type not in entities_by_type:
                entities_by_type[entity_type] = []
            entities_by_type[entity_type].append((placeholder, original_value))
        
        # Apply consistent replacements
        anonymized_text = sanitized_prompt
        statistics = {}
        new_mappings = {}
        
        for entity_type, entities in entities_by_type.items():
            statistics[entity_type] = len(entities)
            
            for placeholder, original_value in entities:
                # Check if we already have a mapping
                if original_value in existing_mappings:
                    faker_value = existing_mappings[original_value]
                else:
                    # Generate new faker value based on type
                    faker_value = self._generate_faker_value(entity_type, original_value)
                    new_mappings[original_value] = faker_value
                
                # Replace placeholder with faker value
                anonymized_text = anonymized_text.replace(placeholder, faker_value, 1)
        
        return anonymized_text, statistics, new_mappings
    
    def _extract_entity_type(self, placeholder: str) -> str:
        """Extract entity type from placeholder format.
        
        e.g., [REDACTED_PERSON_1] -> PERSON
        """
        if not placeholder.startswith("[REDACTED_") or not placeholder.endswith("]"):
            return "UNKNOWN"
            
        # Remove [REDACTED_ prefix and ] suffix, then split
        content = placeholder[10:-1]
        parts = content.rsplit("_", 1)
        
        # Return the type part if we have a number suffix
        if len(parts) == 2 and parts[1].isdigit():
            return parts[0]
        return "UNKNOWN"
    
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
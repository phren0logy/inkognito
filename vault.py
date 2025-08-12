"""Vault management for reversible anonymization.

The vault uses a simple {original: replacement} mapping format for efficiency
and clarity. This format is sufficient for bidirectional mapping through the
create_reverse_mappings() method.

Design decisions:
- Simple flat dictionary structure for mappings
- No nested arrays or complex structures
- Reverse mappings created on-demand for restoration
- Extensible format with version field for future changes
"""

import json
from typing import Dict, Any, Tuple, Optional
from datetime import datetime
from pathlib import Path
import logging

from exceptions import VaultError

logger = logging.getLogger(__name__)


class VaultManager:
    """Manages anonymization vault for consistent replacements.
    
    The vault stores a simple mapping of original values to their faker replacements.
    This design allows for:
    - Easy serialization/deserialization
    - Efficient lookups during anonymization and restoration
    - Future extensibility (e.g., adding entity types, confidence scores)
    """
    
    VAULT_VERSION = "2.0"
    
    @staticmethod
    def serialize_vault(
        mappings: Dict[str, str],
        date_offset: int,
        total_files: int = 1
    ) -> Dict[str, Any]:
        """
        Serialize vault data to v2.0 format.
        
        The vault uses a simple {original: replacement} mapping format.
        This is intentionally simple to make the vault human-readable and
        easy to debug. Complex structures can be added in future versions
        if needed.
        
        Args:
            mappings: Dictionary of original -> replacement mappings
                     e.g., {"John Smith": "Robert Johnson", "jane@example.com": "bob@test.com"}
            date_offset: Date shift offset in days (for consistent date anonymization)
            total_files: Number of files processed
            
        Returns:
            Serialized vault data with metadata
            
        Example output:
            {
                "version": "2.0",
                "date_offset": -184,
                "mappings": {
                    "John Smith": "Robert Johnson",
                    "john.smith@example.com": "rjohnson@example.com"
                },
                "statistics": {
                    "files_processed": 1,
                    "total_replacements": 2
                },
                "created_at": "2024-01-15T10:30:00"
            }
        """
        # Calculate statistics
        total_replacements = len(mappings)
        
        return {
            "version": VaultManager.VAULT_VERSION,
            "date_offset": date_offset,
            "mappings": mappings,
            "statistics": {
                "files_processed": total_files,
                "total_replacements": total_replacements
            },
            "created_at": datetime.now().isoformat()
        }
    
    @staticmethod
    def deserialize_vault(
        vault_data: Optional[Dict[str, Any]]
    ) -> Tuple[Optional[int], Dict[str, str]]:
        """
        Deserialize v2.0 vault data.
        
        Args:
            vault_data: Serialized vault data
            
        Returns:
            Tuple of (date_offset, mappings_dict)
        """
        if not vault_data:
            return None, {}
        
        # Handle v2.0 format
        if vault_data.get("version") == "2.0":
            date_offset = vault_data.get("date_offset")
            mappings = vault_data.get("mappings", {})
            return date_offset, mappings
        
        # Handle legacy formats if needed
        logger.warning(f"Unknown vault version: {vault_data.get('version')}")
        return None, {}
    
    @staticmethod
    def save_vault(
        vault_path: Path,
        mappings: Dict[str, str],
        date_offset: int,
        total_files: int = 1
    ) -> None:
        """Save vault to file.
        
        The vault format is a simple JSON file with:
        - version: Format version for future compatibility
        - date_offset: Days to shift dates for consistency
        - mappings: Simple {original: replacement} dictionary
        - statistics: Processing metadata
        - created_at: Timestamp of vault creation
        """
        try:
            # Ensure parent directory exists
            vault_path.parent.mkdir(parents=True, exist_ok=True)
            
            vault_data = VaultManager.serialize_vault(mappings, date_offset, total_files)
            
            with open(vault_path, 'w', encoding='utf-8') as f:
                json.dump(vault_data, f, indent=2)
            
            logger.info(f"Vault saved to {vault_path}")
        except Exception as e:
            raise VaultError(f"Failed to save vault: {e}")
    
    @staticmethod
    def load_vault(vault_path: Path) -> Tuple[Optional[int], Dict[str, str]]:
        """Load vault from file.
        
        Returns:
            Tuple of (date_offset, mappings_dict)
            
        Raises:
            VaultError: If vault file not found or invalid format
        """
        if not vault_path.exists():
            raise VaultError(f"Vault file not found: {vault_path}")
        
        try:
            with open(vault_path, 'r', encoding='utf-8') as f:
                vault_data = json.load(f)
            
            # Validate required fields
            if not isinstance(vault_data, dict):
                raise VaultError("Invalid vault format: not a dictionary")
            
            if "version" not in vault_data:
                raise VaultError("Invalid vault format: missing version field")
                
            if vault_data["version"] != VaultManager.VAULT_VERSION:
                raise VaultError(f"Unsupported vault version: {vault_data['version']}")
            
            if "mappings" not in vault_data or "date_offset" not in vault_data:
                raise VaultError("Invalid vault format: missing required fields")
            
            return VaultManager.deserialize_vault(vault_data)
        except json.JSONDecodeError as e:
            raise VaultError(f"Invalid vault format: {e}")
        except Exception as e:
            if isinstance(e, VaultError):
                raise
            raise VaultError(f"Failed to load vault: {e}")
    
    @staticmethod
    def create_reverse_mappings(mappings: Dict[str, str]) -> Dict[str, str]:
        """
        Create reverse mappings for restoration.
        
        Args:
            mappings: Original -> replacement mappings
            
        Returns:
            Replacement -> original mappings
        """
        return {v: k for k, v in mappings.items()}
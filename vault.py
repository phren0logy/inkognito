"""Vault management for reversible anonymization."""

import json
from typing import Dict, Any, Tuple, Optional
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class VaultManager:
    """Manages anonymization vault for consistent replacements."""
    
    VAULT_VERSION = "2.0"
    
    @staticmethod
    def serialize_vault(
        mappings: Dict[str, str],
        date_offset: int,
        total_files: int = 1
    ) -> Dict[str, Any]:
        """
        Serialize vault data to v2.0 format.
        
        Args:
            mappings: Dictionary of original -> replacement mappings
            date_offset: Date shift offset in days
            total_files: Number of files processed
            
        Returns:
            Serialized vault data
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
        """Save vault to file."""
        vault_data = VaultManager.serialize_vault(mappings, date_offset, total_files)
        
        with open(vault_path, 'w', encoding='utf-8') as f:
            json.dump(vault_data, f, indent=2)
        
        logger.info(f"Vault saved to {vault_path}")
    
    @staticmethod
    def load_vault(vault_path: Path) -> Tuple[Optional[int], Dict[str, str]]:
        """Load vault from file."""
        if not vault_path.exists():
            raise FileNotFoundError(f"Vault file not found: {vault_path}")
        
        with open(vault_path, 'r', encoding='utf-8') as f:
            vault_data = json.load(f)
        
        return VaultManager.deserialize_vault(vault_data)
    
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
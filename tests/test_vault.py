"""Tests for vault functionality."""

import pytest
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, mock_open

from vault import VaultManager
from exceptions import VaultError


class TestVaultManager:
    """Test the VaultManager class."""
    
    def test_save_vault_success(self, temp_directory, mock_vault_data):
        """Test successful vault saving."""
        vault_path = temp_directory / "test_vault.json"
        mappings = mock_vault_data["mappings"]
        date_offset = mock_vault_data["date_offset"]
        
        VaultManager.save_vault(vault_path, mappings, date_offset, 1)
        
        assert vault_path.exists()
        
        # Load and verify content
        with open(vault_path, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data["version"] == "2.0"
        assert saved_data["date_offset"] == date_offset
        assert saved_data["statistics"]["files_processed"] == 1
        assert saved_data["mappings"] == mappings
        assert "created_at" in saved_data
    
    def test_save_vault_creates_parent_directory(self, temp_directory):
        """Test that save_vault creates parent directories if needed."""
        vault_path = temp_directory / "nested" / "dirs" / "vault.json"
        mappings = {"test": "replacement"}
        
        VaultManager.save_vault(vault_path, mappings, 0, 1)
        
        assert vault_path.exists()
        assert vault_path.parent.exists()
    
    def test_save_vault_empty_mappings(self, temp_directory):
        """Test saving vault with empty mappings."""
        vault_path = temp_directory / "empty_vault.json"
        
        VaultManager.save_vault(vault_path, {}, 0, 0)
        
        with open(vault_path, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data["mappings"] == {}
        assert saved_data["statistics"]["files_processed"] == 0
    
    def test_save_vault_io_error(self, temp_directory):
        """Test handling IO errors during save."""
        vault_path = temp_directory / "vault.json"
        
        with patch('builtins.open', side_effect=IOError("Permission denied")):
            with pytest.raises(VaultError, match="Failed to save vault"):
                VaultManager.save_vault(vault_path, {}, 0, 1)
    
    def test_load_vault_success(self, temp_directory, mock_vault_data):
        """Test successful vault loading."""
        vault_path = temp_directory / "test_vault.json"
        
        # Save vault data
        with open(vault_path, 'w') as f:
            json.dump(mock_vault_data, f)
        
        date_offset, mappings = VaultManager.load_vault(vault_path)
        
        assert date_offset == mock_vault_data["date_offset"]
        assert mappings == mock_vault_data["mappings"]
    
    def test_load_vault_file_not_found(self):
        """Test loading non-existent vault file."""
        with pytest.raises(VaultError, match="Vault file not found"):
            VaultManager.load_vault(Path("/nonexistent/vault.json"))
    
    def test_load_vault_invalid_json(self, temp_directory):
        """Test loading vault with invalid JSON."""
        vault_path = temp_directory / "invalid.json"
        vault_path.write_text("{ invalid json }")
        
        with pytest.raises(VaultError, match="Invalid vault format"):
            VaultManager.load_vault(vault_path)
    
    def test_load_vault_missing_version(self, temp_directory):
        """Test loading vault without version field."""
        vault_path = temp_directory / "no_version.json"
        data = {
            "mappings": {},
            "date_offset": 0,
            "statistics": {
                "files_processed": 1,
                "total_replacements": 0
            }
        }
        with open(vault_path, 'w') as f:
            json.dump(data, f)
        
        with pytest.raises(VaultError, match="Invalid vault format"):
            VaultManager.load_vault(vault_path)
    
    def test_load_vault_unsupported_version(self, temp_directory):
        """Test loading vault with unsupported version."""
        vault_path = temp_directory / "old_version.json"
        data = {
            "version": "1.0",  # Old version
            "mappings": {},
            "date_offset": 0
        }
        with open(vault_path, 'w') as f:
            json.dump(data, f)
        
        with pytest.raises(VaultError, match="Unsupported vault version"):
            VaultManager.load_vault(vault_path)
    
    def test_load_vault_missing_fields(self, temp_directory):
        """Test loading vault with missing required fields."""
        vault_path = temp_directory / "incomplete.json"
        data = {
            "version": "2.0",
            "mappings": {}
            # Missing date_offset
        }
        with open(vault_path, 'w') as f:
            json.dump(data, f)
        
        with pytest.raises(VaultError, match="Invalid vault format"):
            VaultManager.load_vault(vault_path)
    
    def test_create_reverse_mappings_simple(self):
        """Test creating reverse mappings from vault format."""
        mappings = {
            "John Smith": "Robert Johnson",
            "john@example.com": "robert@example.com"
        }
        
        reverse = VaultManager.create_reverse_mappings(mappings)
        
        assert reverse["Robert Johnson"] == "John Smith"
        assert reverse["robert@example.com"] == "john@example.com"
        assert len(reverse) == 2
    
    def test_create_reverse_mappings_empty(self):
        """Test creating reverse mappings from empty vault."""
        reverse = VaultManager.create_reverse_mappings({})
        assert reverse == {}
    
    def test_create_reverse_mappings_multiple_originals(self):
        """Test reverse mappings with multiple original values."""
        # This shouldn't happen in practice, but test the edge case
        mappings = {
            "John Smith": "Bob Wilson",
            "Jane Doe": "Bob Wilson"  # Same replacement!
        }
        
        reverse = VaultManager.create_reverse_mappings(mappings)
        
        # Last one wins in this edge case
        assert reverse["Bob Wilson"] == "Jane Doe"
    
    def test_create_reverse_mappings_consistent_format(self):
        """Test that reverse mappings work with consistent format."""
        # All mappings are simple string-to-string
        mappings = {
            "John Smith": "Robert Johnson",
            "jane@example.com": "bob@example.com",
            "192.168.1.1": "10.0.0.1"
        }
        
        reverse = VaultManager.create_reverse_mappings(mappings)
        
        # All entries should be reversed
        assert len(reverse) == 3
        assert reverse["Robert Johnson"] == "John Smith"
        assert reverse["bob@example.com"] == "jane@example.com"
        assert reverse["10.0.0.1"] == "192.168.1.1"
    
    def test_vault_format_preservation(self, temp_directory):
        """Test that vault format is preserved through save/load cycle."""
        vault_path = temp_directory / "preserve.json"
        original_mappings = {
            "John Smith": "Robert Johnson",
            "Acme Corp": "Global Industries",
            "+1-555-1234": "+1-555-9876",
            "192.168.1.1": "10.0.0.1"
        }
        original_offset = 180
        
        # Save
        VaultManager.save_vault(vault_path, original_mappings, original_offset, 5)
        
        # Load
        loaded_offset, loaded_mappings = VaultManager.load_vault(vault_path)
        
        # Verify exact match
        assert loaded_offset == original_offset
        assert loaded_mappings == original_mappings
    
    def test_vault_metadata_fields(self, temp_directory):
        """Test that all metadata fields are saved correctly."""
        vault_path = temp_directory / "metadata.json"
        
        with patch('vault.datetime') as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = "2024-01-01T12:00:00"
            VaultManager.save_vault(vault_path, {}, 90, 3)
        
        with open(vault_path, 'r') as f:
            data = json.load(f)
        
        assert data["created_at"] == "2024-01-01T12:00:00"
        assert data["statistics"]["files_processed"] == 3
        assert data["date_offset"] == 90
        assert data["version"] == "2.0"
    
    def test_large_vault_handling(self, temp_directory):
        """Test handling large vaults with many mappings."""
        vault_path = temp_directory / "large.json"
        
        # Create large mappings
        large_mappings = {}
        for i in range(1000):
            original = f"entity_{i}@example.com"
            replacement = f"replacement_{i}@example.com"
            large_mappings[original] = replacement
        
        # Save large vault
        VaultManager.save_vault(vault_path, large_mappings, 0, 100)
        
        # Load and verify
        date_offset, loaded_mappings = VaultManager.load_vault(vault_path)
        
        assert len(loaded_mappings) == 1000
        assert loaded_mappings["entity_500@example.com"] == "replacement_500@example.com"
    
    def test_special_characters_in_mappings(self, temp_directory):
        """Test handling special characters in vault mappings."""
        vault_path = temp_directory / "special.json"
        
        special_mappings = {
            "John \"Doc\" Smith": "Robert 'Bob' Johnson",
            "email@[192.168.1.1]": "test@example.com",
            "line1\nline2": "single line",
            "tab\there": "no tab"
        }
        
        VaultManager.save_vault(vault_path, special_mappings, 0, 1)
        date_offset, loaded = VaultManager.load_vault(vault_path)
        
        assert loaded == special_mappings
"""Extractor registry and auto-discovery for Inkognito."""

from .base import BaseExtractor, ExtractionResult
from .registry import registry

# Export key items
__all__ = ["BaseExtractor", "ExtractionResult", "registry"]
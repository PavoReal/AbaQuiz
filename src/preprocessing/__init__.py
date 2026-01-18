"""
PDF preprocessing module for BCBA study materials.

This module provides tools to:
1. Process BCBA study PDFs using Claude's native PDF support
2. Filter BCBA-relevant documents and skip non-relevant ones
3. Output organized markdown files for question generation

Usage:
    python -m src.preprocessing.run_preprocessing --input data/raw/ --output data/processed/
"""

from .pdf_processor import (
    BCBA_DOCUMENTS,
    SKIP_DOCUMENTS,
    PDFProcessor,
    ProcessedDocument,
    PersistentRateLimitError,
    get_document_output_path,
)

__all__ = [
    "BCBA_DOCUMENTS",
    "SKIP_DOCUMENTS",
    "PDFProcessor",
    "ProcessedDocument",
    "PersistentRateLimitError",
    "get_document_output_path",
]

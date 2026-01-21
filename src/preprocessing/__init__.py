"""
PDF preprocessing module for BCBA study materials.

This module provides tools to:
1. Process BCBA study PDFs using GPT 5.2's native PDF support
2. Convert PDFs to markdown with 1:1 filename mapping (foo.pdf -> foo.md)
3. Output markdown files for question generation

Usage:
    python -m src.preprocessing.run_preprocessing --input data/raw/ --output data/processed/
"""

from .pdf_processor import (
    PDFProcessor,
    ProcessedDocument,
    PersistentRateLimitError,
    get_document_output_path,
)

__all__ = [
    "PDFProcessor",
    "ProcessedDocument",
    "PersistentRateLimitError",
    "get_document_output_path",
]

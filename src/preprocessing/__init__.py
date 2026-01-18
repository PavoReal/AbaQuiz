"""
PDF preprocessing module for BCBA study materials.

This module provides tools to:
1. Extract text and tables from BCBA study PDFs
2. Clean and structure content using Claude API
3. Classify content into BCBA Task List content areas
4. Output organized markdown files for question generation

Usage:
    python -m src.preprocessing.run_preprocessing --input data/raw/ --output data/processed/
"""

from .pdf_extractor import (
    extract_pdf,
    extract_tables_as_markdown,
    pages_to_text,
    save_raw_extraction,
    load_raw_extraction,
)
from .content_processor import (
    ContentProcessor,
    PersistentRateLimitError,
    get_content_area_file_mapping,
    get_document_output_path,
    merge_content_by_area,
    estimate_tokens,
)

__all__ = [
    # PDF extraction
    "extract_pdf",
    "extract_tables_as_markdown",
    "pages_to_text",
    "save_raw_extraction",
    "load_raw_extraction",
    # Content processing
    "ContentProcessor",
    "PersistentRateLimitError",
    "get_content_area_file_mapping",
    "get_document_output_path",
    "merge_content_by_area",
    "estimate_tokens",
]

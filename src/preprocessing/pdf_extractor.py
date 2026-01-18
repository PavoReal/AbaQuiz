"""
PDF extraction module for BCBA study materials.

Uses pdfplumber to extract text and tables from PDF documents.
"""

import json
from pathlib import Path
from typing import Any

import pdfplumber

from src.config.logging import get_logger

logger = get_logger(__name__)


def extract_pdf(pdf_path: str | Path) -> list[dict[str, Any]]:
    """
    Extract text and tables from each page of a PDF.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        List of page dictionaries containing:
        - page_num: 1-indexed page number
        - text: Extracted text content
        - tables: List of tables as markdown strings
    """
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pages = []

    with pdfplumber.open(pdf_path) as pdf:
        logger.info(f"Extracting {pdf_path.name}: {len(pdf.pages)} pages")

        for page_num, page in enumerate(pdf.pages, start=1):
            page_data = {
                "page_num": page_num,
                "text": "",
                "tables": [],
            }

            # Extract text
            try:
                text = page.extract_text()
                if text:
                    page_data["text"] = _clean_text(text)
            except Exception as e:
                logger.warning(f"Failed to extract text from page {page_num}: {e}")

            # Extract tables
            try:
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        if table and _is_valid_table(table):
                            md_table = _table_to_markdown(table)
                            if md_table:
                                page_data["tables"].append(md_table)
            except Exception as e:
                logger.warning(f"Failed to extract tables from page {page_num}: {e}")

            pages.append(page_data)

    logger.info(
        f"Extracted {len(pages)} pages from {pdf_path.name}, "
        f"{sum(len(p['tables']) for p in pages)} tables found"
    )

    return pages


def _clean_text(text: str) -> str:
    """
    Clean extracted text by fixing common issues.

    - Normalize whitespace
    - Fix hyphenated line breaks
    - Remove excessive newlines
    """
    # Fix hyphenated line breaks (word- continuation)
    text = text.replace("-\n", "")

    # Normalize line breaks
    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        line = line.strip()
        if line:
            cleaned_lines.append(line)

    # Join with single newlines, preserving paragraph breaks
    result = []
    prev_empty = False

    for line in cleaned_lines:
        if not line:
            if not prev_empty:
                result.append("")
                prev_empty = True
        else:
            result.append(line)
            prev_empty = False

    return "\n".join(result)


def _is_valid_table(table: list[list]) -> bool:
    """Check if a table has valid content (not just empty cells)."""
    if not table or len(table) < 2:
        return False

    # Check if table has at least some non-empty cells
    non_empty_cells = sum(
        1 for row in table for cell in row if cell and str(cell).strip()
    )

    return non_empty_cells >= 3


def _table_to_markdown(table: list[list]) -> str:
    """
    Convert a pdfplumber table to markdown format.

    Args:
        table: List of rows, each row is a list of cell values

    Returns:
        Markdown table string
    """
    if not table:
        return ""

    # Clean cell values
    cleaned_table = []
    for row in table:
        cleaned_row = []
        for cell in row:
            if cell is None:
                cleaned_row.append("")
            else:
                # Clean cell content
                cell_text = str(cell).strip()
                # Replace newlines within cells with spaces
                cell_text = " ".join(cell_text.split())
                # Escape pipe characters
                cell_text = cell_text.replace("|", "\\|")
                cleaned_row.append(cell_text)
        cleaned_table.append(cleaned_row)

    if not cleaned_table:
        return ""

    # Build markdown table
    lines = []

    # Header row
    header = cleaned_table[0]
    lines.append("| " + " | ".join(header) + " |")

    # Separator row
    separators = ["---"] * len(header)
    lines.append("| " + " | ".join(separators) + " |")

    # Data rows
    for row in cleaned_table[1:]:
        # Pad row to match header length
        while len(row) < len(header):
            row.append("")
        lines.append("| " + " | ".join(row[: len(header)]) + " |")

    return "\n".join(lines)


def extract_tables_as_markdown(tables: list[list[list]]) -> str:
    """
    Convert multiple pdfplumber tables to markdown format.

    Args:
        tables: List of tables from pdfplumber

    Returns:
        Markdown string with all tables separated by blank lines
    """
    md_tables = []

    for table in tables:
        if table and _is_valid_table(table):
            md = _table_to_markdown(table)
            if md:
                md_tables.append(md)

    return "\n\n".join(md_tables)


def pages_to_text(pages: list[dict[str, Any]]) -> str:
    """
    Convert extracted pages to a single text string.

    Combines text and tables from all pages.

    Args:
        pages: List of page dictionaries from extract_pdf

    Returns:
        Combined text content
    """
    parts = []

    for page in pages:
        page_content = []

        # Add page text
        if page["text"]:
            page_content.append(page["text"])

        # Add tables
        for table in page["tables"]:
            page_content.append("\n" + table + "\n")

        if page_content:
            parts.append("\n".join(page_content))

    return "\n\n".join(parts)


def save_raw_extraction(
    pages: list[dict[str, Any]],
    output_path: str | Path,
) -> None:
    """
    Save raw extracted content to JSON for inspection/debugging.

    Args:
        pages: List of page dictionaries from extract_pdf
        output_path: Path to save JSON file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(pages, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved raw extraction to {output_path}")


def load_raw_extraction(json_path: str | Path) -> list[dict[str, Any]]:
    """
    Load previously saved raw extraction from JSON.

    Args:
        json_path: Path to JSON file

    Returns:
        List of page dictionaries
    """
    json_path = Path(json_path)

    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

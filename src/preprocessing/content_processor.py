"""
Content processing module for BCBA study materials.

Uses Claude API to clean, structure, and classify extracted PDF content.
"""

import asyncio
import json
import re
from pathlib import Path
from typing import Any, Optional

import anthropic

from src.config.constants import ContentArea
from src.config.logging import get_logger

logger = get_logger(__name__)

# Extended backoff delays in seconds (1 min, 5 min, 10 min)
EXTENDED_BACKOFF_DELAYS = [60, 300, 600]


class PersistentRateLimitError(Exception):
    """Raised when rate limiting persists after all extended backoff attempts."""

    pass

# Content area names for classification
CONTENT_AREA_NAMES = [area.value for area in ContentArea]

# System prompt for content cleanup
CLEANUP_SYSTEM_PROMPT = """You are processing BCBA exam study material. Your task is to clean and structure the raw extracted text into well-formatted markdown.

Guidelines:
1. Fix any OCR/extraction errors or garbled text
2. Structure the content with proper markdown headers (# ## ###)
3. Convert any tables to markdown table format
4. Preserve ALL factual content exactly - do not summarize or omit information
5. Remove page numbers, headers/footers, and formatting artifacts
6. Fix broken words and sentences that were split across lines
7. Maintain the original document structure and hierarchy
8. Use bullet points or numbered lists where appropriate

Output clean, well-structured markdown only. Do not add commentary or explanations."""

# System prompt for content area classification
CLASSIFICATION_SYSTEM_PROMPT = """You are classifying BCBA study content into content areas from the BCBA 5th Edition Task List.

The 9 content areas are:
1. Philosophical Underpinnings - Behaviorism philosophy, determinism, parsimony, empiricism
2. Concepts and Principles - Basic behavior principles, reinforcement, punishment, stimulus control
3. Measurement, Data Display, and Interpretation - Data collection, graphing, analysis
4. Experimental Design - Research methods, experimental control, validity
5. Ethics - Professional conduct, ethical codes, boundaries
6. Behavior Assessment - FBA, assessments, data-based decision making
7. Behavior-Change Procedures - Reinforcement-based procedures, punishment, stimulus control procedures
8. Selecting and Implementing Interventions - Treatment selection, implementation, monitoring
9. Personnel Supervision and Management - Supervision requirements, training, management

Classify the content into the SINGLE most appropriate content area.
Respond with ONLY the exact area name from the list above, nothing else."""


class ContentProcessor:
    """Processes extracted PDF content using Claude API."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-haiku-4-5-20250514",
        max_tokens_per_chunk: int = 4000,
        delay_between_calls: float = 1.2,  # 50 req/min max = 1.2s between calls
    ) -> None:
        """
        Initialize the content processor.

        Args:
            api_key: Anthropic API key
            model: Claude model to use
            max_tokens_per_chunk: Max tokens per API request
            delay_between_calls: Delay in seconds between API calls
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens_per_chunk = max_tokens_per_chunk
        self.delay_between_calls = delay_between_calls

        # Total token tracking (across all PDFs)
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_api_calls = 0

        # Per-PDF token tracking
        self._pdf_input_tokens = 0
        self._pdf_output_tokens = 0
        self._pdf_api_calls = 0

        logger.info(f"ContentProcessor initialized with model: {self.model}")

    def reset_pdf_tokens(self) -> None:
        """Reset per-PDF token counters. Call before processing each PDF."""
        self._pdf_input_tokens = 0
        self._pdf_output_tokens = 0
        self._pdf_api_calls = 0

    @property
    def pdf_tokens(self) -> dict[str, int]:
        """Get token usage for current PDF."""
        return {
            "input": self._pdf_input_tokens,
            "output": self._pdf_output_tokens,
            "calls": self._pdf_api_calls,
        }

    @property
    def total_tokens(self) -> dict[str, int]:
        """Get total token usage across all PDFs."""
        return {
            "input": self._total_input_tokens,
            "output": self._total_output_tokens,
            "calls": self._total_api_calls,
        }

    def _log_api_call(
        self,
        call_type: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Log an API call with token stats."""
        # Update counters
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        self._total_api_calls += 1

        self._pdf_input_tokens += input_tokens
        self._pdf_output_tokens += output_tokens
        self._pdf_api_calls += 1

        logger.info(
            f"LLM call [{call_type}]: "
            f"{input_tokens:,} in / {output_tokens:,} out | "
            f"PDF total: {self._pdf_input_tokens:,} in / {self._pdf_output_tokens:,} out "
            f"({self._pdf_api_calls} calls)"
        )

    async def _call_with_extended_backoff(
        self,
        call_type: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        retries: int = 3,
    ) -> str:
        """
        Make an API call with initial retries and extended backoff on persistent failures.

        Args:
            call_type: Type of call for logging ("cleanup" or "classify")
            system_prompt: System prompt for the API call
            user_prompt: User prompt for the API call
            max_tokens: Maximum tokens for response
            retries: Number of initial retries per attempt

        Returns:
            Response text from the API

        Raises:
            PersistentRateLimitError: If all extended backoff attempts fail
        """
        # Try with initial retries first
        for attempt in range(retries):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )

                self._log_api_call(
                    call_type,
                    response.usage.input_tokens,
                    response.usage.output_tokens,
                )

                await asyncio.sleep(self.delay_between_calls)
                return response.content[0].text

            except anthropic.RateLimitError:
                wait_time = (attempt + 1) * 10
                logger.warning(f"Rate limited, waiting {wait_time}s...")
                await asyncio.sleep(wait_time)

            except anthropic.APIError as e:
                logger.error(f"API error on attempt {attempt + 1}: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(5 * (attempt + 1))

        # Initial retries exhausted, try extended backoff
        logger.warning(f"Initial retries exhausted, starting extended backoff...")

        for i, delay in enumerate(EXTENDED_BACKOFF_DELAYS):
            delay_mins = delay // 60
            logger.warning(
                f"Extended backoff {i + 1}/{len(EXTENDED_BACKOFF_DELAYS)}: "
                f"waiting {delay_mins} minute(s)..."
            )
            await asyncio.sleep(delay)

            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )

                self._log_api_call(
                    call_type,
                    response.usage.input_tokens,
                    response.usage.output_tokens,
                )

                logger.info("Extended backoff successful, resuming normal operation")
                await asyncio.sleep(self.delay_between_calls)
                return response.content[0].text

            except anthropic.RateLimitError:
                logger.warning(f"Still rate limited after {delay_mins} minute wait")
                continue

            except anthropic.APIError as e:
                logger.error(f"API error during extended backoff: {e}")
                continue

        # All extended backoff attempts failed
        logger.error(
            "All extended backoff attempts failed (1min, 5min, 10min). "
            "Stopping to preserve progress."
        )
        raise PersistentRateLimitError(
            "Rate limiting persists after extended backoff. "
            "Progress has been saved - resume later with same command."
        )

    async def process_content(
        self,
        raw_text: str,
        source_doc: str,
        retries: int = 3,
    ) -> str:
        """
        Send raw text to Claude for cleanup and structuring.

        Args:
            raw_text: Raw extracted text from PDF
            source_doc: Name of source document for context
            retries: Number of retries on failure

        Returns:
            Cleaned and structured markdown text
        """
        if not raw_text.strip():
            return ""

        user_prompt = f"""Clean and structure this raw text extracted from "{source_doc}".

RAW TEXT:
{raw_text}

Output clean markdown only."""

        return await self._call_with_extended_backoff(
            call_type="cleanup",
            system_prompt=CLEANUP_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=8192,
            retries=retries,
        )

    async def classify_content_area(
        self,
        text: str,
        retries: int = 3,
    ) -> str:
        """
        Determine which BCBA content area a section belongs to.

        Args:
            text: Text content to classify
            retries: Number of retries on failure

        Returns:
            Content area name (defaults to "Concepts and Principles" if unclassifiable)
        """
        if not text.strip():
            return ContentArea.CONCEPTS_AND_PRINCIPLES.value

        # Use a sample of the text for classification (first ~2000 chars)
        sample = text[:2000] if len(text) > 2000 else text

        user_prompt = f"""Classify this BCBA study content:

{sample}

Content area:"""

        result = await self._call_with_extended_backoff(
            call_type="classify",
            system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=50,
            retries=retries,
        )

        result = result.strip()

        # Match to valid content area
        area = self._match_content_area(result)
        if area:
            logger.info(f"Classified content as: {area}")
            return area

        logger.warning(f"Unrecognized content area: {result}")
        return ContentArea.CONCEPTS_AND_PRINCIPLES.value

    def _match_content_area(self, text: str) -> Optional[str]:
        """Match a text response to a valid content area."""
        text_lower = text.lower().strip()

        # Try exact match first
        for area_name in CONTENT_AREA_NAMES:
            if text_lower == area_name.lower():
                return area_name

        # Try partial match
        for area_name in CONTENT_AREA_NAMES:
            if area_name.lower() in text_lower or text_lower in area_name.lower():
                return area_name

        # Try keyword matching
        keyword_map = {
            "philosophical": ContentArea.PHILOSOPHICAL_UNDERPINNINGS.value,
            "underpinning": ContentArea.PHILOSOPHICAL_UNDERPINNINGS.value,
            "concepts": ContentArea.CONCEPTS_AND_PRINCIPLES.value,
            "principles": ContentArea.CONCEPTS_AND_PRINCIPLES.value,
            "measurement": ContentArea.MEASUREMENT.value,
            "data display": ContentArea.MEASUREMENT.value,
            "experimental": ContentArea.EXPERIMENTAL_DESIGN.value,
            "design": ContentArea.EXPERIMENTAL_DESIGN.value,
            "ethics": ContentArea.ETHICS.value,
            "ethical": ContentArea.ETHICS.value,
            "assessment": ContentArea.BEHAVIOR_ASSESSMENT.value,
            "behavior-change": ContentArea.BEHAVIOR_CHANGE_PROCEDURES.value,
            "behavior change": ContentArea.BEHAVIOR_CHANGE_PROCEDURES.value,
            "procedures": ContentArea.BEHAVIOR_CHANGE_PROCEDURES.value,
            "intervention": ContentArea.INTERVENTIONS.value,
            "implementing": ContentArea.INTERVENTIONS.value,
            "supervision": ContentArea.SUPERVISION.value,
            "management": ContentArea.SUPERVISION.value,
            "personnel": ContentArea.SUPERVISION.value,
        }

        for keyword, area in keyword_map.items():
            if keyword in text_lower:
                return area

        return None

    async def process_chunks(
        self,
        text: str,
        source_doc: str,
        chunk_size: int = 6000,
        overlap: int = 200,
    ) -> str:
        """
        Process large text by splitting into chunks.

        Args:
            text: Full text to process
            source_doc: Name of source document
            chunk_size: Approximate characters per chunk
            overlap: Character overlap between chunks

        Returns:
            Combined processed markdown
        """
        if len(text) <= chunk_size:
            return await self.process_content(text, source_doc)

        chunks = self._split_into_chunks(text, chunk_size, overlap)
        logger.info(f"Processing {len(chunks)} chunks for {source_doc}")

        processed_chunks = []
        for i, chunk in enumerate(chunks, start=1):
            logger.debug(f"Processing chunk {i}/{len(chunks)}")
            processed = await self.process_content(chunk, f"{source_doc} (part {i})")
            if processed:
                processed_chunks.append(processed)

        return "\n\n".join(processed_chunks)

    def _split_into_chunks(
        self,
        text: str,
        chunk_size: int,
        overlap: int,
    ) -> list[str]:
        """Split text into overlapping chunks, trying to break at paragraph boundaries."""
        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            if end >= len(text):
                chunks.append(text[start:])
                break

            # Try to find a paragraph break near the end
            break_point = text.rfind("\n\n", start + chunk_size // 2, end)
            if break_point == -1:
                # Try single newline
                break_point = text.rfind("\n", start + chunk_size // 2, end)
            if break_point == -1:
                # Try space
                break_point = text.rfind(" ", start + chunk_size // 2, end)
            if break_point == -1:
                break_point = end

            chunks.append(text[start:break_point])
            start = break_point - overlap

        return chunks


async def merge_content_by_area(
    processed_chunks: list[dict[str, Any]],
) -> dict[str, list[str]]:
    """
    Combine processed content organized by content area.

    Args:
        processed_chunks: List of dicts with 'content' and 'content_area' keys

    Returns:
        Dict mapping content area names to lists of content strings
    """
    merged: dict[str, list[str]] = {}

    for chunk in processed_chunks:
        area = chunk.get("content_area", ContentArea.CONCEPTS_AND_PRINCIPLES.value)
        content = chunk.get("content", "")

        if not content.strip():
            continue

        if area not in merged:
            merged[area] = []

        merged[area].append(content)

    return merged


def get_content_area_file_mapping() -> dict[str, str]:
    """
    Get mapping of content area names to output file paths.

    Returns:
        Dict mapping content area names to relative file paths
    """
    return {
        ContentArea.PHILOSOPHICAL_UNDERPINNINGS.value: (
            "section_1_foundations/1.1_philosophical_underpinnings.md"
        ),
        ContentArea.CONCEPTS_AND_PRINCIPLES.value: (
            "section_1_foundations/1.2_concepts_and_principles.md"
        ),
        ContentArea.MEASUREMENT.value: "section_1_foundations/1.3_measurement.md",
        ContentArea.EXPERIMENTAL_DESIGN.value: (
            "section_1_foundations/1.4_experimental_design.md"
        ),
        ContentArea.ETHICS.value: "section_2_applications/2.1_ethics.md",
        ContentArea.BEHAVIOR_ASSESSMENT.value: (
            "section_2_applications/2.2_behavior_assessment.md"
        ),
        ContentArea.BEHAVIOR_CHANGE_PROCEDURES.value: (
            "section_2_applications/2.3_behavior_change_procedures.md"
        ),
        ContentArea.INTERVENTIONS.value: (
            "section_2_applications/2.4_interventions.md"
        ),
        ContentArea.SUPERVISION.value: (
            "section_2_applications/2.5_supervision.md"
        ),
    }


# Pre-defined file-to-content-area mappings for known documents
# This allows skipping Claude classification for obvious cases
KNOWN_DOCUMENT_AREAS: dict[str, list[str]] = {
    "Ethics-Code-for-Behavior-Analysts.pdf": [ContentArea.ETHICS.value],
    "RBT-Ethics-Code.pdf": [ContentArea.ETHICS.value],
    "Supervisor-Training-Curriculum.pdf": [ContentArea.SUPERVISION.value],
}

# Documents that should go to supplementary
SUPPLEMENTARY_DOCUMENTS: dict[str, str] = {
    "Ethics-Code-for-Behavior-Analysts.pdf": "supplementary/ethics_code.md",
    "ABA-Glossary-Workbook.pdf": "supplementary/glossary.md",
    "ABA-Terminology-Acronyms.pdf": "supplementary/key_terms.md",
    "PECS-Glossary.pdf": "supplementary/glossary.md",
}


def get_document_output_path(pdf_name: str) -> Optional[str]:
    """
    Get the output path for a known supplementary document.

    Args:
        pdf_name: Name of the PDF file

    Returns:
        Relative output path or None if not a known supplementary document
    """
    return SUPPLEMENTARY_DOCUMENTS.get(pdf_name)


def estimate_tokens(text: str) -> int:
    """
    Rough estimate of token count for text.

    Uses ~4 characters per token as approximation.
    """
    return len(text) // 4

"""
PDF processing module using OpenAI GPT 5.2's native PDF support.

Sends PDFs directly to GPT 5.2 API for extraction and structuring,
leveraging its 400K context window and native PDF capabilities.
"""

import asyncio
import base64
import io
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import openai
from openai import OpenAI
from pypdf import PdfReader, PdfWriter

from src.config.logging import get_logger

logger = get_logger(__name__)

# Extended backoff delays in seconds (1 min, 5 min, 10 min)
# Used only after SDK's built-in retries are exhausted
EXTENDED_BACKOFF_DELAYS = [60, 300, 600]


def _get_jittered_delay(base_delay: int) -> float:
    """Add random jitter (0-10%) to avoid thundering herd."""
    return base_delay * (1 + 0.1 * random.random())


class PersistentRateLimitError(Exception):
    """Raised when rate limiting persists after all extended backoff attempts."""

    pass


# System prompt for PDF extraction
PDF_EXTRACTION_PROMPT = """You are processing BCBA exam study material from a PDF document.

Your task:
1. Extract ALL content from this PDF, preserving structure
2. Convert to well-formatted markdown
3. Preserve tables as markdown tables - pay special attention to table formatting
4. Maintain hierarchical structure with proper # headers
5. Include ALL definitions, terms, and concepts - do not summarize
6. Fix any OCR artifacts or formatting issues if present

Output clean markdown only. No commentary or explanations."""

# Documents to process with their output paths (BCBA exam relevant materials only)
BCBA_DOCUMENTS: dict[str, str] = {
    # Core BCBA materials
    "BCBA-Task-List-5th-Edition.pdf": "core/task_list.md",
    "BCBA-Handbook.pdf": "core/handbook.md",
    "BCBA-TCO-6th-Edition.pdf": "core/tco.md",
    "BCBA-6th-Edition-Test-Content-Outline-240903-a.pdf": "core/tco.md",  # Updated TCO
    # Ethics
    "Ethics-Code-for-Behavior-Analysts.pdf": "ethics/ethics_code.md",
    # Supervision
    "Supervisor-Training-Curriculum.pdf": "supervision/curriculum.md",
    # Reference materials
    "ABA-Glossary-Workbook.pdf": "reference/glossary.md",
    "ABA-Terminology-Acronyms.pdf": "reference/key_terms.md",
    "PECS-Glossary.pdf": "reference/glossary.md",
}

# Documents to skip (not BCBA exam relevant)
SKIP_DOCUMENTS: set[str] = {
    "ACE-Provider-Handbook.pdf",
    "BCaBA-Handbook.pdf",
    "BCaBA-TCO-6th-Edition.pdf",
    "RBT-Ethics-Code.pdf",
    "RBT-Handbook.pdf",
    "ABA-101-Handouts.pdf",
    "ABA-Description-Michigan.pdf",
    "ABA-Introduction-Autism-NJ.pdf",
}


@dataclass
class ProcessedDocument:
    """Result of processing a PDF document."""

    markdown: str
    page_count: int
    input_tokens: int
    output_tokens: int
    api_calls: int


class PDFProcessor:
    """Process PDFs using OpenAI GPT 5.2's native PDF support."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.2",
        delay_between_calls: float = 1.0,
        max_tokens: int = 32768,
    ) -> None:
        """
        Initialize the PDF processor.

        Args:
            api_key: OpenAI API key
            model: OpenAI model to use (should support PDF input)
            delay_between_calls: Delay in seconds between API calls
            max_tokens: Maximum output tokens (GPT 5.2 supports up to 128K)
        """
        # Configure SDK with built-in retries (exponential backoff with jitter)
        # This handles 429/5xx errors automatically before our extended backoff kicks in
        self.client = OpenAI(
            api_key=api_key,
            max_retries=5,  # Increased from default 2
            timeout=300.0,  # 5 min timeout for large PDFs
        )
        self.model = model
        self.delay_between_calls = delay_between_calls
        self.max_tokens = max_tokens
        self.max_pages_per_request = 100  # GPT 5.2 supports up to 100 pages
        self.max_file_size_mb = 32  # GPT 5.2 supports up to 32MB

        # Total token tracking (across all PDFs)
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_api_calls = 0

        # Per-PDF token tracking
        self._pdf_input_tokens = 0
        self._pdf_output_tokens = 0
        self._pdf_api_calls = 0

        logger.info(f"PDFProcessor initialized with model: {self.model}")

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

    def _identify_rate_limit_type(self, error_message: str) -> str:
        """
        Identify which rate limit was exceeded from the error message.

        The API returns different messages for:
        - RPM: requests per minute limit
        - ITPM: input tokens per minute limit
        - OTPM: output tokens per minute limit

        Args:
            error_message: The error message from the RateLimitError

        Returns:
            String identifying the limit type: "RPM", "ITPM", "OTPM", or "unknown"
        """
        msg_lower = error_message.lower()

        if "request" in msg_lower:
            return "RPM"
        elif "input" in msg_lower:
            return "ITPM"
        elif "output" in msg_lower:
            return "OTPM"
        else:
            return "unknown"

    async def process_pdf(
        self,
        pdf_path: Path,
        verbose: bool = False,
    ) -> ProcessedDocument:
        """
        Process a PDF file using Claude's native PDF support.

        Args:
            pdf_path: Path to the PDF file
            verbose: Whether to log detailed progress

        Returns:
            ProcessedDocument with extracted markdown and metadata
        """
        pdf_name = pdf_path.name

        # Get page count
        reader = PdfReader(pdf_path)
        page_count = len(reader.pages)

        if verbose:
            logger.info(f"Processing {pdf_name}: {page_count} pages")

        # Check if PDF needs to be split
        pdf_chunks = self._split_large_pdf(pdf_path)

        if verbose:
            logger.info(f"Split into {len(pdf_chunks)} chunk(s)")

        # Process each chunk
        markdown_parts = []
        for i, chunk_bytes in enumerate(pdf_chunks, start=1):
            if verbose and len(pdf_chunks) > 1:
                logger.info(f"Processing chunk {i}/{len(pdf_chunks)}")

            chunk_markdown = await self._send_pdf_to_gpt(
                pdf_data=chunk_bytes,
                system_prompt=PDF_EXTRACTION_PROMPT,
                user_prompt=f"Extract and structure all content from this PDF document: {pdf_name}",
            )
            markdown_parts.append(chunk_markdown)

        # Combine all parts
        full_markdown = "\n\n".join(markdown_parts)

        # Debug: save response to file for inspection
        if verbose:
            debug_path = Path("data/debug_response.md")
            debug_path.write_text(full_markdown, encoding="utf-8")
            logger.info(f"DEBUG: Response saved to {debug_path}")

        return ProcessedDocument(
            markdown=full_markdown,
            page_count=page_count,
            input_tokens=self._pdf_input_tokens,
            output_tokens=self._pdf_output_tokens,
            api_calls=self._pdf_api_calls,
        )

    async def _send_pdf_to_gpt(
        self,
        pdf_data: bytes,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """
        Send PDF to GPT 5.2 API using file input type.

        SDK handles retries automatically (max_retries=5 with exponential backoff).
        Extended backoff is used only for persistent rate limiting in batch scenarios.

        Args:
            pdf_data: PDF file bytes
            system_prompt: System prompt
            user_prompt: User prompt

        Returns:
            Response text from the API
        """
        # Encode PDF as base64 data URL
        pdf_base64 = base64.standard_b64encode(pdf_data).decode("utf-8")

        # Build message with PDF file for GPT 5.2
        messages = [
            {
                "role": "developer",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "file",
                        "file": {
                            "filename": "document.pdf",
                            "file_data": f"data:application/pdf;base64,{pdf_base64}",
                        },
                    },
                    {
                        "type": "text",
                        "text": user_prompt,
                    },
                ],
            },
        ]

        return await self._call_with_extended_backoff(
            call_type="pdf_extract",
            messages=messages,
        )

    async def _call_with_extended_backoff(
        self,
        call_type: str,
        messages: list,
    ) -> str:
        """
        Make an API call with SDK built-in retries and extended backoff for batch processing.

        The OpenAI SDK handles initial retries automatically (max_retries=5 with exponential
        backoff and jitter). Extended backoff is only used for persistent rate limiting
        in batch processing scenarios where we want to wait longer rather than fail.

        Args:
            call_type: Type of call for logging
            messages: Messages list for the API call (includes developer message for system prompt)

        Returns:
            Response text from the API

        Raises:
            PersistentRateLimitError: If all extended backoff attempts fail
        """
        # First attempt - SDK handles retries automatically with exponential backoff
        try:
            logger.info(f"API call [{call_type}]: sending request to {self.model}")
            response = self.client.chat.completions.create(
                model=self.model,
                max_completion_tokens=self.max_tokens,
                messages=messages,
            )

            content = response.choices[0].message.content
            logger.info(
                f"API call [{call_type}]: received response, "
                f"{len(content):,} chars, finish_reason={response.choices[0].finish_reason}"
            )

            self._log_api_call(
                call_type,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
            )

            await asyncio.sleep(self.delay_between_calls)
            return content

        except openai.RateLimitError as e:
            # SDK retries exhausted - use extended backoff for batch processing
            limit_type = self._identify_rate_limit_type(str(e))
            logger.warning(
                f"SDK retries exhausted ({limit_type}), starting extended backoff for batch processing..."
            )

        except openai.APIError as e:
            # Non-rate-limit API errors - don't use extended backoff, just fail
            logger.error(f"API error (SDK retries exhausted): {e}")
            raise

        # Extended backoff - for persistent rate limiting in batch scenarios
        for i, base_delay in enumerate(EXTENDED_BACKOFF_DELAYS):
            # Add jitter to avoid thundering herd
            delay = _get_jittered_delay(base_delay)
            delay_mins = base_delay // 60

            logger.warning(
                f"Extended backoff {i + 1}/{len(EXTENDED_BACKOFF_DELAYS)}: "
                f"waiting ~{delay_mins} minute(s)..."
            )
            await asyncio.sleep(delay)

            try:
                logger.info(f"API call [{call_type}]: sending request to {self.model} (extended backoff {i + 1})")
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_completion_tokens=self.max_tokens,
                    messages=messages,
                )

                content = response.choices[0].message.content
                logger.info(
                    f"API call [{call_type}]: received response, "
                    f"{len(content):,} chars, finish_reason={response.choices[0].finish_reason}"
                )

                self._log_api_call(
                    call_type,
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                )

                logger.info("Extended backoff successful, resuming normal operation")
                await asyncio.sleep(self.delay_between_calls)
                return content

            except openai.RateLimitError as e:
                # Check if API provided a specific retry-after time
                retry_after = None
                if hasattr(e, "response") and e.response is not None:
                    retry_after = e.response.headers.get("retry-after")

                limit_type = self._identify_rate_limit_type(str(e))
                if retry_after:
                    logger.warning(
                        f"Still rate limited ({limit_type}) after {delay_mins} minute wait. "
                        f"API says wait {retry_after}s"
                    )
                else:
                    logger.warning(
                        f"Still rate limited ({limit_type}) after {delay_mins} minute wait"
                    )
                continue

            except openai.APIError as e:
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

    def _split_large_pdf(self, pdf_path: Path) -> list[bytes]:
        """
        Split PDF if it exceeds the page limit.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            List of PDF bytes (one item if no splitting needed)
        """
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)

        # Check file size
        file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
        if file_size_mb > self.max_file_size_mb:
            logger.warning(
                f"PDF file size ({file_size_mb:.1f}MB) exceeds limit "
                f"({self.max_file_size_mb}MB), will split by pages"
            )

        # If small enough, return as-is
        if total_pages <= self.max_pages_per_request:
            return [pdf_path.read_bytes()]

        logger.info(
            f"PDF has {total_pages} pages, splitting into "
            f"{(total_pages + self.max_pages_per_request - 1) // self.max_pages_per_request} chunks"
        )

        chunks = []
        for start in range(0, total_pages, self.max_pages_per_request):
            writer = PdfWriter()
            end = min(start + self.max_pages_per_request, total_pages)

            for page_num in range(start, end):
                writer.add_page(reader.pages[page_num])

            buffer = io.BytesIO()
            writer.write(buffer)
            chunks.append(buffer.getvalue())

        return chunks


def get_document_output_path(pdf_name: str) -> str | None:
    """
    Get output path for a document.

    Args:
        pdf_name: Name of the PDF file

    Returns:
        Output path if document should be processed, None if should be skipped
    """
    if pdf_name in SKIP_DOCUMENTS:
        return None  # Skip this document
    return BCBA_DOCUMENTS.get(pdf_name)

"""
PDF processing module using OpenAI GPT 5.2's native PDF support.

Sends PDFs directly to GPT 5.2 API for extraction and structuring,
leveraging its 400K context window and native PDF capabilities.
"""

import asyncio
import base64
import io
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import openai
from openai import AsyncOpenAI
from pypdf import PdfReader, PdfWriter

from src.config.logging import get_logger

logger = get_logger(__name__)

# Extended backoff delays in seconds (1 min, 5 min, 10 min)
# Used only after SDK's built-in retries are exhausted
EXTENDED_BACKOFF_DELAYS = [60, 300, 600]


def _get_jittered_delay(base_delay: int) -> float:
    """Add random jitter (0-10%) to avoid thundering herd."""
    return base_delay * (1 + 0.1 * random.random())


def _estimate_tokens_from_base64(base64_size: int) -> int:
    """Estimate input tokens from base64 encoded PDF size.

    Formula: base64_size × 0.75 (base64 overhead) ÷ 4 (chars per token) ≈ tokens
    More conservative: ~1.5 tokens per character of base64 for PDF content.
    """
    return int(base64_size * 0.75 / 4)


def _format_elapsed(seconds: float) -> str:
    """Format elapsed time as Xm Ys."""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    if mins > 0:
        return f"{mins}m {secs}s"
    return f"{secs}s"


def _estimate_cost(input_tokens: int, output_tokens: int = 0) -> float:
    """Estimate cost using GPT 5.2 pricing ($1.75/1M input, $14/1M output)."""
    input_cost = input_tokens / 1_000_000 * 1.75
    output_cost = output_tokens / 1_000_000 * 14.00
    return input_cost + output_cost


class PersistentRateLimitError(Exception):
    """Raised when rate limiting persists after all extended backoff attempts."""

    pass


class ContentFilterError(Exception):
    """Raised when API response is blocked by content filter."""

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


@dataclass
class ProcessedDocument:
    """Result of processing a PDF document."""

    markdown: str
    page_count: int
    input_tokens: int
    output_tokens: int
    api_calls: int


@dataclass
class ChunkJob:
    """A single chunk of a PDF to process."""

    pdf_name: str  # "BCBA-Handbook.pdf"
    chunk_index: int  # 0, 1, 2...
    total_chunks: int  # total chunks for this PDF
    pdf_data: bytes  # chunk PDF bytes
    estimated_tokens: int  # for progress display


@dataclass
class ChunkResult:
    """Result of processing a single chunk."""

    pdf_name: str
    chunk_index: int
    markdown: str
    input_tokens: int
    output_tokens: int
    error: str | None = None


class ProgressTracker:
    """Track concurrent API calls for unified progress display."""

    def __init__(self, max_concurrent: int = 3) -> None:
        self._max_concurrent = max_concurrent
        self._active: dict[str, tuple[ChunkJob, float]] = {}  # job_id -> (job, start_time)
        self._display_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._running = False
        self._total_estimated_cost = 0.0

    async def register(self, job: ChunkJob) -> str:
        """Register job, return job_id, start display if first."""
        job_id = f"{Path(job.pdf_name).stem}_{job.chunk_index + 1}"
        async with self._lock:
            self._active[job_id] = (job, time.time())
            self._total_estimated_cost += _estimate_cost(job.estimated_tokens)
            if not self._running:
                self._running = True
                self._display_task = asyncio.create_task(self._display_loop())
        return job_id

    async def unregister(self, job_id: str) -> None:
        """Remove job, stop display if last."""
        async with self._lock:
            if job_id in self._active:
                job, _ = self._active.pop(job_id)
                self._total_estimated_cost -= _estimate_cost(job.estimated_tokens)
            if not self._active and self._running:
                self._running = False
                if self._display_task:
                    self._display_task.cancel()
                    try:
                        await self._display_task
                    except asyncio.CancelledError:
                        pass
                    self._display_task = None
                # Clear the status line
                sys.stderr.write("\r" + " " * 100 + "\r")
                sys.stderr.flush()

    async def _display_loop(self) -> None:
        """Single stderr line showing all active jobs."""
        while self._running:
            async with self._lock:
                if not self._active:
                    break

                # Build status line
                active_count = len(self._active)
                parts = [f"Slots: {active_count}/{self._max_concurrent}"]

                # Add each active job with elapsed time
                for job_id, (job, start_time) in sorted(self._active.items()):
                    elapsed = time.time() - start_time
                    elapsed_str = _format_elapsed(elapsed)
                    parts.append(f"{job_id}: {elapsed_str}")

                # Add estimated cost
                parts.append(f"Est: ~${self._total_estimated_cost:.2f}")

                status_line = " | ".join(parts)
                sys.stderr.write(f"\r  {status_line}    ")
                sys.stderr.flush()

            await asyncio.sleep(1)


class PDFProcessor:
    """Process PDFs using OpenAI GPT 5.2's native PDF support."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.2",
        delay_between_calls: float = 1.0,
        max_tokens: int = 65536,
    ) -> None:
        """
        Initialize the PDF processor.

        Args:
            api_key: OpenAI API key
            model: OpenAI model to use (should support PDF input)
            delay_between_calls: Delay in seconds between API calls
            max_tokens: Maximum output tokens (GPT 5.2 supports up to 128K)
        """
        # Configure OpenAI client (extended backoff handles rate limits)
        self.client = AsyncOpenAI(
            api_key=api_key,
            max_retries=1,
            timeout=1800.0,  # 30 min timeout for large PDFs
        )
        self.model = model
        self.delay_between_calls = delay_between_calls
        self.max_tokens = max_tokens
        self.max_pages_per_request = 40  # Lower threshold to force chunking for faster processing
        self.max_file_size_mb = 32  # GPT 5.2 supports up to 32MB

        # Total token tracking (across all PDFs)
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_api_calls = 0

        # Per-PDF token tracking
        self._pdf_input_tokens = 0
        self._pdf_output_tokens = 0
        self._pdf_api_calls = 0

        # Progress tracker for parallel chunk processing
        self._progress_tracker: ProgressTracker | None = None

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
        Process a PDF file using GPT 5.2's native PDF support.

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

        # Process chunks (parallel for multiple chunks)
        if len(pdf_chunks) == 1:
            # Single chunk - no parallelization needed
            markdown_parts = [await self._send_pdf_to_gpt(
                pdf_data=pdf_chunks[0],
                system_prompt=PDF_EXTRACTION_PROMPT,
                user_prompt=f"Extract and structure all content from this PDF document: {pdf_name}",
            )]
        else:
            if verbose:
                logger.info(f"Processing {len(pdf_chunks)} chunks in parallel")

            tasks = [
                self._send_pdf_to_gpt(
                    pdf_data=chunk_bytes,
                    system_prompt=PDF_EXTRACTION_PROMPT,
                    user_prompt=f"Extract and structure content from this PDF (part {i}/{len(pdf_chunks)}): {pdf_name}",
                )
                for i, chunk_bytes in enumerate(pdf_chunks, start=1)
            ]
            markdown_parts = await asyncio.gather(*tasks)

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

        Extended backoff is used for rate limiting in batch scenarios.

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

        # Estimate tokens for progress display
        estimated_tokens = _estimate_tokens_from_base64(len(pdf_base64))

        return await self._call_with_extended_backoff(
            call_type="pdf_extract",
            messages=messages,
            estimated_input_tokens=estimated_tokens,
        )

    async def _call_with_extended_backoff(
        self,
        call_type: str,
        messages: list,
        estimated_input_tokens: int = 0,
    ) -> str:
        """
        Make an API call with extended backoff for batch processing.

        Extended backoff is used for rate limiting in batch processing scenarios
        where we want to wait longer rather than fail.

        Args:
            call_type: Type of call for logging
            messages: Messages list for the API call (includes developer message for system prompt)
            estimated_input_tokens: Estimated input tokens for progress display

        Returns:
            Response text from the API

        Raises:
            PersistentRateLimitError: If all extended backoff attempts fail
        """
        # Display progress info during API call
        est_cost = _estimate_cost(estimated_input_tokens)
        est_tokens_k = estimated_input_tokens / 1000

        async def _show_progress(start_time: float) -> None:
            """Show progress while waiting for API response."""
            while True:
                elapsed = time.time() - start_time
                elapsed_str = _format_elapsed(elapsed)
                # Write to stderr to avoid interfering with logs
                sys.stderr.write(
                    f"\r  Processing... Elapsed: {elapsed_str} | "
                    f"Est. input: ~{est_tokens_k:.0f}K tokens | "
                    f"Est. cost: ~${est_cost:.2f}    "
                )
                sys.stderr.flush()
                await asyncio.sleep(1)

        # First attempt - SDK handles retries automatically with exponential backoff
        start_time = time.time()
        progress_task = asyncio.create_task(_show_progress(start_time))
        try:
            logger.info(f"API call [{call_type}]: sending request to {self.model}")
            response = await self.client.chat.completions.create(
                model=self.model,
                max_completion_tokens=self.max_tokens,
                messages=messages,
            )
            progress_task.cancel()
            sys.stderr.write("\r" + " " * 80 + "\r")  # Clear progress line
            sys.stderr.flush()

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
            progress_task.cancel()
            sys.stderr.write("\r" + " " * 80 + "\r")  # Clear progress line
            sys.stderr.flush()
            # Rate limited - use extended backoff for batch processing
            limit_type = self._identify_rate_limit_type(str(e))
            logger.warning(
                f"Rate limited ({limit_type}), starting extended backoff..."
            )

        except openai.APIError as e:
            progress_task.cancel()
            sys.stderr.write("\r" + " " * 80 + "\r")  # Clear progress line
            sys.stderr.flush()
            # Non-rate-limit API errors - fail immediately
            logger.error(f"API error: {e}")
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
                response = await self.client.chat.completions.create(
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

    def prepare_chunks(self, pdf_path: Path) -> list[ChunkJob]:
        """
        Prepare chunk jobs for a PDF without processing.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            List of ChunkJob objects ready for parallel processing
        """
        pdf_name = pdf_path.name
        pdf_chunks = self._split_large_pdf(pdf_path)

        jobs = []
        for i, chunk_bytes in enumerate(pdf_chunks):
            # Estimate tokens from base64 size
            pdf_base64_len = len(base64.standard_b64encode(chunk_bytes))
            estimated_tokens = _estimate_tokens_from_base64(pdf_base64_len)

            jobs.append(
                ChunkJob(
                    pdf_name=pdf_name,
                    chunk_index=i,
                    total_chunks=len(pdf_chunks),
                    pdf_data=chunk_bytes,
                    estimated_tokens=estimated_tokens,
                )
            )

        return jobs

    async def process_chunks_parallel(
        self,
        jobs: list[ChunkJob],
        max_concurrent: int = 3,
    ) -> list[ChunkResult]:
        """
        Process chunk jobs with bounded concurrency.

        Args:
            jobs: List of ChunkJob objects to process
            max_concurrent: Maximum concurrent API calls

        Returns:
            List of ChunkResult objects in same order as input jobs
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        self._progress_tracker = ProgressTracker(max_concurrent)

        progress_tracker = self._progress_tracker  # Local reference for type checker

        async def process_one(job: ChunkJob) -> ChunkResult:
            async with semaphore:
                job_id = await progress_tracker.register(job)
                try:
                    markdown = await self._process_chunk_job(job)
                    return ChunkResult(
                        pdf_name=job.pdf_name,
                        chunk_index=job.chunk_index,
                        markdown=markdown,
                        input_tokens=0,  # Updated by _log_api_call
                        output_tokens=0,  # Updated by _log_api_call
                        error=None,
                    )
                except Exception as e:
                    logger.error(f"Error processing chunk {job_id}: {e}")
                    return ChunkResult(
                        pdf_name=job.pdf_name,
                        chunk_index=job.chunk_index,
                        markdown="",
                        input_tokens=0,
                        output_tokens=0,
                        error=str(e),
                    )
                finally:
                    await progress_tracker.unregister(job_id)

        results = await asyncio.gather(*[process_one(job) for job in jobs])
        self._progress_tracker = None
        return list(results)

    async def _process_chunk_job(self, job: ChunkJob) -> str:
        """
        Process a single chunk job with one retry on content filter.

        Args:
            job: ChunkJob to process

        Returns:
            Extracted markdown content
        """
        # Encode PDF as base64 data URL
        pdf_base64 = base64.standard_b64encode(job.pdf_data).decode("utf-8")

        # Build message with PDF file for GPT 5.2
        messages = [
            {
                "role": "developer",
                "content": PDF_EXTRACTION_PROMPT,
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
                        "text": f"Extract and structure content from this PDF (part {job.chunk_index + 1}/{job.total_chunks}): {job.pdf_name}",
                    },
                ],
            },
        ]

        # Try once, retry once on content filter
        try:
            return await self._call_api_no_progress(
                call_type="pdf_extract",
                messages=messages,
            )
        except ContentFilterError as e:
            job_id = f"{Path(job.pdf_name).stem}_{job.chunk_index + 1}"
            logger.warning(f"Content filter on {job_id}, retrying once: {e}")
            await asyncio.sleep(2)  # Brief delay before retry
            return await self._call_api_no_progress(
                call_type="pdf_extract_retry",
                messages=messages,
            )

    async def _call_api_no_progress(
        self,
        call_type: str,
        messages: list,
    ) -> str:
        """
        Make an API call without individual progress display.

        Used by parallel chunk processing where ProgressTracker handles display.

        Args:
            call_type: Type of call for logging
            messages: Messages list for the API call

        Returns:
            Response text from the API
        """
        # First attempt - SDK handles retries automatically
        try:
            logger.info(f"API call [{call_type}]: sending request to {self.model}")
            response = await self.client.chat.completions.create(
                model=self.model,
                max_completion_tokens=self.max_tokens,
                messages=messages,
            )

            finish_reason = response.choices[0].finish_reason
            content = response.choices[0].message.content or ""
            logger.info(
                f"API call [{call_type}]: received response, "
                f"{len(content):,} chars, finish_reason={finish_reason}"
            )

            self._log_api_call(
                call_type,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
            )

            # Check for content filter
            if finish_reason == "content_filter":
                raise ContentFilterError(
                    f"Response blocked by content filter (finish_reason={finish_reason})"
                )

            await asyncio.sleep(self.delay_between_calls)
            return content

        except openai.RateLimitError as e:
            # Rate limited - use extended backoff for batch processing
            limit_type = self._identify_rate_limit_type(str(e))
            logger.warning(
                f"Rate limited ({limit_type}), starting extended backoff..."
            )

        except openai.APIError as e:
            # Non-rate-limit API errors - fail immediately
            logger.error(f"API error: {e}")
            raise

        # Extended backoff - for persistent rate limiting in batch scenarios
        for i, base_delay in enumerate(EXTENDED_BACKOFF_DELAYS):
            delay = _get_jittered_delay(base_delay)
            delay_mins = base_delay // 60

            logger.warning(
                f"Extended backoff {i + 1}/{len(EXTENDED_BACKOFF_DELAYS)}: "
                f"waiting ~{delay_mins} minute(s)..."
            )
            await asyncio.sleep(delay)

            try:
                logger.info(f"API call [{call_type}]: sending request to {self.model} (extended backoff {i + 1})")
                response = await self.client.chat.completions.create(
                    model=self.model,
                    max_completion_tokens=self.max_tokens,
                    messages=messages,
                )

                finish_reason = response.choices[0].finish_reason
                content = response.choices[0].message.content or ""
                logger.info(
                    f"API call [{call_type}]: received response, "
                    f"{len(content):,} chars, finish_reason={finish_reason}"
                )

                self._log_api_call(
                    call_type,
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                )

                # Check for content filter
                if finish_reason == "content_filter":
                    raise ContentFilterError(
                        f"Response blocked by content filter (finish_reason={finish_reason})"
                    )

                logger.info("Extended backoff successful, resuming normal operation")
                await asyncio.sleep(self.delay_between_calls)
                return content

            except openai.RateLimitError as e:
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


def get_document_output_path(pdf_name: str) -> str:
    """Convert PDF filename to markdown output path (1:1 mapping).

    Args:
        pdf_name: Name of the PDF file (e.g., "foo.pdf")

    Returns:
        Output path as markdown file (e.g., "foo.md")
    """
    stem = Path(pdf_name).stem
    return f"{stem}.md"

"""
CLI for running the PDF preprocessing pipeline.

Usage:
    python -m src.preprocessing.run_preprocessing --input data/raw/ --output data/processed/
    python -m src.preprocessing.run_preprocessing -f data/raw/bacb/Ethics-Code-for-Behavior-Analysts.pdf -v
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.config.logging import get_logger, setup_logging
from src.preprocessing.content_processor import (
    ContentProcessor,
    PersistentRateLimitError,
    SUPPLEMENTARY_DOCUMENTS,
    get_content_area_file_mapping,
    get_document_output_path,
    estimate_tokens,
)
from src.preprocessing.pdf_extractor import (
    extract_pdf,
    pages_to_text,
    save_raw_extraction,
    load_raw_extraction,
)

logger = get_logger(__name__)


MANIFEST_FILENAME = "preprocessing_manifest.json"


def discover_pdfs(input_dir: Path) -> list[Path]:
    """Find all PDF files in input directory and subdirectories."""
    pdfs = list(input_dir.glob("**/*.pdf"))
    return sorted(pdfs)


def load_manifest(output_dir: Path) -> dict[str, Any]:
    """Load the preprocessing manifest tracking processed PDFs."""
    manifest_path = output_dir / MANIFEST_FILENAME
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"processed": {}, "version": 1}


def save_manifest(output_dir: Path, manifest: dict[str, Any]) -> None:
    """Save the preprocessing manifest."""
    manifest_path = output_dir / MANIFEST_FILENAME
    manifest["last_updated"] = datetime.now().isoformat()
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    logger.info(f"Manifest saved: {len(manifest['processed'])} PDFs tracked")


def is_pdf_processed(manifest: dict[str, Any], pdf_path: Path) -> bool:
    """Check if a PDF has already been processed successfully."""
    pdf_key = str(pdf_path.name)
    entry = manifest.get("processed", {}).get(pdf_key)
    if not entry:
        return False
    # Check if processing completed successfully
    return entry.get("status") == "completed"


def mark_pdf_processed(
    manifest: dict[str, Any],
    pdf_path: Path,
    result: dict[str, Any],
) -> None:
    """Mark a PDF as processed in the manifest."""
    pdf_key = str(pdf_path.name)
    manifest.setdefault("processed", {})[pdf_key] = {
        "status": "completed" if not result.get("error") else "failed",
        "processed_at": datetime.now().isoformat(),
        "pages": result.get("pages", 0),
        "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0),
        "api_calls": result.get("api_calls", 0),
        "content_areas": result.get("content_areas", []),
        "output_files": result.get("output_files", []),
        "error": result.get("error"),
    }


def get_config() -> dict[str, Any]:
    """Load preprocessing config from config.json."""
    config_path = Path(__file__).parent.parent.parent / "config" / "config.json"

    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
            return config.get("preprocessing", {})

    return {}


def ensure_output_dirs(output_dir: Path) -> None:
    """Create output directory structure."""
    subdirs = [
        "section_1_foundations",
        "section_2_applications",
        "supplementary",
    ]

    for subdir in subdirs:
        (output_dir / subdir).mkdir(parents=True, exist_ok=True)


async def process_single_pdf(
    pdf_path: Path,
    output_dir: Path,
    processor: ContentProcessor,
    raw_extraction_dir: Path,
    skip_extraction: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    """
    Process a single PDF file through the pipeline.

    Returns dict with processing stats.
    """
    pdf_name = pdf_path.name
    logger.info(f"Processing: {pdf_name}")

    # Reset per-PDF token counters
    processor.reset_pdf_tokens()

    result = {
        "pdf": pdf_name,
        "pages": 0,
        "chars_extracted": 0,
        "chars_processed": 0,
        "content_areas": [],
        "output_files": [],
        "input_tokens": 0,
        "output_tokens": 0,
        "api_calls": 0,
        "error": None,
    }

    try:
        # Step 1: Extract PDF
        raw_json_path = raw_extraction_dir / f"{pdf_path.stem}.json"

        if skip_extraction and raw_json_path.exists():
            logger.info(f"Loading existing extraction from {raw_json_path}")
            pages = load_raw_extraction(raw_json_path)
        else:
            pages = extract_pdf(pdf_path)
            save_raw_extraction(pages, raw_json_path)

        result["pages"] = len(pages)

        # Step 2: Convert to text
        raw_text = pages_to_text(pages)
        result["chars_extracted"] = len(raw_text)

        if verbose:
            logger.info(
                f"  Extracted {len(pages)} pages, {len(raw_text)} chars, "
                f"~{estimate_tokens(raw_text)} tokens"
            )

        if dry_run:
            logger.info(f"  [DRY RUN] Would process {pdf_name}")
            return result

        if not raw_text.strip():
            logger.warning(f"  No text extracted from {pdf_name}")
            return result

        # Step 3: Check if this is a known supplementary document
        supp_path = get_document_output_path(pdf_name)

        if supp_path:
            # Process as supplementary document
            logger.info(f"  Processing as supplementary: {supp_path}")

            processed = await processor.process_chunks(raw_text, pdf_name)
            result["chars_processed"] = len(processed)

            output_path = output_dir / supp_path
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Append to existing file or create new
            _append_to_file(output_path, processed, pdf_name)
            result["output_files"].append(str(supp_path))

        else:
            # Process and classify by content area
            logger.info(f"  Processing and classifying content...")

            # Process in chunks
            processed = await processor.process_chunks(raw_text, pdf_name)
            result["chars_processed"] = len(processed)

            # Classify the content
            content_area = await processor.classify_content_area(processed)
            result["content_areas"].append(content_area)

            if verbose:
                logger.info(f"  Classified as: {content_area}")

            # Get output file path
            area_mapping = get_content_area_file_mapping()
            output_file = area_mapping.get(content_area)

            if output_file:
                output_path = output_dir / output_file
                output_path.parent.mkdir(parents=True, exist_ok=True)

                _append_to_file(output_path, processed, pdf_name)
                result["output_files"].append(output_file)

    except Exception as e:
        logger.error(f"Error processing {pdf_name}: {e}")
        result["error"] = str(e)

    # Capture token stats for this PDF
    pdf_tokens = processor.pdf_tokens
    result["input_tokens"] = pdf_tokens["input"]
    result["output_tokens"] = pdf_tokens["output"]
    result["api_calls"] = pdf_tokens["calls"]

    # Log PDF summary
    if pdf_tokens["calls"] > 0:
        logger.info(
            f"PDF complete: {pdf_name} | "
            f"{pdf_tokens['calls']} API calls | "
            f"{pdf_tokens['input']:,} input tokens | "
            f"{pdf_tokens['output']:,} output tokens"
        )

    return result


def _append_to_file(path: Path, content: str, source: str) -> None:
    """Append content to a file with source header."""
    header = f"\n\n---\n\n## Source: {source}\n\n"

    mode = "a" if path.exists() else "w"
    with open(path, mode, encoding="utf-8") as f:
        if mode == "a":
            f.write(header)
        else:
            f.write(f"# {path.stem.replace('_', ' ').title()}\n\n")
            f.write(f"*Generated: {datetime.now().isoformat()}*\n")
            f.write(header)
        f.write(content)


def generate_index(output_dir: Path) -> None:
    """Generate index.md with table of contents."""
    index_path = output_dir / "00_index.md"

    lines = [
        "# BCBA Study Content Index",
        "",
        f"*Generated: {datetime.now().isoformat()}*",
        "",
        "## Contents",
        "",
    ]

    # List all markdown files
    for md_file in sorted(output_dir.glob("**/*.md")):
        if md_file.name == "00_index.md":
            continue

        relative_path = md_file.relative_to(output_dir)
        name = md_file.stem.replace("_", " ").title()

        # Get file size for info
        size_kb = md_file.stat().st_size / 1024
        lines.append(f"- [{name}]({relative_path}) ({size_kb:.1f} KB)")

    lines.append("")

    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"Generated index: {index_path}")


def print_summary(results: list[dict[str, Any]], processor: ContentProcessor) -> None:
    """Print processing summary."""
    print("\n" + "=" * 60)
    print("PREPROCESSING SUMMARY")
    print("=" * 60)

    total_pages = sum(r["pages"] for r in results)
    total_chars = sum(r["chars_extracted"] for r in results)
    total_processed = sum(r["chars_processed"] for r in results)
    errors = [r for r in results if r.get("error")]

    print(f"\nDocuments processed: {len(results)}")
    print(f"Total pages: {total_pages}")
    print(f"Total characters extracted: {total_chars:,}")
    print(f"Total characters processed: {total_processed:,}")

    tokens = processor.total_tokens
    print(f"\nAPI Usage:")
    print(f"  Total API calls: {tokens['calls']:,}")
    print(f"  Input tokens: {tokens['input']:,}")
    print(f"  Output tokens: {tokens['output']:,}")

    # Per-PDF breakdown
    print("\nPer-PDF Token Usage:")
    for r in results:
        if r.get("api_calls", 0) > 0:
            print(
                f"  {r['pdf']}: "
                f"{r['api_calls']} calls, "
                f"{r['input_tokens']:,} in, "
                f"{r['output_tokens']:,} out"
            )

    # Estimate cost using Haiku pricing
    input_cost = tokens["input"] / 1_000_000 * 1.00
    output_cost = tokens["output"] / 1_000_000 * 5.00
    total_cost = input_cost + output_cost
    print(f"\nEstimated cost (Haiku 4.5): ${total_cost:.4f}")
    print(f"  Input: ${input_cost:.4f}")
    print(f"  Output: ${output_cost:.4f}")

    if errors:
        print(f"\nErrors: {len(errors)}")
        for e in errors:
            print(f"  - {e['pdf']}: {e['error']}")

    print("\n" + "=" * 60)


async def main(
    input_dir: Path,
    output_dir: Path,
    single_file: Path | None = None,
    skip_extraction: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
    force: bool = False,
) -> None:
    """Run the preprocessing pipeline."""
    # Load environment variables
    load_dotenv()

    # Get API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set in environment or .env file")
        sys.exit(1)

    # Load config
    config = get_config()

    # Setup directories
    ensure_output_dirs(output_dir)
    raw_extraction_dir = input_dir.parent / "raw_extractions"
    raw_extraction_dir.mkdir(parents=True, exist_ok=True)

    # Load manifest for resume support
    manifest = load_manifest(output_dir)
    already_processed = len([k for k, v in manifest.get("processed", {}).items()
                             if v.get("status") == "completed"])
    if already_processed > 0:
        logger.info(f"Manifest loaded: {already_processed} PDFs already processed")

    # Initialize processor
    processor = ContentProcessor(
        api_key=api_key,
        model=config.get("model", "claude-haiku-4-5-20250514"),
        max_tokens_per_chunk=config.get("max_tokens_per_chunk", 4000),
        delay_between_calls=config.get("delay_between_calls", 1.0),
    )

    # Discover PDFs
    if single_file:
        pdfs = [single_file]
    else:
        pdfs = discover_pdfs(input_dir)

    if not pdfs:
        print(f"No PDF files found in {input_dir}")
        sys.exit(1)

    # Filter out already-processed PDFs unless --force
    if not force and not single_file:
        pdfs_to_process = []
        skipped = []
        for pdf in pdfs:
            if is_pdf_processed(manifest, pdf):
                skipped.append(pdf.name)
            else:
                pdfs_to_process.append(pdf)

        if skipped:
            print(f"Skipping {len(skipped)} already-processed PDFs (use --force to reprocess)")
            if verbose:
                for name in skipped:
                    print(f"  - {name}")

        pdfs = pdfs_to_process

    if not pdfs:
        print("All PDFs already processed. Use --force to reprocess.")
        sys.exit(0)

    print(f"Found {len(pdfs)} PDF files to process")

    if dry_run:
        print("\n[DRY RUN MODE - No Claude API calls will be made]\n")

    # Process each PDF
    results = []
    rate_limit_stopped = False

    try:
        for i, pdf in enumerate(pdfs, start=1):
            print(f"\n[{i}/{len(pdfs)}] {pdf.name}")

            result = await process_single_pdf(
                pdf_path=pdf,
                output_dir=output_dir,
                processor=processor,
                raw_extraction_dir=raw_extraction_dir,
                skip_extraction=skip_extraction,
                dry_run=dry_run,
                verbose=verbose,
            )
            results.append(result)

            # Update manifest after each PDF (for resume support)
            if not dry_run:
                mark_pdf_processed(manifest, pdf, result)
                save_manifest(output_dir, manifest)

    except PersistentRateLimitError as e:
        rate_limit_stopped = True
        logger.error(str(e))
        print(f"\n{'=' * 60}")
        print("RATE LIMIT - STOPPING")
        print("=" * 60)
        print(f"\nProcessed {len(results)} PDFs before rate limit.")
        print(f"Remaining: {len(pdfs) - len(results)} PDFs")
        print("\nProgress saved. Resume with:")
        print(f"  python -m src.preprocessing.run_preprocessing")
        print("=" * 60)

        # Save manifest for any partial progress
        if not dry_run:
            save_manifest(output_dir, manifest)

    # Generate index
    if not dry_run:
        generate_index(output_dir)

    # Print summary
    print_summary(results, processor)

    if rate_limit_stopped:
        sys.exit(1)


def cli() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Preprocess BCBA study PDFs into structured markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all PDFs in data/raw/ (resumes from last run)
  python -m src.preprocessing.run_preprocessing

  # Process a single file with verbose output
  python -m src.preprocessing.run_preprocessing -f data/raw/bacb/Ethics-Code.pdf -v

  # Dry run to see what would be processed
  python -m src.preprocessing.run_preprocessing --dry-run

  # Skip extraction if JSON files already exist
  python -m src.preprocessing.run_preprocessing --skip-extraction

  # Force reprocess all PDFs (ignore manifest)
  python -m src.preprocessing.run_preprocessing --force
        """,
    )

    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=Path("data/raw"),
        help="Input directory with PDFs (default: data/raw/)",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("data/processed"),
        help="Output directory for markdown (default: data/processed/)",
    )

    parser.add_argument(
        "-f",
        "--file",
        type=Path,
        default=None,
        help="Process a single PDF file instead of directory",
    )

    parser.add_argument(
        "--skip-extraction",
        action="store_true",
        help="Use existing JSON extractions (skip pdfplumber)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without calling Claude API",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed progress",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess all PDFs, ignoring manifest of already-processed files",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level)

    # Validate inputs
    if args.file:
        if not args.file.exists():
            print(f"Error: File not found: {args.file}")
            sys.exit(1)
    else:
        if not args.input.exists():
            print(f"Error: Input directory not found: {args.input}")
            sys.exit(1)

    # Run pipeline
    asyncio.run(
        main(
            input_dir=args.input,
            output_dir=args.output,
            single_file=args.file,
            skip_extraction=args.skip_extraction,
            dry_run=args.dry_run,
            verbose=args.verbose,
            force=args.force,
        )
    )


if __name__ == "__main__":
    cli()

"""
CLI for running the PDF preprocessing pipeline.

Uses GPT 5.2's native PDF support for direct extraction and structuring.

Usage:
    python -m src.preprocessing.run_preprocessing --input data/raw/ --output data/processed/
    python -m src.preprocessing.run_preprocessing -f data/raw/bacb/Ethics-Code-for-Behavior-Analysts.pdf -v
"""

import argparse
import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.config.logging import get_logger, setup_logging
from src.preprocessing.pdf_processor import (
    PDFProcessor,
    PersistentRateLimitError,
    get_document_output_path,
)

logger = get_logger(__name__)


MANIFEST_FILENAME = "preprocessing_manifest.json"


def discover_pdfs(input_dir: Path) -> list[Path]:
    """Find all PDF files in input directory and subdirectories."""
    pdfs = list(input_dir.glob("**/*.pdf"))
    return sorted(pdfs)


def prompt_for_pdf(pdf_name: str, output_path: str | None, index: int, total: int) -> str:
    """
    Prompt user whether to process a PDF.

    Returns:
        'y' to process, 's' to skip, 'q' to quit, 'a' to process all remaining
    """
    if output_path:
        print(f"\n[{index}/{total}] {pdf_name}")
        print(f"  Output: {output_path}")
    else:
        print(f"\n[{index}/{total}] {pdf_name}")
        print("  Status: Will be skipped (not BCBA material)")

    while True:
        response = input("  Process? [Y]es / [s]kip / [a]ll remaining / [q]uit: ").strip().lower()
        if response in ("", "y", "yes"):
            return "y"
        elif response in ("s", "skip"):
            return "s"
        elif response in ("a", "all"):
            return "a"
        elif response in ("q", "quit"):
            return "q"
        else:
            print("  Invalid input. Enter y, s, a, or q.")


def validate_manifest(manifest_path: Path) -> bool:
    """Validate manifest file is readable and properly formatted.

    Returns:
        True if manifest is valid or doesn't exist, False if corrupt (backed up).
    """
    if not manifest_path.exists():
        return True  # No manifest = fresh start

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        # Check required fields
        if not isinstance(manifest.get("processed"), dict):
            logger.error("Invalid manifest: missing 'processed' dict")
            return False

        return True

    except json.JSONDecodeError as e:
        logger.error(f"Corrupt manifest file: {e}")
        # Backup and recreate
        backup = manifest_path.with_suffix(".json.bak")
        manifest_path.rename(backup)
        logger.info(f"Backed up corrupt manifest to {backup}")
        return True  # Will recreate fresh


def load_manifest(output_dir: Path) -> dict[str, Any]:
    """Load the preprocessing manifest tracking processed PDFs."""
    manifest_path = output_dir / MANIFEST_FILENAME

    # Validate before loading
    validate_manifest(manifest_path)

    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"processed": {}, "version": 2}


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
        "content_area": result.get("content_area"),
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
        "core",
        "ethics",
        "supervision",
        "reference",
    ]

    for subdir in subdirs:
        (output_dir / subdir).mkdir(parents=True, exist_ok=True)


async def process_single_pdf(
    pdf_path: Path,
    output_dir: Path,
    processor: PDFProcessor,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    """
    Process a single PDF file using GPT 5.2's native PDF support.

    Returns dict with processing stats.
    """
    pdf_name = pdf_path.name

    # Check if this document should be skipped
    output_path_rel = get_document_output_path(pdf_name)
    if output_path_rel is None:
        logger.info(f"Skipping {pdf_name} (not BCBA exam material)")
        return {"pdf": pdf_name, "status": "skipped", "reason": "not BCBA material"}

    logger.info(f"Processing: {pdf_name}")

    # Reset per-PDF token counters
    processor.reset_pdf_tokens()

    result = {
        "pdf": pdf_name,
        "pages": 0,
        "output_files": [],
        "input_tokens": 0,
        "output_tokens": 0,
        "api_calls": 0,
        "error": None,
    }

    if dry_run:
        # Just count pages for dry run
        from pypdf import PdfReader

        reader = PdfReader(pdf_path)
        result["pages"] = len(reader.pages)
        logger.info(f"  [DRY RUN] Would process {pdf_name} ({result['pages']} pages)")
        logger.info(f"  [DRY RUN] Would write to: {output_path_rel}")
        return result

    try:
        # Process PDF using GPT 5.2's native PDF support
        doc = await processor.process_pdf(pdf_path, verbose=verbose)

        result["pages"] = doc.page_count

        # Write to explicit output path (with deduplication)
        logger.info(f"  Writing to: {output_path_rel}")
        output_path = output_dir / output_path_rel
        output_path.parent.mkdir(parents=True, exist_ok=True)
        was_added = _append_to_file(output_path, doc.markdown, pdf_name)
        if was_added:
            result["output_files"].append(str(output_path_rel))
        else:
            result["status"] = "skipped"
            result["reason"] = "duplicate content"

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


def get_content_hash(content: str) -> str:
    """Generate hash of content for deduplication."""
    return hashlib.md5(content.encode()).hexdigest()[:12]


def _append_to_file(path: Path, content: str, source: str) -> bool:
    """Append content to a file with source header and deduplication.

    Returns:
        True if content was added, False if duplicate was skipped.
    """
    content_hash = get_content_hash(content)
    hash_marker = f"<!-- hash:{content_hash} -->"

    # Check for duplicate content
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if hash_marker in existing:
            logger.info(f"Skipping duplicate content from {source} (hash: {content_hash})")
            return False

    header = f"\n\n---\n\n{hash_marker}\n## Source: {source}\n\n"

    mode = "a" if path.exists() else "w"
    with open(path, mode, encoding="utf-8") as f:
        if mode == "a":
            f.write(header)
        else:
            f.write(f"# {path.stem.replace('_', ' ').title()}\n\n")
            f.write(f"*Generated: {datetime.now().isoformat()}*\n")
            f.write(header)
        f.write(content)

    return True


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


def print_summary(results: list[dict[str, Any]], processor: PDFProcessor) -> None:
    """Print processing summary."""
    print("\n" + "=" * 60)
    print("PREPROCESSING SUMMARY")
    print("=" * 60)

    total_pages = sum(r["pages"] for r in results)
    errors = [r for r in results if r.get("error")]

    print(f"\nDocuments processed: {len(results)}")
    print(f"Total pages: {total_pages}")

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

    # Estimate cost using GPT 5.2 pricing ($1.75/1M input, $14/1M output)
    input_cost = tokens["input"] / 1_000_000 * 1.75
    output_cost = tokens["output"] / 1_000_000 * 14.00
    total_cost = input_cost + output_cost
    print(f"\nEstimated cost (GPT 5.2): ${total_cost:.4f}")
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
    dry_run: bool = False,
    verbose: bool = False,
    force: bool = False,
    ask: bool = False,
) -> None:
    """Run the preprocessing pipeline."""
    # Load environment variables
    load_dotenv()

    # Get API key (OpenAI for GPT 5.2)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not set in environment or .env file")
        sys.exit(1)

    # Load config
    config = get_config()

    # Setup directories
    ensure_output_dirs(output_dir)

    # Load manifest for resume support
    manifest = load_manifest(output_dir)
    already_processed = len(
        [k for k, v in manifest.get("processed", {}).items() if v.get("status") == "completed"]
    )
    if already_processed > 0:
        logger.info(f"Manifest loaded: {already_processed} PDFs already processed")

    # Initialize processor with GPT 5.2's native PDF support
    processor = PDFProcessor(
        api_key=api_key,
        model=config.get("model", "gpt-5.2"),
        delay_between_calls=config.get("delay_between_calls", 1.0),
        max_tokens=config.get("max_tokens", 32768),
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
        print("\n[DRY RUN MODE - No GPT 5.2 API calls will be made]\n")

    if ask:
        print("\n[INTERACTIVE MODE - You will be prompted before each PDF]\n")

    # Process each PDF
    results = []
    rate_limit_stopped = False
    process_all = False  # Set to True when user selects 'all remaining'

    try:
        for i, pdf in enumerate(pdfs, start=1):
            # Interactive mode: prompt before processing
            if ask and not process_all:
                output_path = get_document_output_path(pdf.name)
                response = prompt_for_pdf(pdf.name, output_path, i, len(pdfs))

                if response == "q":
                    print("\nQuitting. Progress saved.")
                    break
                elif response == "s":
                    print("  Skipped by user")
                    results.append({"pdf": pdf.name, "status": "skipped", "reason": "user skipped"})
                    continue
                elif response == "a":
                    process_all = True
                    print("  Processing all remaining PDFs...")
                # response == "y" falls through to process

            if not ask:
                print(f"\n[{i}/{len(pdfs)}] {pdf.name}")

            result = await process_single_pdf(
                pdf_path=pdf,
                output_dir=output_dir,
                processor=processor,
                dry_run=dry_run,
                verbose=verbose,
            )
            results.append(result)

            # Update manifest after each PDF (for resume support)
            if not dry_run and result.get("status") != "skipped":
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
        print("  python -m src.preprocessing.run_preprocessing")
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
        description="Preprocess BCBA study PDFs into structured markdown using GPT 5.2's native PDF support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process PDFs interactively (prompts before each file)
  python -m src.preprocessing.run_preprocessing

  # Process all without prompts
  python -m src.preprocessing.run_preprocessing -y

  # Process a single file with verbose output
  python -m src.preprocessing.run_preprocessing -f data/raw/bacb/Ethics-Code.pdf -v

  # Dry run to see what would be processed
  python -m src.preprocessing.run_preprocessing --dry-run

  # Force reprocess all PDFs (ignore manifest)
  python -m src.preprocessing.run_preprocessing --force -y
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
        "--dry-run",
        action="store_true",
        help="Show what would be processed without calling GPT 5.2 API",
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

    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip prompts and process all PDFs without asking",
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
            dry_run=args.dry_run,
            verbose=args.verbose,
            force=args.force,
            ask=not args.yes,
        )
    )


if __name__ == "__main__":
    cli()

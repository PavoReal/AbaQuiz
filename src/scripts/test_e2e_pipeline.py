#!/usr/bin/env python3
"""
End-to-end pipeline test for AbaQuiz.

Interactive script to test the complete PDF-to-question pipeline:
1. Select a PDF from data/raw/
2. Preprocess PDF to markdown
3. Upload/sync to vector store
4. Generate questions using file_search
5. Display results

Usage:
    python -m src.scripts.test_e2e_pipeline
    python -m src.scripts.test_e2e_pipeline --verbose
"""

import argparse
import asyncio
import os
import random
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config.constants import ContentArea
from src.config.logging import get_logger, setup_logging
from src.preprocessing.pdf_processor import PDFProcessor, get_document_output_path
from src.services.question_generator import QuestionGenerator
from src.services.vector_store_manager import VectorStoreManager

logger = get_logger(__name__)


def discover_pdfs(raw_dir: Path) -> list[Path]:
    """Find all PDFs recursively in the raw data directory.

    Args:
        raw_dir: Directory to search for PDFs.

    Returns:
        List of Path objects for found PDFs, sorted by name.
    """
    pdfs = list(raw_dir.rglob("*.pdf"))
    return sorted(pdfs, key=lambda p: p.name.lower())


def select_pdf_interactive(pdfs: list[Path]) -> Path | None:
    """Display numbered list of PDFs and get user selection.

    Args:
        pdfs: List of PDF paths to choose from.

    Returns:
        Selected PDF path or None if cancelled.
    """
    if not pdfs:
        print("No PDFs found.")
        return None

    print("\nAvailable PDFs:")
    print("-" * 60)

    for i, pdf in enumerate(pdfs, 1):
        # Show relative path from data/raw/ for clarity
        try:
            rel_path = pdf.relative_to(project_root / "data" / "raw")
        except ValueError:
            rel_path = pdf.name

        size_kb = pdf.stat().st_size / 1024
        print(f"  {i:2d}. {rel_path} ({size_kb:.1f} KB)")

    print("-" * 60)
    print("Enter number to select, or 'q' to quit")

    while True:
        try:
            choice = input("\nSelection: ").strip()

            if choice.lower() == 'q':
                return None

            idx = int(choice) - 1
            if 0 <= idx < len(pdfs):
                return pdfs[idx]
            else:
                print(f"Please enter a number between 1 and {len(pdfs)}")

        except ValueError:
            print("Please enter a valid number or 'q' to quit")
        except KeyboardInterrupt:
            print("\nCancelled.")
            return None


async def step_preprocess(
    pdf_path: Path,
    output_dir: Path,
    verbose: bool = False
) -> Path | None:
    """Process PDF to markdown.

    Args:
        pdf_path: Path to the PDF file.
        output_dir: Directory to write markdown output.
        verbose: Whether to show detailed progress.

    Returns:
        Path to the generated markdown file, or None on failure.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("  ERROR: OPENAI_API_KEY not set")
        return None

    print(f"\n[Step 1/4] Preprocessing PDF")
    print(f"  Input:  {pdf_path.name}")

    # Determine output filename
    output_filename = get_document_output_path(pdf_path.name)
    output_path = output_dir / output_filename
    print(f"  Output: {output_filename}")

    # Check if already processed
    if output_path.exists():
        print(f"  Status: Already exists ({output_path.stat().st_size / 1024:.1f} KB)")
        reprocess = input("  Reprocess? [y/N] ").strip().lower()
        if reprocess != 'y':
            print("  Using existing markdown file.")
            return output_path

    try:
        processor = PDFProcessor(api_key=api_key)
        processor.reset_pdf_tokens()

        print("  Processing... (this may take a minute)")
        result = await processor.process_pdf(pdf_path, verbose=verbose)

        # Write output
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result.markdown, encoding="utf-8")

        print(f"  Done: {len(result.markdown):,} chars, {result.page_count} pages")
        print(f"  Tokens: {result.input_tokens:,} in / {result.output_tokens:,} out")

        return output_path

    except Exception as e:
        print(f"  ERROR: {e}")
        logger.exception("Preprocessing failed")
        return None


async def step_upload_to_vector_store(md_path: Path) -> bool:
    """Upload markdown to vector store (create if needed).

    Args:
        md_path: Path to the markdown file to upload.

    Returns:
        True if successful, False otherwise.
    """
    print(f"\n[Step 2/4] Uploading to Vector Store")
    print(f"  File: {md_path.name}")

    try:
        manager = VectorStoreManager()

        # Check if store exists, create if not
        store_id = await manager.get_store_id()
        if not store_id:
            print("  Creating new vector store...")
            store_id = await manager.create_store()
            print(f"  Created: {store_id}")
        else:
            print(f"  Using existing store: {store_id}")

        # Sync files (this will upload new/changed files)
        print("  Syncing files...")
        result = await manager.sync()

        if result.added:
            print(f"  Added: {', '.join(result.added)}")
        if result.removed:
            print(f"  Removed: {', '.join(result.removed)}")
        if result.unchanged:
            print(f"  Unchanged: {len(result.unchanged)} files")

        if result.errors:
            print(f"  Errors: {result.errors}")
            return False

        # Wait for indexing
        print("  Waiting 5 seconds for vector store indexing...")
        await asyncio.sleep(5)

        # Verify status
        status = await manager.get_status()
        if "store_file_counts" in status:
            counts = status["store_file_counts"]
            print(f"  Store status: {counts['completed']} ready, {counts['in_progress']} processing")

        print("  Upload complete!")
        return True

    except Exception as e:
        print(f"  ERROR: {e}")
        logger.exception("Upload failed")
        return False


async def step_generate_questions(count: int = 2) -> list[dict]:
    """Generate questions using file_search from vector store.

    Generates questions from different content areas for variety.

    Args:
        count: Number of questions to generate.

    Returns:
        List of generated question dictionaries.
    """
    print(f"\n[Step 3/4] Generating {count} Questions")

    try:
        generator = QuestionGenerator()

        # Clear any cached vector store ID to get fresh state
        generator.clear_vector_store_cache()

        # Select random content areas for variety
        all_areas = list(ContentArea)
        selected_areas = random.sample(all_areas, min(count, len(all_areas)))

        questions = []
        for i, area in enumerate(selected_areas, 1):
            print(f"  [{i}/{count}] Generating question for: {area.value}")

            question = await generator.generate_question(content_area=area)

            if question:
                questions.append(question)
                print(f"    Generated {question.get('type', 'unknown')} question")
            else:
                print(f"    Failed to generate question")

        print(f"  Generated {len(questions)}/{count} questions")
        return questions

    except Exception as e:
        print(f"  ERROR: {e}")
        logger.exception("Question generation failed")
        return []


def display_questions(questions: list[dict]) -> None:
    """Pretty-print generated questions.

    Args:
        questions: List of question dictionaries to display.
    """
    print(f"\n[Step 4/4] Generated Questions")
    print("=" * 70)

    if not questions:
        print("No questions to display.")
        return

    for i, q in enumerate(questions, 1):
        print(f"\nQuestion {i}: ({q.get('content_area', 'Unknown')})")
        print("-" * 70)

        # Question text
        print(f"\n{q.get('question', 'No question text')}\n")

        # Options
        options = q.get("options", {})
        for key in sorted(options.keys()):
            print(f"  {key}. {options[key]}")

        # Correct answer
        print(f"\nCorrect Answer: {q.get('correct_answer', 'Unknown')}")

        # Explanation
        explanation = q.get("explanation", "No explanation provided")
        print(f"\nExplanation:\n  {explanation}")

        # Source citation
        citation = q.get("source_citation")
        if citation:
            print(f"\nSource:")
            if citation.get("section"):
                print(f"  Section: {citation['section']}")
            if citation.get("heading"):
                print(f"  Heading: {citation['heading']}")
            if citation.get("quote"):
                print(f"  Quote: \"{citation['quote']}\"")

        # Metadata
        print(f"\nMetadata:")
        print(f"  Type: {q.get('type', 'unknown')}")
        print(f"  Category: {q.get('category', 'unknown')}")
        print(f"  Model: {q.get('model', 'unknown')}")

        print("\n" + "=" * 70)


async def run_e2e_test(verbose: bool = False) -> bool:
    """Run the complete E2E pipeline test.

    Args:
        verbose: Whether to show detailed progress.

    Returns:
        True if all steps succeeded, False otherwise.
    """
    print("\n" + "=" * 70)
    print("AbaQuiz E2E Pipeline Test")
    print("=" * 70)

    # Check for API key upfront
    if not os.getenv("OPENAI_API_KEY"):
        print("\nERROR: OPENAI_API_KEY environment variable not set.")
        print("Please set it before running this test.")
        return False

    # Discover PDFs
    raw_dir = project_root / "data" / "raw"
    output_dir = project_root / "data" / "processed"

    if not raw_dir.exists():
        print(f"\nERROR: Raw data directory not found: {raw_dir}")
        return False

    pdfs = discover_pdfs(raw_dir)
    if not pdfs:
        print(f"\nERROR: No PDFs found in {raw_dir}")
        return False

    print(f"\nFound {len(pdfs)} PDF(s) in {raw_dir}")

    # Select PDF
    selected_pdf = select_pdf_interactive(pdfs)
    if not selected_pdf:
        print("\nNo PDF selected. Exiting.")
        return False

    print(f"\nSelected: {selected_pdf.name}")

    # Step 1: Preprocess
    md_path = await step_preprocess(selected_pdf, output_dir, verbose=verbose)
    if not md_path:
        print("\nPreprocessing failed. Stopping.")
        return False

    # Step 2: Upload to vector store
    if not await step_upload_to_vector_store(md_path):
        print("\nVector store upload failed. Stopping.")
        return False

    # Step 3: Generate questions
    questions = await step_generate_questions(count=2)
    if not questions:
        print("\nQuestion generation failed. Stopping.")
        return False

    # Step 4: Display results
    display_questions(questions)

    print("\nE2E Pipeline Test Complete!")
    return True


def main() -> int:
    """CLI entry point.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    parser = argparse.ArgumentParser(
        description="Test the complete PDF-to-question pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script tests the full pipeline:
  1. Select a PDF from data/raw/
  2. Preprocess it to markdown
  3. Upload to OpenAI vector store
  4. Generate questions using file_search
  5. Display the results

Examples:
  %(prog)s              # Run interactive test
  %(prog)s --verbose    # Run with detailed logging
""",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed progress and debug output",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level)

    try:
        success = asyncio.run(run_e2e_test(verbose=args.verbose))
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        return 1
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        logger.exception("E2E test failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

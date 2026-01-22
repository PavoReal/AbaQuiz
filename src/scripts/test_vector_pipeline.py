"""
Test script for the vector store pipeline.

Tests:
1. Creating/verifying vector store setup
2. Uploading content files
3. Generating 3 questions using file_search

Usage:
    .venv/bin/python -m src.scripts.test_vector_pipeline
"""

import asyncio
import json
import sys
from datetime import datetime

from src.config.constants import ContentArea
from src.config.logging import get_logger
from src.services.vector_store_manager import get_vector_store_manager
from src.services.question_generator import get_question_generator

logger = get_logger(__name__)


async def test_vector_store_setup() -> bool:
    """Test vector store creation and file upload."""
    print("\n" + "=" * 60)
    print("STEP 1: Vector Store Setup")
    print("=" * 60)

    manager = get_vector_store_manager()
    status = await manager.get_status()

    if status.get("configured"):
        print(f"✓ Vector store already configured: {status.get('store_id')}")
        print(f"  Created: {status.get('created_at')}")
        print(f"  Last sync: {status.get('last_sync')}")
        print(f"  Files tracked: {status.get('tracked_files', 0)}")

        # Check if we need to sync
        local_files = status.get("local_files", 0)
        tracked_files = status.get("tracked_files", 0)

        if local_files != tracked_files:
            print(f"\n  Local files ({local_files}) != tracked ({tracked_files})")
            print("  Running sync...")
            result = await manager.sync()
            print(f"  Sync complete: +{len(result.added)} -{len(result.removed)} ={len(result.unchanged)}")

        return True

    print("Vector store not configured. Creating...")

    # Create store
    try:
        store_id = await manager.create_store()
        print(f"✓ Created vector store: {store_id}")
    except Exception as e:
        print(f"✗ Failed to create store: {e}")
        return False

    # Upload files
    try:
        print("\nUploading content files...")
        uploaded_ids = await manager.upload_files()
        print(f"✓ Uploaded {len(uploaded_ids)} files")
    except Exception as e:
        print(f"✗ Failed to upload files: {e}")
        return False

    return True


async def test_question_generation(count: int = 3) -> list[dict]:
    """Test generating questions using file_search."""
    print("\n" + "=" * 60)
    print(f"STEP 2: Generate {count} Questions")
    print("=" * 60)

    generator = get_question_generator()
    questions = []

    # Test different content areas
    test_areas = [
        ContentArea.ETHICS,
        ContentArea.BEHAVIOR_CHANGE_PROCEDURES,
        ContentArea.MEASUREMENT,
    ]

    for i, area in enumerate(test_areas[:count]):
        print(f"\n[{i+1}/{count}] Generating {area.value} question...")

        try:
            question = await generator.generate_question(area)

            if question:
                questions.append(question)
                print(f"✓ Generated question:")
                print(f"  Type: {question.get('type')}")
                print(f"  Category: {question.get('category')}")
                print(f"  Question: {question.get('question', '')[:100]}...")
                print(f"  Correct: {question.get('correct_answer')}")
            else:
                print(f"✗ Generation returned None")

        except Exception as e:
            print(f"✗ Error generating question: {e}")
            logger.exception("Question generation failed")

    return questions


def display_questions(questions: list[dict]) -> None:
    """Display generated questions in detail."""
    print("\n" + "=" * 60)
    print("GENERATED QUESTIONS")
    print("=" * 60)

    for i, q in enumerate(questions, 1):
        print(f"\n--- Question {i} ---")
        print(f"Content Area: {q.get('content_area')}")
        print(f"Category: {q.get('category')}")
        print(f"Type: {q.get('type')}")
        print(f"\nQ: {q.get('question')}")

        options = q.get("options", {})
        print("\nOptions:")
        for key in ["A", "B", "C", "D", "True", "False"]:
            if key in options and options[key]:
                marker = "→" if key == q.get("correct_answer") else " "
                print(f"  {marker} {key}: {options[key]}")

        print(f"\nCorrect Answer: {q.get('correct_answer')}")
        print(f"\nExplanation: {q.get('explanation')}")

        citation = q.get("source_citation")
        if citation:
            print(f"\nSource: {citation.get('section', 'N/A')} - {citation.get('heading', 'N/A')}")


async def main():
    """Run the vector store pipeline test."""
    print("\n" + "=" * 60)
    print("VECTOR STORE PIPELINE TEST")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 60)

    # Step 1: Setup vector store
    if not await test_vector_store_setup():
        print("\n✗ Vector store setup failed. Aborting.")
        sys.exit(1)

    # Wait for vector store to be ready
    print("\nWaiting for vector store to process files...")
    await asyncio.sleep(5)

    # Step 2: Generate questions
    questions = await test_question_generation(count=3)

    # Step 3: Display results
    if questions:
        display_questions(questions)

        # Save to file
        output_file = "data/test_questions_output.json"
        with open(output_file, "w") as f:
            json.dump(questions, f, indent=2)
        print(f"\n✓ Questions saved to {output_file}")

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Vector Store: ✓ Ready")
    print(f"Questions Generated: {len(questions)}/3")
    print(f"Success Rate: {len(questions)/3*100:.0f}%")

    if len(questions) == 3:
        print("\n✓ Pipeline test PASSED")
        return 0
    else:
        print(f"\n⚠ Pipeline test completed with {3-len(questions)} failures")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

"""
Embedding-based deduplication service using OpenAI embeddings.

Uses cosine similarity between embeddings to detect duplicate questions.
Much faster and cheaper than LLM-based deduplication.
"""

import asyncio
import math
from dataclasses import dataclass
from typing import Any, Optional

from openai import AsyncOpenAI

from src.config.logging import get_logger
from src.config.settings import get_settings

logger = get_logger(__name__)


@dataclass
class DedupResult:
    """Result of a deduplication check."""

    is_duplicate: bool
    similarity: float
    matched_index: Optional[int] = None
    matched_question: Optional[str] = None


class EmbeddingDedupService:
    """Deduplication using embedding cosine similarity."""

    EMBEDDING_MODEL = "text-embedding-3-large"
    DEFAULT_THRESHOLD = 0.85

    def __init__(self, threshold: Optional[float] = None) -> None:
        self.settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=self.settings.openai_api_key,
            max_retries=3,
        )
        self.threshold = threshold or self.DEFAULT_THRESHOLD
        # Cache embeddings to avoid redundant API calls
        self._embedding_cache: dict[str, list[float]] = {}
        # Semaphore for rate limiting
        self._semaphore = asyncio.Semaphore(50)

    def _format_question_text(self, question: dict[str, Any]) -> str:
        """Format a question dict into text for embedding.

        Combines question text and options for better similarity detection.
        """
        q_text = question.get("question", question.get("content", ""))
        options = question.get("options", {})
        options_text = " ".join(f"{k}: {v}" for k, v in options.items() if v)
        return f"{q_text} {options_text}"

    async def get_embedding(self, text: str) -> list[float]:
        """Get embedding vector for text.

        Uses caching to avoid redundant API calls for the same text.
        """
        # Check cache
        cache_key = text[:500]  # Use truncated text as cache key
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]

        async with self._semaphore:
            response = await self.client.embeddings.create(
                model=self.EMBEDDING_MODEL,
                input=text,
            )

        embedding = response.data[0].embedding

        # Cache the result
        self._embedding_cache[cache_key] = embedding
        return embedding

    async def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings for multiple texts in a single API call.

        More efficient than individual calls for batches.
        """
        if not texts:
            return []

        # Check cache for already computed embeddings
        cached_results: dict[int, list[float]] = {}
        texts_to_embed: list[tuple[int, str]] = []

        for i, text in enumerate(texts):
            cache_key = text[:500]
            if cache_key in self._embedding_cache:
                cached_results[i] = self._embedding_cache[cache_key]
            else:
                texts_to_embed.append((i, text))

        # Get embeddings for uncached texts
        if texts_to_embed:
            async with self._semaphore:
                response = await self.client.embeddings.create(
                    model=self.EMBEDDING_MODEL,
                    input=[text for _, text in texts_to_embed],
                )

            # Store results and cache them
            for (idx, text), emb_data in zip(texts_to_embed, response.data):
                embedding = emb_data.embedding
                cached_results[idx] = embedding
                cache_key = text[:500]
                self._embedding_cache[cache_key] = embedding

        # Reconstruct results in order
        return [cached_results[i] for i in range(len(texts))]

    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    async def check_duplicate(
        self,
        new_question: dict[str, Any],
        existing_questions: list[dict[str, Any]],
        threshold: Optional[float] = None,
    ) -> DedupResult:
        """Check if new question is duplicate of any existing question.

        Args:
            new_question: The new question to check
            existing_questions: List of existing questions to check against
            threshold: Similarity threshold (default: self.threshold)

        Returns:
            DedupResult with is_duplicate flag and similarity info
        """
        if not existing_questions:
            return DedupResult(is_duplicate=False, similarity=0.0)

        threshold = threshold or self.threshold

        # Format new question
        new_text = self._format_question_text(new_question)

        # Format existing questions
        existing_texts = [self._format_question_text(q) for q in existing_questions]

        try:
            # Get embeddings (new question + existing in batch)
            all_texts = [new_text] + existing_texts
            embeddings = await self.get_embeddings_batch(all_texts)

            new_embedding = embeddings[0]
            existing_embeddings = embeddings[1:]

            # Find maximum similarity
            max_similarity = 0.0
            max_idx = -1

            for i, existing_emb in enumerate(existing_embeddings):
                similarity = self.cosine_similarity(new_embedding, existing_emb)
                if similarity > max_similarity:
                    max_similarity = similarity
                    max_idx = i

            is_duplicate = max_similarity >= threshold

            if is_duplicate:
                matched_q = existing_questions[max_idx].get(
                    "question", existing_questions[max_idx].get("content", "")
                )
                logger.debug(
                    f"Duplicate found (similarity={max_similarity:.3f}): {matched_q[:50]}..."
                )
                return DedupResult(
                    is_duplicate=True,
                    similarity=max_similarity,
                    matched_index=max_idx,
                    matched_question=matched_q,
                )

            return DedupResult(
                is_duplicate=False,
                similarity=max_similarity,
            )

        except Exception as e:
            logger.warning(f"Dedup check failed, allowing question: {e}")
            return DedupResult(is_duplicate=False, similarity=0.0)

    async def check_duplicates_batch(
        self,
        new_questions: list[dict[str, Any]],
        existing_questions: list[dict[str, Any]],
        threshold: Optional[float] = None,
    ) -> list[DedupResult]:
        """Check multiple new questions for duplicates.

        More efficient than checking one at a time when you have multiple
        new questions to validate.

        Args:
            new_questions: List of new questions to check
            existing_questions: List of existing questions to check against
            threshold: Similarity threshold (default: self.threshold)

        Returns:
            List of DedupResult, one per new question
        """
        if not new_questions:
            return []

        if not existing_questions:
            return [DedupResult(is_duplicate=False, similarity=0.0) for _ in new_questions]

        threshold = threshold or self.threshold

        # Format all questions
        new_texts = [self._format_question_text(q) for q in new_questions]
        existing_texts = [self._format_question_text(q) for q in existing_questions]

        try:
            # Get all embeddings in batch
            all_texts = new_texts + existing_texts
            embeddings = await self.get_embeddings_batch(all_texts)

            new_embeddings = embeddings[: len(new_texts)]
            existing_embeddings = embeddings[len(new_texts) :]

            # Check each new question
            results = []
            for i, new_emb in enumerate(new_embeddings):
                max_similarity = 0.0
                max_idx = -1

                for j, existing_emb in enumerate(existing_embeddings):
                    similarity = self.cosine_similarity(new_emb, existing_emb)
                    if similarity > max_similarity:
                        max_similarity = similarity
                        max_idx = j

                is_duplicate = max_similarity >= threshold

                if is_duplicate:
                    matched_q = existing_questions[max_idx].get(
                        "question", existing_questions[max_idx].get("content", "")
                    )
                    results.append(
                        DedupResult(
                            is_duplicate=True,
                            similarity=max_similarity,
                            matched_index=max_idx,
                            matched_question=matched_q,
                        )
                    )
                else:
                    results.append(
                        DedupResult(
                            is_duplicate=False,
                            similarity=max_similarity,
                        )
                    )

            return results

        except Exception as e:
            logger.warning(f"Batch dedup check failed, allowing all questions: {e}")
            return [DedupResult(is_duplicate=False, similarity=0.0) for _ in new_questions]

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._embedding_cache.clear()
        logger.debug("Embedding cache cleared")


# Singleton instance
_dedup_service: Optional[EmbeddingDedupService] = None


def get_dedup_service() -> EmbeddingDedupService:
    """Get or create the deduplication service instance."""
    global _dedup_service
    if _dedup_service is None:
        _dedup_service = EmbeddingDedupService()
    return _dedup_service

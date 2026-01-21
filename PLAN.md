# Implementation Plan: OpenAI File Search API Migration

## Overview

Migrate from local file loading + Claude to OpenAI File Search API + GPT-5.2 exclusively. Remove all Anthropic dependencies.

---

## Phase 1: Vector Store Infrastructure

### 1.1 Create Vector Store Manager Module

**File:** `src/services/vector_store_manager.py`

```python
class VectorStoreManager:
    """Manages OpenAI vector store for BCBA content."""

    def __init__(self):
        self.client = AsyncOpenAI()
        self.state_file = Path("data/.vector_store_state.json")

    async def create_store(self, name: str) -> str:
        """Create new vector store, return ID."""

    async def upload_files(self, directory: Path) -> list[str]:
        """Upload all .md files from directory to vector store."""

    async def sync(self) -> SyncResult:
        """Detect new/changed files, upload them, remove deleted."""

    async def get_store_id(self) -> str | None:
        """Load store ID from state file."""

    async def list_files(self) -> list[FileInfo]:
        """List all files in vector store with metadata."""

    async def delete_store(self) -> None:
        """Delete vector store and clear state."""
```

### 1.2 Create CLI Script

**File:** `src/scripts/manage_vector_store.py`

Commands:
```bash
# Create new vector store and upload all files
python -m src.scripts.manage_vector_store create

# Sync files (upload new, remove deleted)
python -m src.scripts.manage_vector_store sync

# List files in vector store
python -m src.scripts.manage_vector_store list

# Show vector store status
python -m src.scripts.manage_vector_store status

# Delete vector store
python -m src.scripts.manage_vector_store delete
```

### 1.3 State File Format

**File:** `data/.vector_store_state.json`

```json
{
  "vector_store_id": "vs_abc123",
  "created_at": "2026-01-20T10:00:00Z",
  "last_sync": "2026-01-20T10:00:00Z",
  "files": {
    "BCBA-Handbook.md": {
      "file_id": "file_xyz789",
      "uploaded_at": "2026-01-20T10:00:00Z",
      "size_bytes": 241664,
      "checksum": "sha256:abc..."
    }
  }
}
```

---

## Phase 2: Question Generator Migration

### 2.1 Update Question Generator

**File:** `src/services/question_generator.py`

Changes:
1. Remove `_load_content_for_area()` method
2. Remove `_content_cache`
3. Remove local file path logic
4. Add vector store ID loading from state file
5. Switch to Responses API with `file_search` tool

### 2.2 Content Area Query Mapping

Replace hardcoded file mappings with semantic queries:

```python
CONTENT_AREA_QUERIES: dict[ContentArea, str] = {
    ContentArea.ETHICS: "BACB ethics code professional conduct multiple relationships confidentiality",
    ContentArea.BEHAVIOR_ASSESSMENT: "functional behavior assessment FBA indirect direct assessment preference assessment",
    ContentArea.BEHAVIOR_CHANGE_PROCEDURES: "reinforcement punishment extinction differential reinforcement shaping chaining prompting",
    ContentArea.CONCEPTS_AND_PRINCIPLES: "operant respondent conditioning stimulus control verbal behavior motivating operations",
    ContentArea.MEASUREMENT: "data collection frequency rate duration latency IOA graphing visual analysis",
    ContentArea.EXPERIMENTAL_DESIGN: "single subject design reversal multiple baseline alternating treatment changing criterion",
    ContentArea.INTERVENTIONS: "evidence-based practice treatment integrity social validity intervention selection",
    ContentArea.SUPERVISION: "RBT supervision feedback performance monitoring training competency assessment",
    ContentArea.PHILOSOPHICAL_UNDERPINNINGS: "radical behaviorism determinism selectionism parsimony pragmatism",
}
```

### 2.3 New Generation Flow

```python
async def generate_question(self, content_area: ContentArea) -> dict:
    # Get vector store ID
    store_id = await self.vector_store_manager.get_store_id()
    if not store_id:
        raise RuntimeError("Vector store not configured. Run: python -m src.scripts.manage_vector_store create")

    # Build query with content area guidance
    query = CONTENT_AREA_QUERIES[content_area]

    # Use Responses API with file_search
    response = await self.client.responses.create(
        model="gpt-5.2",
        input=f"Generate a BCBA exam question about {content_area.value}. Focus on: {query}",
        tools=[{
            "type": "file_search",
            "vector_store_ids": [store_id],
        }],
        # ... rest of config
    )
```

---

## Phase 3: Deduplication Migration

### 3.1 Create Embedding-Based Dedup Service

**File:** `src/services/dedup_service.py`

```python
class EmbeddingDedupService:
    """Deduplication using embedding cosine similarity."""

    EMBEDDING_MODEL = "text-embedding-3-large"
    DEFAULT_THRESHOLD = 0.85

    async def get_embedding(self, text: str) -> list[float]:
        """Get embedding vector for text."""

    async def check_duplicate(
        self,
        new_question: str,
        existing_questions: list[str],
        threshold: float = DEFAULT_THRESHOLD
    ) -> DedupResult:
        """Check if new question is duplicate of any existing."""

    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
```

### 3.2 Update Pool Manager

**File:** `src/services/pool_manager.py`

Changes:
1. Remove Claude Haiku dedup calls
2. Import and use `EmbeddingDedupService`
3. Update config references from `dedup_model` to `dedup_threshold`

### 3.3 Config Changes

**File:** `config/config.json`

```json
{
  "pool_management": {
    "dedup_threshold": 0.85,
    "dedup_embedding_model": "text-embedding-3-large",
    // Remove: "dedup_model": "claude-haiku-4-5"
  }
}
```

---

## Phase 4: User Response Migration

### 4.1 Identify Claude Usage for User Responses

Search for Anthropic client usage in:
- `src/bot/handlers.py`
- `src/bot/callback_handlers.py`
- Any other user-facing response generation

### 4.2 Replace with OpenAI

Update all user response generation to use GPT-5.2 via AsyncOpenAI client.

---

## Phase 5: Remove Anthropic Dependencies

### 5.1 Remove SDK

```bash
# Remove from requirements
pip uninstall anthropic

# Update requirements.txt / pyproject.toml
```

### 5.2 Remove Imports

Search and remove all:
```python
import anthropic
from anthropic import ...
```

### 5.3 Remove Config

**File:** `config/config.json`

Remove entire `pricing.anthropic` section:
```json
{
  "pricing": {
    // Remove anthropic section
    "openai": { ... }
  }
}
```

### 5.4 Remove Environment Variable

**File:** `.env`

Remove: `ANTHROPIC_API_KEY=...`

### 5.5 Update Settings

**File:** `src/config/settings.py`

Remove `anthropic_api_key` field and validation.

---

## Phase 6: Content Validator Update

### 6.1 Update Validator

**File:** `src/services/content_validator.py`

Changes:
1. Remove local file validation (no longer relevant)
2. Add vector store validation:
   - Check if vector store exists
   - Verify files are uploaded
   - Check file count matches local directory

```python
async def validate_vector_store() -> ValidationResult:
    """Validate vector store is configured and populated."""
```

### 6.2 Update Startup Validation

**File:** `src/main.py`

Replace `validate_content_on_startup()` with `validate_vector_store()`.

---

## Phase 7: Documentation & Cleanup

### 7.1 Update CLAUDE.md

- Update tech stack section
- Update commands section (add vector store CLI)
- Remove Claude/Anthropic references
- Update pricing section

### 7.2 Update docs/

- `docs/CLI_TOOLS.md` - Add vector store commands
- `docs/preprocessing_guide.md` - Update for vector store workflow

### 7.3 Add .gitignore Entry

```
data/.vector_store_state.json
```

---

## File Change Summary

| File | Action |
|------|--------|
| `src/services/vector_store_manager.py` | **Create** |
| `src/services/dedup_service.py` | **Create** |
| `src/scripts/manage_vector_store.py` | **Create** |
| `src/services/question_generator.py` | **Modify** - Remove local files, add file_search |
| `src/services/pool_manager.py` | **Modify** - Use embedding dedup |
| `src/services/content_validator.py` | **Modify** - Validate vector store |
| `src/bot/handlers.py` | **Modify** - Replace Claude with GPT-5.2 |
| `src/config/settings.py` | **Modify** - Remove Anthropic config |
| `config/config.json` | **Modify** - Remove Anthropic pricing, add dedup config |
| `requirements.txt` | **Modify** - Remove anthropic |
| `CLAUDE.md` | **Modify** - Update documentation |
| `.env` | **Modify** - Remove ANTHROPIC_API_KEY |
| `data/.vector_store_state.json` | **Create** (at runtime) |

---

## Testing Plan

1. **Unit Tests**
   - `tests/test_vector_store_manager.py` - Mock OpenAI API
   - `tests/test_dedup_service.py` - Test cosine similarity, threshold logic

2. **Integration Tests**
   - Create test vector store with sample files
   - Generate questions using file search
   - Verify dedup catches similar questions

3. **Manual Testing**
   - Run full CLI workflow: create → sync → status → list
   - Generate batch of questions
   - Verify no Anthropic API calls in logs

---

## Rollout Steps

1. Create feature branch
2. Implement Phase 1 (Vector Store Infrastructure)
3. Test CLI commands manually
4. Implement Phase 2 (Question Generator)
5. Implement Phase 3 (Deduplication)
6. Implement Phase 4 (User Responses)
7. Implement Phase 5 (Remove Anthropic)
8. Implement Phase 6 (Validator)
9. Run full test suite
10. Update documentation (Phase 7)
11. Create PR for review

---

## Cost Impact

| Component | Before | After |
|-----------|--------|-------|
| Question Generation | GPT-5.2 + ~25K input tokens | GPT-5.2 + ~16K retrieved tokens |
| User Responses | Claude Sonnet ($3/$15 per 1M) | GPT-5.2 ($1.75/$14 per 1M) |
| Deduplication | Claude Haiku ($1/$5 per 1M) | Embeddings ($0.13 per 1M) |
| Storage | $0 | $0 (under 1GB free tier) |

**Estimated savings:** 30-50% reduction in API costs

# Feature 1: Question Seeding and Deduplication Improvements

## Problem Summary

The seed script spent $30+ USD without completing because:
1. **1 API call per question** - 250 questions = 250 Sonnet calls
2. **Every question triggers multiple Haiku dedup calls** - 10 calls per question
3. **No confidence filtering** - even "low" confidence duplicates rejected
4. **No early exit** - checks all batches even when unnecessary
5. **Manual JSON parsing** - fragile, can fail on malformed output

## Solution Overview

| Optimization | Before | After | Impact |
|--------------|--------|-------|--------|
| Batch generation | 1 question/call | 5 questions/call | 80% fewer Sonnet calls |
| Structured outputs | Manual JSON parse | Guaranteed valid JSON | No parse failures |
| Dedup check limit | 50 questions | 30 questions | 40% fewer Haiku calls |
| Confidence filter | All rejected | High only | Fewer wasted generations |
| Early exit | None | After 3 clean batches | ~50% fewer Haiku calls |
| Skip-dedup flag | N/A | Available | 100% dedup savings on empty pool |

**Estimated cost for 250 questions:**
- Before: $30+ (with high rejection)
- After (normal): ~$2.50
- After (--skip-dedup): ~$1.50

---

## Implementation Plan

### Phase 1: Batch Question Generation with Structured Outputs (question_generator.py)

#### 1.1 Pydantic Models for Type-Safe Output

Define schema using Pydantic - Claude's structured outputs will guarantee valid JSON:

```python
from pydantic import BaseModel, Field
from typing import Literal

class GeneratedQuestion(BaseModel):
    """A single generated quiz question."""
    question: str = Field(description="The question text")
    type: Literal["multiple_choice", "true_false"] = Field(description="Question type")
    options: dict[str, str] = Field(description="Answer options (A/B/C/D or True/False)")
    correct_answer: str = Field(description="The correct answer key")
    explanation: str = Field(description="Why the answer is correct and others wrong")

class QuestionBatch(BaseModel):
    """Batch of generated questions."""
    questions: list[GeneratedQuestion] = Field(description="List of generated questions")
```

#### 1.2 Batch Generation with Structured Outputs

Use the `structured-outputs-2025-11-13` beta for guaranteed valid JSON:

```python
# Updated system prompt (no JSON formatting instructions needed - schema handles it)
BATCH_SYSTEM_PROMPT = """You are an expert BCBA exam question writer creating practice questions based on the BCBA 5th Edition Task List.

Guidelines:
1. All options should be plausible to someone who hasn't mastered the content
2. Avoid "all of the above" or "none of the above" options
3. Explanations should teach the concept and explain why correct/incorrect
4. Match BCBA certification exam difficulty and style
5. Reference specific ethics codes, task list items where relevant
6. Use diverse names, settings, demographics in scenarios

Requirements for variety in each batch:
- Mix categories: ~40% scenario-based, ~30% definition, ~30% application
- Each question must test a DIFFERENT concept
- Vary difficulty levels"""

async def generate_question_batch(
    self,
    content_area: ContentArea,
    count: int = 5,
) -> list[dict[str, Any]]:
    """Generate multiple questions in a single API call using structured outputs."""
    content = self._load_content_for_area(content_area)

    user_prompt = f"""Generate exactly {count} BCBA exam questions about {content_area.value}.

CONTENT AREA GUIDANCE:
{CONTENT_AREA_GUIDANCE.get(content_area, "")}

STUDY CONTENT:
{content if content else f"Use your knowledge of {content_area.value} from the BCBA Task List."}

Generate {count} diverse questions testing different concepts within this area."""

    # Use structured outputs beta - guarantees valid JSON matching schema
    response = self.client.beta.messages.create(
        model=self.settings.claude_model,
        max_tokens=4096,
        betas=["structured-outputs-2025-11-13"],
        system=BATCH_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        output_format={
            "type": "json_schema",
            "schema": QuestionBatch.model_json_schema(),
        },
    )

    # Guaranteed valid JSON - just parse it
    data = json.loads(response.content[0].text)
    questions = data["questions"]

    # Add metadata
    for q in questions:
        q["content_area"] = content_area.value

    logger.info(
        f"Generated {len(questions)} questions for {content_area.value}: "
        f"{response.usage.input_tokens} in, {response.usage.output_tokens} out"
    )

    return questions
```

#### 1.3 No Manual JSON Parsing Needed

With structured outputs, we get **guaranteed valid JSON** matching our Pydantic schema:
- No `json.JSONDecodeError` handling needed
- No regex extraction fallbacks
- No field validation - schema enforces required fields and types
- No retries for malformed output

**Note:** First request per schema has ~1s latency for grammar compilation (cached 24h after).

---

### Phase 2: Update Pool Manager (pool_manager.py)

#### 2.1 Use Batch Generation

```python
async def generate_with_dedup(
    self,
    content_area: ContentArea,
    count: int,
) -> list[dict[str, Any]]:
    """Generate questions with deduplication, using batch generation."""
    generator = get_question_generator()
    repo = await get_repository(self.settings.database_path)

    existing_questions = await repo.get_questions_by_content_area(
        content_area.value, limit=self.DEDUP_CHECK_LIMIT
    )

    unique_questions: list[dict[str, Any]] = []
    batch_size = 5
    max_batches = (count * 2) // batch_size  # Allow for rejections

    for batch_num in range(max_batches):
        if len(unique_questions) >= count:
            break

        # Generate batch of 5
        batch = await generator.generate_question_batch(
            content_area=content_area,
            count=batch_size,
        )

        # Check each for duplicates
        for question in batch:
            if len(unique_questions) >= count:
                break

            is_dup = await self.check_duplicate(
                question,
                existing_questions + unique_questions
            )

            if not is_dup:
                unique_questions.append(question)

    return unique_questions
```

#### 2.2 Confidence-Based Duplicate Rejection

```python
# Config
self.dedup_confidence_threshold = pool_config.get("dedup_confidence_threshold", "high")

async def check_duplicate(self, new_question, existing_questions) -> bool:
    # ... batch checking logic ...

    if result and result.get("is_duplicate"):
        confidence = result.get("confidence", "high")

        # Only reject high confidence
        if confidence == "high" or (
            confidence == "medium" and self.dedup_confidence_threshold != "high"
        ):
            logger.debug(f"Duplicate rejected ({confidence}): {result.get('reason')}")
            return True
        else:
            logger.debug(f"Duplicate skipped ({confidence} < threshold)")
            return False

    return False
```

#### 2.3 Early Exit Optimization

```python
self.dedup_early_exit_batches = pool_config.get("dedup_early_exit_batches", 3)

async def check_duplicate(self, new_question, existing_questions) -> bool:
    if not existing_questions:
        return False

    consecutive_clean = 0
    batch_size = 5

    for i in range(0, len(existing_questions), batch_size):
        batch = existing_questions[i:i + batch_size]

        # ... check batch ...

        if not is_duplicate_in_batch:
            consecutive_clean += 1
            if consecutive_clean >= self.dedup_early_exit_batches:
                return False  # Early exit
        else:
            consecutive_clean = 0
            if is_high_confidence_duplicate:
                return True

    return False
```

#### 2.4 Reduce Check Limit

```python
DEDUP_CHECK_LIMIT = 30  # Down from 50
```

#### 2.5 Skip-Dedup Generation

```python
async def generate_without_dedup(
    self,
    content_area: ContentArea,
    count: int,
) -> list[dict[str, Any]]:
    """Generate questions without dedup checks (for initial seeding)."""
    generator = get_question_generator()
    questions = []
    batch_size = 5

    for _ in range(0, count, batch_size):
        needed = min(batch_size, count - len(questions))
        batch = await generator.generate_question_batch(content_area, needed)
        questions.extend(batch)

    return questions[:count]
```

---

### Phase 3: Update Seed Script (seed_questions.py)

#### 3.1 Add --skip-dedup Flag

```python
parser.add_argument(
    "--skip-dedup",
    action="store_true",
    help="Skip deduplication (for initial seeding on empty pool)",
)
```

#### 3.2 Fix Cost Estimate

```python
def estimate_cost(question_count: int, skip_dedup: bool = False) -> dict:
    batch_size = 5
    generation_calls = (question_count + batch_size - 1) // batch_size

    # Sonnet: ~2000 input, ~2000 output per batch (5 questions)
    gen_input_tokens = generation_calls * 2000
    gen_output_tokens = generation_calls * 2000
    gen_cost = (
        gen_input_tokens / 1_000_000 * sonnet_pricing["input_per_million"]
        + gen_output_tokens / 1_000_000 * sonnet_pricing["output_per_million"]
    )

    if skip_dedup:
        dedup_cost = 0
    else:
        # ~3 Haiku calls per question (with early exit)
        dedup_calls = question_count * 3
        dedup_cost = dedup_calls * 0.001  # ~$0.001 per call

    return {
        "generation_calls": generation_calls,
        "generation_cost": gen_cost,
        "dedup_cost": dedup_cost,
        "total_cost": gen_cost + dedup_cost,
    }
```

#### 3.3 State Persistence for Resume

```python
STATE_FILE = Path("data/.seed_progress.json")

def save_progress(state: dict) -> None:
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))

def load_progress() -> dict | None:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            return None
    return None

def clear_progress() -> None:
    STATE_FILE.unlink(missing_ok=True)
```

**State format:**
```json
{
  "started_at": "2026-01-18T10:00:00",
  "target_total": 250,
  "completed_areas": ["Ethics", "Measurement"],
  "current_area": "Behavior-Change Procedures",
  "current_area_progress": 12,
  "stats": {
    "generated": 78,
    "rejected": 5
  }
}
```

#### 3.4 Progress Display

```python
# During generation
print(f"\n[{area.value}] Generating {count} questions...")
print(f"  Progress: {len(questions)}/{count} | Rejected: {rejected_count}")
```

---

### Phase 4: Configuration (config/config.json)

```json
{
  "pool_management": {
    "threshold": 20,
    "batch_size": 50,
    "dedup_model": "claude-haiku-4-5",
    "dedup_check_limit": 30,
    "dedup_confidence_threshold": "high",
    "dedup_early_exit_batches": 3,
    "generation_batch_size": 5
  }
}
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/services/question_generator.py` | Add Pydantic models, `generate_question_batch()` with structured outputs |
| `src/services/pool_manager.py` | Use batch generation, confidence filter, early exit, skip-dedup |
| `src/scripts/seed_questions.py` | --skip-dedup flag, fix cost estimate, state persistence |
| `config/config.json` | New config parameters |

---

## API Requirements

**Structured Outputs Beta:**
- Requires beta header: `structured-outputs-2025-11-13`
- Use `client.beta.messages.create()` instead of `client.messages.create()`
- Supported models: Claude Sonnet 4.5, Claude Opus 4.1, Claude Opus 4.5, Claude Haiku 4.5
- First request has ~1s latency for grammar compilation (cached 24h)

**Anthropic SDK:**
- Ensure `anthropic` package is up-to-date: `pip install --upgrade anthropic`
- Pydantic v2 required for `model_json_schema()`

---

## CLI Usage

```bash
# Initial seed (empty database, skip dedup)
python -m src.scripts.seed_questions --count 250 --skip-dedup

# Resume interrupted seed
python -m src.scripts.seed_questions --resume

# Normal replenishment (with dedup)
python -m src.scripts.seed_questions --count 50

# Dry run
python -m src.scripts.seed_questions --count 250 --dry-run
```

---

## Cost Comparison

| Scenario | Sonnet Calls | Haiku Calls | Est. Cost |
|----------|--------------|-------------|-----------|
| Before (250 q, high rejection) | 350+ | 3500+ | $30+ |
| After (250 q, normal) | 50 | ~750 | ~$2.50 |
| After (250 q, --skip-dedup) | 50 | 0 | ~$1.50 |

---

*Plan Version: 2.1 - Added structured outputs for guaranteed JSON*
*Created: 2026-01-18*

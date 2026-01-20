# Complete Guide: PDF Preprocessing & Question Generation in AbaQuiz

## Overview

AbaQuiz uses a two-phase pipeline:
1. **PDF Preprocessing** - Converts BCBA study PDFs to structured markdown (one-time)
2. **Question Generation** - Uses Claude to generate quiz questions from processed content

---

## Part 1: PDF Preprocessing Pipeline

### Step-by-Step Flow

```
Raw PDFs → Claude API (document type) → Markdown Files → Cached for Question Generation
```

### Step 1: Discovery & Validation

**File**: `src/preprocessing/run_preprocessing.py`

1. Scans `data/raw/` directory recursively for PDFs
2. Filters documents using predefined mappings:

```python
# src/preprocessing/pdf_processor.py:45-72
BCBA_DOCUMENTS = {
    "BCBA-Task-List-5th-Edition.pdf": "core/task_list.md",
    "BCBA-Handbook.pdf": "core/handbook.md",
    "Ethics-Code-for-Behavior-Analysts.pdf": "ethics/ethics_code.md",
    # ... more mappings
}

SKIP_DOCUMENTS = {
    "ACE-Provider-Handbook.pdf",  # Not relevant for BCBA
    "RBT-Handbook.pdf",
    # ...
}
```

3. Checks `preprocessing_manifest.json` to skip already-processed files

### Step 2: PDF Splitting (Large Documents)

**File**: `src/preprocessing/pdf_processor.py:426-468`

```python
def _split_large_pdf(self, pdf_path: Path) -> list[bytes]:
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)

    # Limits per Anthropic API docs:
    # - max_pages_per_request = 100
    # - max_file_size_mb = 32 MB
```

**Correlation with API Documentation:**

| Requirement | API Limit | AbaQuiz Implementation |
|------------|-----------|------------------------|
| Max pages per request | 100 | `max_pages_per_request = 100` |
| Max request size | 32MB | `max_file_size_mb = 32` |

### Step 3: Send PDF to Claude API

**File**: `src/preprocessing/pdf_processor.py:247-296`

The implementation uses Claude's **native document type** (not image conversion):

```python
# System prompt for extraction
PDF_EXTRACTION_PROMPT = """You are processing BCBA exam study material from a PDF document.

Your task:
1. Extract ALL content from this PDF, preserving structure
2. Convert to well-formatted markdown
3. Preserve tables as markdown tables - pay special attention to table formatting
4. Maintain hierarchical structure with proper # headers
5. Include ALL definitions, terms, and concepts - do not summarize
6. Fix any OCR artifacts or formatting issues if present

Output clean markdown only. No commentary or explanations."""

# API call
response = await self.client.messages.create(
    model=self.settings.claude_model,  # claude-sonnet-4-5
    max_tokens=16384,
    system=PDF_EXTRACTION_PROMPT,
    messages=[{
        "role": "user",
        "content": [{
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": base64.standard_b64encode(pdf_bytes).decode("utf-8")
            }
        }, {
            "type": "text",
            "text": f"Extract and structure all content from this PDF document: {pdf_name}"
        }]
    }]
)
```

**Correlation with API Best Practices:**

| Best Practice | Implementation |
|--------------|----------------|
| Place PDFs before text | Document block comes first in content array |
| Use base64 encoding | `base64.standard_b64encode(pdf_bytes)` |
| Proper media type | `"media_type": "application/pdf"` |
| Use document type (not image) | `"type": "document"` for native PDF support |

### Step 4: Rate Limit Handling

**File**: `src/preprocessing/pdf_processor.py:298-424`

```python
# Retry strategy
INITIAL_RETRIES = 3
RETRY_DELAYS = [10, 20]  # seconds

EXTENDED_BACKOFF = [60, 300, 600]  # 1min, 5min, 10min
```

**Rate limit types detected:**
- RPM (Requests Per Minute)
- ITPM (Input Tokens Per Minute)
- OTPM (Output Tokens Per Minute)

### Step 5: Output & Deduplication

**Output Structure:**
```
data/processed/
├── 00_index.md                    # Auto-generated TOC
├── core/
│   ├── task_list.md
│   ├── handbook.md
│   └── tco.md
├── ethics/
│   └── ethics_code.md
├── supervision/
│   └── curriculum.md
├── reference/
│   ├── glossary.md
│   └── key_terms.md
└── preprocessing_manifest.json
```

**Deduplication via MD5 hash:**
```markdown
<!-- hash:abc123def456 -->
## Source: BCBA-Handbook.pdf

{extracted content}
```

### CLI Commands

```bash
# Interactive mode (prompts before each PDF)
python -m src.preprocessing.run_preprocessing

# Process all without prompts
python -m src.preprocessing.run_preprocessing -y

# Dry run (preview without API calls)
python -m src.preprocessing.run_preprocessing --dry-run

# Resume after rate limit
python -m src.preprocessing.run_preprocessing  # Auto-resumes from manifest
```

### Token & Cost Tracking

From the manifest, actual processing costs:

| Document | Pages | Input Tokens | Output Tokens |
|----------|-------|--------------|---------------|
| BCBA-Handbook.pdf | 78 | 178,918 | 16,384 |
| Ethics Code | 19 | 46,543 | 15,598 |
| Task List | 5 | 10,143 | 2,146 |
| **Total** | **170** | **370,730** | **61,506** |

**Estimated Cost**: ~$1.12 (one-time)

---

## Part 2: Question Generation System

### Architecture Overview

```
Processed Markdown → Claude Sonnet 4.5 → Structured JSON → Database
                     (with structured outputs beta)
```

### Step 1: Content Loading

**File**: `src/services/question_generator.py`

```python
# Content area to file mapping
AREA_FILES = {
    ContentArea.ETHICS: ["ethics/ethics_code.md", "core/handbook.md"],
    ContentArea.BEHAVIOR_ASSESSMENT: ["core/task_list.md", "core/tco.md"],
    ContentArea.BEHAVIOR_CHANGE_PROCEDURES: ["core/task_list.md", "reference/glossary.md"],
    # ... 9 total content areas
}

def _load_content_for_area(self, content_area: ContentArea) -> str:
    # Cached loading - avoids repeated file reads
    if content_area in self._content_cache:
        return self._content_cache[content_area]

    content_parts = []
    for file in AREA_FILES[content_area]:
        path = self.content_dir / file
        if path.exists():
            content_parts.append(path.read_text())

    content = "\n\n---\n\n".join(content_parts)
    self._content_cache[content_area] = content
    return content
```

### Step 2: Define Pydantic Models for Structured Output

**File**: `src/services/question_generator.py`

```python
from pydantic import BaseModel
from typing import Optional

class SourceCitation(BaseModel):
    section: str      # e.g., "Task List F-1", "Ethics Code 2.09"
    heading: str      # Section heading
    quote: str        # Brief quote (max 50 words)

class QuestionOptions(BaseModel):
    A: Optional[str] = None
    B: Optional[str] = None
    C: Optional[str] = None
    D: Optional[str] = None
    True_: Optional[str] = None   # For true/false
    False_: Optional[str] = None

class GeneratedQuestion(BaseModel):
    question: str
    type: str  # "multiple_choice" | "true_false"
    options: QuestionOptions
    correct_answer: str  # A/B/C/D or True/False
    explanation: str
    category: str  # "scenario" | "definition" | "application"
    source_citation: SourceCitation

class QuestionBatch(BaseModel):
    questions: list[GeneratedQuestion]
```

### Step 3: API Call with Structured Outputs

**File**: `src/services/question_generator.py`

```python
from anthropic import transform_schema

async def generate_question_batch(
    self,
    content_area: ContentArea,
    count: int = 5,
) -> list[dict[str, Any]]:

    content = self._load_content_for_area(content_area)

    # Calculate category distribution: 40% scenario, 30% definition, 30% application
    scenario_count = round(count * 0.4)
    definition_count = round(count * 0.3)
    application_count = count - scenario_count - definition_count

    response = await self.client.beta.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        betas=["structured-outputs-2025-11-13"],  # Required beta header
        system=BATCH_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"""Generate {count} questions for {content_area.value}.

Distribution:
- {scenario_count} scenario-based questions
- {definition_count} definition/concept questions
- {application_count} application questions

STUDY CONTENT:
{content}"""
        }],
        output_format={
            "type": "json_schema",
            "schema": transform_schema(QuestionBatch),  # Pydantic → JSON Schema
        },
    )

    # Guaranteed valid JSON - no parsing errors possible
    batch = json.loads(response.content[0].text)
    return [self._normalize_question(q) for q in batch["questions"]]
```

**Correlation with API Documentation:**

| API Feature | Implementation |
|------------|----------------|
| Beta header | `betas=["structured-outputs-2025-11-13"]` |
| Pydantic integration | `transform_schema(QuestionBatch)` |
| JSON schema format | `output_format={"type": "json_schema", "schema": ...}` |
| Model support | Claude Sonnet 4.5 |

### Step 4: System Prompt for Question Generation

```python
BATCH_SYSTEM_PROMPT = """You are creating BCBA certification exam practice questions.

REQUIREMENTS:
1. Questions must match BCBA 5th Edition Task List exam style
2. Create plausible distractors (avoid "all of the above"/"none of the above")
3. Reference specific ethics codes and task list items
4. Use diverse names, settings, demographics in scenarios
5. Mix difficulty levels: straightforward + multi-step reasoning

CATEGORY DEFINITIONS:
- **Scenario (40%)**: Clinical vignettes with specific client details
- **Definition (30%)**: Key terms requiring true understanding, not just recall
- **Application (30%)**: Novel situations requiring principle transfer

CITATIONS: Include source_citation for each question referencing:
- Task List items (e.g., "F-1", "B-3")
- Ethics Code sections (e.g., "2.09", "3.01")
- Specific handbook guidance"""
```

### Step 5: Question Deduplication (Haiku)

**File**: `src/services/pool_manager.py`

```python
async def check_duplicate(
    self,
    new_question: dict[str, Any],
    existing_questions: list[dict[str, Any]],
) -> bool:
    """Check if new question is too similar to existing ones using Haiku."""

    # Format question for comparison
    new_q_text = f"""Question: {new_question['question']}
Options: {json.dumps(new_question['options'])}
Answer: {new_question['correct_answer']}"""

    # Batch existing questions (5 at a time for efficiency)
    for batch in self._chunk(existing_questions, 5):
        response = await self.client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": f"""Compare this NEW question to EXISTING questions.

NEW QUESTION:
{new_q_text}

EXISTING QUESTIONS:
{self._format_batch(batch)}

Is the new question TOO SIMILAR to any existing question?

TOO SIMILAR means:
- Same specific concept with superficial wording changes
- Nearly identical scenarios with minor detail swaps
- Would feel repetitive to a student

NOT TOO SIMILAR means:
- Different aspects of same topic
- Different reasoning paths required
- Provides additional learning value

Return JSON: {{"is_duplicate": bool, "reason": str, "confidence": "high"|"medium"|"low"}}"""
            }]
        )

        result = json.loads(response.content[0].text)
        if result["is_duplicate"] and result["confidence"] == "high":
            return True  # Reject question

    return False  # Accept question
```

**Dedup Configuration:**
```json
{
  "dedup_model": "claude-haiku-4-5",
  "dedup_check_limit": 30,
  "dedup_confidence_threshold": "high",
  "dedup_early_exit_batches": 3,
  "generation_batch_size": 5
}
```

### Step 6: Pool Management & BCBA Exam Weights

**File**: `src/services/pool_manager.py`

```python
# BCBA 5th Edition exam weight distribution
BCBA_WEIGHTS = {
    ContentArea.ETHICS: 0.13,
    ContentArea.BEHAVIOR_CHANGE_PROCEDURES: 0.14,
    ContentArea.CONCEPTS_AND_PRINCIPLES: 0.14,
    ContentArea.BEHAVIOR_ASSESSMENT: 0.13,
    ContentArea.INTERVENTIONS: 0.11,
    ContentArea.SUPERVISION: 0.11,
    ContentArea.MEASUREMENT: 0.12,
    ContentArea.EXPERIMENTAL_DESIGN: 0.07,
    ContentArea.PHILOSOPHICAL_UNDERPINNINGS: 0.05,
}

async def check_and_replenish_pool(self) -> dict[str, Any]:
    """Auto-generate questions when pool runs low."""

    # Calculate: avg unseen questions per active user
    metrics = await self.repo.get_pool_metrics()

    # Trigger when avg_unseen < 20 (configurable)
    if metrics["avg_unseen"] < self.config["pool_threshold"]:
        distribution = self.calculate_batch_distribution()
        # Generate batch_size (50) questions distributed by BCBA weights
        await self._generate_batch(distribution)
```

### Step 7: Seeding Script

**File**: `src/scripts/seed_questions.py`

```bash
# Generate 250 questions distributed by BCBA exam weights
python -m src.scripts.seed_questions --count 250

# Skip deduplication for initial empty pool (faster)
python -m src.scripts.seed_questions --count 250 --skip-dedup

# Generate for specific content area only
python -m src.scripts.seed_questions --area "Ethics" --count 50

# Preview plan (shows cost estimate)
python -m src.scripts.seed_questions --dry-run

# Resume interrupted seeding
python -m src.scripts.seed_questions --resume --count 300
```

**Cost Estimates:**
- Initial seed (250 questions with dedup): ~$6.00
- Initial seed (250 questions no dedup): ~$4.50
- Weekly batch (50 questions): ~$1.20

---

## Best Practices Alignment with API Docs

### PDF Support Best Practices

| Anthropic Recommendation | AbaQuiz Implementation |
|-------------------------|------------------------|
| Place PDFs before text in requests | Document block comes first |
| Use standard fonts | Processing BACB official PDFs |
| Split large PDFs into chunks | Max 100 pages per request |
| Enable prompt caching for repeated analysis | Not implemented (one-time processing) |
| Rotate pages to proper orientation | Official PDFs already oriented |

### Structured Outputs Best Practices

| Anthropic Recommendation | AbaQuiz Implementation |
|-------------------------|------------------------|
| Use beta header | `betas=["structured-outputs-2025-11-13"]` |
| Use Pydantic for schema definition | `transform_schema()` helper |
| Handle refusals (`stop_reason: "refusal"`) | Could be improved |
| Handle max_tokens cutoff | Uses adequate `max_tokens=4096` for batches |
| Set `additionalProperties: false` | SDK handles automatically |

### Error Handling Best Practices

| Anthropic Recommendation | AbaQuiz Implementation |
|-------------------------|------------------------|
| Implement retry with backoff | 3 retries + extended backoff (1m, 5m, 10m) |
| Handle rate limits gracefully | Detects RPM/ITPM/OTPM limits |
| Save progress for resumption | Manifest tracking |
| Graceful degradation | Dedup failure doesn't block generation |

---

## Example Output

### Generated Question

```json
{
    "question": "A BCBA notices that a client's aggressive behavior increases immediately after demands are placed and results in the removal of task materials. Based on this pattern, the behavior analyst should FIRST:",
    "type": "multiple_choice",
    "options": {
        "A": "Implement a DRA procedure targeting compliance",
        "B": "Conduct a functional behavior assessment",
        "C": "Apply an extinction procedure by not removing materials",
        "D": "Consult with the client's physician about medication"
    },
    "correct_answer": "B",
    "explanation": "A functional behavior assessment (FBA) should be conducted first to systematically identify the function of the behavior before selecting an intervention (Task List item F-1). While the pattern suggests escape-maintained behavior, a proper FBA will confirm this hypothesis...",
    "category": "scenario",
    "content_area": "Behavior Assessment",
    "model": "claude-sonnet-4-5",
    "source_citation": {
        "section": "Task List F-1",
        "heading": "Review records and available data at the outset of the case",
        "quote": "Behavior analysts conduct assessments...before selecting and implementing interventions"
    }
}
```

---

## API Reference Links

- [PDF Support - Claude Docs](https://platform.claude.com/docs/en/build-with-claude/pdf-support)
- [Structured Outputs - Claude Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Files API - Claude Docs](https://platform.claude.com/docs/en/build-with-claude/files)
- [Messages API - Claude Docs](https://platform.claude.com/docs/en/api/messages)

# PDF Preprocessing Guide

Quick guide for processing BCBA study materials into structured markdown.

## Basic Usage

```bash
# Process PDFs interactively (prompts before each file)
python -m src.preprocessing.run_preprocessing

# Process all without prompts
python -m src.preprocessing.run_preprocessing -y

# Process with verbose output
python -m src.preprocessing.run_preprocessing -v

# Dry run (see what would be processed without API calls)
python -m src.preprocessing.run_preprocessing --dry-run

# Force reprocess all PDFs (ignore previous progress)
python -m src.preprocessing.run_preprocessing --force -y

# Process a single file
python -m src.preprocessing.run_preprocessing -f data/raw/BCBA-Task-List-5th-Edition.pdf -v
```

## Interactive Mode

By default, the script prompts before processing each PDF:

```
[1/8] BCBA-Task-List-5th-Edition.pdf
  Output: core/task_list.md
  Process? [Y]es / [s]kip / [a]ll remaining / [q]uit:
```

Options:
- **Y/Enter** - Process this PDF
- **s** - Skip this PDF
- **a** - Process all remaining PDFs without prompting
- **q** - Quit (progress is saved)

Use `-y` or `--yes` to skip prompts and process everything automatically.

## Input/Output

**Input:** Place BCBA PDFs in `data/raw/` (or subdirectories)

**Output:** Structured markdown in `data/processed/`:
```
data/processed/
├── core/
│   ├── task_list.md      # BCBA-Task-List-5th-Edition.pdf
│   ├── handbook.md       # BCBA-Handbook.pdf
│   └── tco.md            # BCBA-TCO-6th-Edition.pdf
├── ethics/
│   └── ethics_code.md    # Ethics-Code-for-Behavior-Analysts.pdf
├── supervision/
│   └── curriculum.md     # Supervisor-Training-Curriculum.pdf
├── reference/
│   ├── glossary.md       # ABA-Glossary-Workbook.pdf + PECS-Glossary.pdf
│   └── key_terms.md      # ABA-Terminology-Acronyms.pdf
└── 00_index.md           # Auto-generated index
```

## What Gets Processed

| PDF | Output |
|-----|--------|
| BCBA-Task-List-5th-Edition.pdf | core/task_list.md |
| BCBA-Handbook.pdf | core/handbook.md |
| BCBA-TCO-6th-Edition.pdf | core/tco.md |
| Ethics-Code-for-Behavior-Analysts.pdf | ethics/ethics_code.md |
| Supervisor-Training-Curriculum.pdf | supervision/curriculum.md |
| ABA-Glossary-Workbook.pdf | reference/glossary.md |
| ABA-Terminology-Acronyms.pdf | reference/key_terms.md |
| PECS-Glossary.pdf | reference/glossary.md (appended) |

## What Gets Skipped

Non-BCBA materials are automatically skipped:
- ACE-Provider-Handbook.pdf
- BCaBA-Handbook.pdf / BCaBA-TCO-6th-Edition.pdf
- RBT-Ethics-Code.pdf / RBT-Handbook.pdf
- ABA-101-Handouts.pdf
- State-specific docs (ABA-Description-Michigan.pdf, etc.)

## Resume Support

Progress is saved after each PDF. If interrupted (rate limit, error, Ctrl+C):
1. Progress is saved to `data/processed/preprocessing_manifest.json`
2. Run the same command again to resume from where you left off
3. Use `--force` to reprocess everything from scratch

## Verification

After processing:
```bash
# Check output structure
tree data/processed/

# Verify file contents
head -50 data/processed/core/task_list.md

# Check the index
cat data/processed/00_index.md
```

## Environment

Requires `ANTHROPIC_API_KEY` in `.env` or environment variables.

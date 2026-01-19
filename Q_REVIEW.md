# BCBA Question Pool Review

**Review Date:** 2026-01-19
**Reviewer:** Claude (Automated Review)
**Questions Reviewed:** 234 total, ~15 in detail across all content areas

---

## Executive Summary

The question pool is **high quality** and suitable for BCBA exam preparation. Questions are technically accurate, have well-written explanations, and follow appropriate exam-style formatting. However, the generation prompts reference the outdated 5th Edition Task List and miss key 6th Edition emphases like cultural humility.

**Overall Rating:** ✅ Good (with recommended improvements)

---

## Part 1: Question Pool Validation

### Content Areas Reviewed

| Content Area | Sample Questions | Verdict |
|--------------|------------------|---------|
| Personnel Supervision & Management | #266, #267 | ✅ Accurate |
| Ethics | #184, #185 | ✅ Accurate |
| Concepts and Principles | #161, #162, #163 | ✅ Accurate |
| Behavior-Change Procedures | #141, #142, #143 | ✅ Accurate |
| Measurement, Data Display, Interpretation | #228, #229 | ✅ Accurate |

### Strengths Identified

1. **Technically Correct Answers**
   - Ethics questions properly cite specific code sections (1.11, 3.03, 1.05, 1.14)
   - Procedural questions reference correct Task List items (B-14, G-14)
   - Explanations correctly distinguish between similar concepts (DRL vs DRO, mand vs echoic)

2. **Exam-Appropriate Format**
   - Scenario-based clinical vignettes (~40%)
   - Definition/concept testing (~30%)
   - Application questions (~30%)
   - Four plausible answer options per multiple choice question

3. **Quality Distractors**
   - Wrong answers are plausible but distinguishable with proper knowledge
   - Example: Q#141 correctly differentiates DRL criterion setting from DRO and continuous reinforcement

4. **Thorough Explanations**
   - Each question explains why incorrect options are wrong, not just why the correct answer is right
   - References specific ethics codes, task list items, and ABA principles

### Issues Found

- **None** - All reviewed questions were factually accurate and well-constructed

---

## Part 2: Prompt Analysis & Recommendations

### File Reviewed
`src/services/question_generator.py`

---

### 🔴 Critical Issues

#### 1. Wrong Task List Version Referenced

**Location:** Lines 84, 122

**Current:**
```python
"BCBA 5th Edition Task List"
```

**Problem:** The BCBA exam transitioned to the **6th Edition** in January 2025. All prompts reference the outdated 5th Edition.

**Fix:** Update all references to "6th Edition Task List"

---

#### 2. Missing Cultural Humility Emphasis (New in 6th Edition)

The 6th Edition adds significant focus on cultural humility, inclusion, and culturally responsive practice. Current prompts don't address this.

**Add to `SYSTEM_PROMPT` (after line 91):**
```
8. Incorporate cultural considerations - questions should reflect diverse client backgrounds,
   and correct answers should demonstrate cultural humility and responsiveness
9. Include assent (not just consent) considerations where applicable - the 6th Edition
   emphasizes client dignity and self-determination
10. A technically correct procedure that ignores assent, caregiver context, cultural factors,
    or safety should be presented as an INCORRECT option
```

---

### 🟡 Moderate Issues

#### 3. Strengthen "Best Answer" Question Guidance

Real BCBA exams often have questions where multiple answers seem correct, but one is the "best" or "most appropriate" response. Current prompts say distractors should be "plausible" but don't explicitly guide this common question style.

**Add to `SYSTEM_PROMPT`:**
```
When writing questions with multiple plausible options:
- Use "BEST," "MOST appropriate," or "FIRST step" language to signal ranking is required
- At least one distractor should be a technically correct procedure that violates ethics,
  ignores practical constraints, or lacks cultural sensitivity
- Include options that represent common mistakes or misconceptions
```

---

#### 4. Ethics Questions Are Too Siloed

Current ethics guidance (lines 161-167) focuses only on the ethics domain. Real BCBA exams integrate ethical reasoning across ALL domains.

**Add to `BATCH_SYSTEM_PROMPT` (after line 135):**
```
Cross-cutting ethics requirement:
- Even non-ethics questions should occasionally test ethical reasoning within the domain
- Example: A measurement question might include an option about collecting data without proper consent
- Example: A supervision question should consider ethics of feedback delivery and competency boundaries
- Example: An intervention question might have a distractor that works technically but ignores client assent
```

---

#### 5. Missing "Integrated Scenario" Question Type

Real exams frequently present scenarios requiring synthesis across multiple Task List areas. Current categories (scenario, definition, application) don't capture this.

**Add to `QuestionCategory` enum:**
```python
INTEGRATED = "integrated"  # Cross-domain synthesis
```

**Add to `CATEGORY_INSTRUCTIONS`:**
```python
QuestionCategory.INTEGRATED: """Create an INTEGRATED question (cross-domain synthesis):
- Present a scenario that spans multiple Task List domains
- Require synthesizing ethics + assessment OR measurement + intervention selection
- Test the ability to prioritize competing considerations
- The correct answer should balance technical correctness with ethical/practical constraints
- Example: A functional analysis scenario where the correct answer considers
  both the data pattern AND client safety/dignity
- Example: A supervision scenario involving both feedback delivery AND scope of competence"""
```

**Update `CATEGORY_WEIGHTS`:**
```python
CATEGORY_WEIGHTS: dict[QuestionCategory, float] = {
    QuestionCategory.SCENARIO: 0.35,
    QuestionCategory.DEFINITION: 0.25,
    QuestionCategory.APPLICATION: 0.25,
    QuestionCategory.INTEGRATED: 0.15,
}
```

---

### 🟢 Minor Enhancements

#### 6. Add Distractor Quality Patterns

Add specific distractor patterns based on common exam traps.

**Add new constant after line 157:**
```python
DISTRACTOR_PATTERNS = """
When creating incorrect answer options, use these patterns:

1. CONCEPTUAL CONFUSION: A term commonly confused with the correct answer
   (e.g., negative reinforcement vs. punishment, mand vs. tact)

2. PARTIALLY CORRECT: An answer that addresses part of the scenario but misses key elements
   (e.g., correct procedure but wrong timing or sequence)

3. TECHNICALLY RIGHT BUT ETHICALLY WRONG: A procedure that would achieve behavior change
   but violates ethics, ignores consent/assent, or lacks cultural sensitivity

4. COMMON MISCONCEPTION: A choice reflecting what untrained practitioners often do
   (e.g., using punishment before trying reinforcement-based approaches)

5. PREMATURE ACTION: An intervention step that skips required assessment or baseline
   (e.g., implementing treatment before completing FBA)

6. OVERGENERALIZATION: Applying a concept beyond its appropriate scope
   (e.g., using extinction for all attention-maintained behavior regardless of severity)
"""
```

---

#### 7. Enhance Data Interpretation Guidance

Per research, measurement questions should require actual interpretation, not just definitions.

**Update `CONTENT_AREA_GUIDANCE[ContentArea.MEASUREMENT]` (lines 189-195):**
```python
ContentArea.MEASUREMENT: """Measurement focus areas:
- Present ACTUAL data patterns or graph descriptions, ask what they demonstrate
- Questions should require interpreting level, trend, AND variability together
- Include questions about when data is sufficient to make clinical decisions
- Test understanding of measurement error and IOA threshold implications
- Ask "what would you conclude" or "what should happen next" not just "what is this called"
- Include questions about selecting appropriate measurement systems for specific behaviors
- Test ability to identify threats to data validity (reactivity, observer drift, etc.)""",
```

---

#### 8. Add Difficulty Calibration Guidance

Add explicit difficulty distribution to ensure appropriate challenge levels.

**Add new constant:**
```python
DIFFICULTY_GUIDANCE = """
Target difficulty distribution for each batch:
- 20% RECALL: Direct application of definitions to clear examples (entry-level)
- 50% APPLICATION: Apply concept to novel scenario with clear correct answer (standard)
- 30% ANALYSIS: Multi-step reasoning, competing priorities, or ambiguous scenarios
  where multiple options seem plausible (challenging)

For ANALYSIS-level questions:
- Require weighing multiple factors (effectiveness vs. ethics vs. practicality)
- Present scenarios with incomplete information requiring professional judgment
- Include questions where the "textbook" answer conflicts with practical constraints
"""
```

---

#### 9. Add Negative Stem Guidance

Real exams sometimes use negative stems ("Which is NOT..." or "All EXCEPT..."). Current prompts don't address this.

**Add to `SYSTEM_PROMPT`:**
```
Occasionally (10-15% of questions) use negative stems:
- "Which of the following is NOT an example of..."
- "All of the following are correct EXCEPT..."
- "Which action would be LEAST appropriate..."
When using negative stems, make sure the question is clearly worded and the stem is emphasized.
```

---

## Part 3: Implementation Priority

| Priority | Issue | Effort | Impact |
|----------|-------|--------|--------|
| 🔴 P0 | Update 5th → 6th Edition references | Low | High |
| 🔴 P0 | Add cultural humility guidance | Low | High |
| 🟡 P1 | Add "best answer" guidance | Low | Medium |
| 🟡 P1 | Add cross-cutting ethics requirement | Low | Medium |
| 🟡 P1 | Add INTEGRATED question category | Medium | Medium |
| 🟢 P2 | Add distractor patterns | Low | Low |
| 🟢 P2 | Enhance measurement guidance | Low | Low |
| 🟢 P2 | Add difficulty calibration | Low | Low |
| 🟢 P2 | Add negative stem guidance | Low | Low |

---

## Part 4: Sample Improved System Prompt

Here's what the updated `SYSTEM_PROMPT` should look like:

```python
SYSTEM_PROMPT = """You are an expert BCBA (Board Certified Behavior Analyst) exam question writer. Your task is to create high-quality practice questions based on the BCBA 6th Edition Task List content provided.

Core Guidelines:
1. All options should be plausible to someone who hasn't mastered the content
2. Avoid "all of the above" or "none of the above" options
3. The explanation should teach the concept and explain why the correct answer is right AND why other options are wrong
4. Match the difficulty and style of actual BCBA certification exam questions
5. Reference specific ethics codes, task list items, or principles where relevant
6. Use diverse names, settings, and demographics in scenarios
7. Vary complexity - some questions should require multi-step reasoning
8. Incorporate cultural considerations - correct answers should demonstrate cultural humility and responsiveness
9. Include assent (not just consent) considerations - the 6th Edition emphasizes client dignity and self-determination
10. A technically correct procedure that ignores assent, caregiver context, cultural factors, or safety is WRONG

Question Style Guidelines:
- Use "BEST," "MOST appropriate," or "FIRST step" language when multiple options could partially work
- At least one distractor should be technically correct but ethically problematic or impractical
- Include distractors representing common misconceptions or premature actions
- Occasionally (10-15%) use negative stems ("Which is NOT...", "All EXCEPT...")

Distractor Patterns to Use:
- Conceptual confusion (similar but distinct terms)
- Partially correct (right idea, wrong execution)
- Technically right but ethically wrong
- Common practitioner misconceptions
- Premature action (skipping required steps)

You MUST respond with valid JSON matching this exact schema:
{
  "question": "The question text here",
  "type": "multiple_choice",
  "options": {
    "A": "First option",
    "B": "Second option",
    "C": "Third option",
    "D": "Fourth option"
  },
  "correct_answer": "B",
  "explanation": "Detailed explanation of why B is correct and why other options are incorrect."
}
"""
```

---

## References

- [BCBA Exam 2025: Format, Content Domains, and What Actually Gets Tested](https://www.operationsarmy.com/post/bcba-exam-2025-format-content-domains-and-what-actually-gets-tested)
- [Pass the Big ABA Exam - Breaking Down BCBA Exam Questions](https://passthebigabaexam.com/dana-dos-the-abcs-of-breaking-down-bcba-exam-test-questions/)
- [BCBA Exam Format Breakdown 2025](https://abastudyguide.com/bcba-exam-format-breakdown-what-to-expect-on-test-day-2025-update/)
- [BCBA Test Content Outline (6th ed.)](https://www.bacb.com/wp-content/uploads/2022/01/BCBA-6th-Edition-Test-Content-Outline-240903-a.pdf)
- [Behavior Analyst Study - Free Practice Questions](https://behavioranalyststudy.com/bcba-exam-practice-questions/)

---

## Next Steps

1. [ ] Update `question_generator.py` with 6th Edition references
2. [ ] Add cultural humility and assent guidance to prompts
3. [ ] Add INTEGRATED question category
4. [ ] Regenerate question pool with updated prompts
5. [ ] Re-validate sample of new questions against these criteria

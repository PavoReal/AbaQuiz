"""
Seed the database with sample questions for testing.

Run with: python -m scripts.seed_questions
"""

import asyncio
import json

from src.config.settings import get_settings
from src.database.migrations import initialize_database
from src.database.repository import Repository


SAMPLE_QUESTIONS = [
    {
        "content": "A behavior analyst is working with a client who exhibits self-injurious behavior. The functional behavior assessment suggests the behavior is maintained by automatic reinforcement. Which of the following would be the MOST appropriate first step?",
        "question_type": "multiple_choice",
        "options": {
            "A": "Implement differential reinforcement of other behavior (DRO)",
            "B": "Conduct a functional analysis to confirm the function",
            "C": "Apply response blocking immediately",
            "D": "Increase the magnitude of social reinforcement"
        },
        "correct_answer": "B",
        "explanation": "Before implementing any intervention, it is essential to confirm the function of the behavior through a functional analysis. While a functional behavior assessment may have suggested automatic reinforcement, a functional analysis provides experimental verification. This aligns with the ethical requirement to use assessment results to guide intervention selection (Ethics Code 2.13). Response blocking and DRO may be appropriate interventions, but only after confirming the function. Social reinforcement would be inappropriate if the behavior is automatically maintained.",
        "content_area": "Behavior Assessment"
    },
    {
        "content": "According to the BACB Ethics Code, when a behavior analyst discovers that a colleague's intervention may be causing harm to a client, they should FIRST:",
        "question_type": "multiple_choice",
        "options": {
            "A": "Report the colleague to the BACB immediately",
            "B": "Attempt to resolve the issue directly with the colleague",
            "C": "Inform the client's family about the potential harm",
            "D": "Document the concerns and take no further action"
        },
        "correct_answer": "B",
        "explanation": "The BACB Ethics Code (1.05) requires behavior analysts to first attempt to resolve ethical concerns informally when possible. This typically means speaking directly with the colleague about the concerns before escalating to formal reporting. While documentation is important and reporting may eventually be necessary, the first step should be direct communication when it is safe and appropriate to do so.",
        "content_area": "Ethics"
    },
    {
        "content": "A teacher is using a token economy with her class. Students earn tokens for completing work and can exchange them for preferred activities. One student, Marcus, has stopped responding to the token system. Which principle BEST explains this change?",
        "question_type": "multiple_choice",
        "options": {
            "A": "Stimulus generalization",
            "B": "Satiation",
            "C": "Extinction",
            "D": "Negative punishment"
        },
        "correct_answer": "B",
        "explanation": "Satiation occurs when the effectiveness of a reinforcer decreases due to repeated or excessive presentation. If Marcus has had too much access to the backup reinforcers, tokens may no longer be effective. This is different from extinction (which would require withholding reinforcement), stimulus generalization (responding to similar stimuli), or negative punishment (removing a stimulus to decrease behavior).",
        "content_area": "Concepts and Principles"
    },
    {
        "content": "In a multiple baseline design across behaviors, when should intervention be introduced to the second behavior?",
        "question_type": "multiple_choice",
        "options": {
            "A": "After a predetermined number of sessions",
            "B": "When the first behavior shows a change in the desired direction",
            "C": "Immediately after baseline data collection",
            "D": "When the participant requests the change"
        },
        "correct_answer": "B",
        "explanation": "In a multiple baseline design, intervention is staggered across behaviors (or settings, or participants). The intervention is introduced to subsequent behaviors only after a change is observed in the preceding behavior. This staggering provides experimental control by demonstrating that behavior change occurs only when intervention is applied, ruling out confounding variables like maturation or history.",
        "content_area": "Experimental Design"
    },
    {
        "content": "Radical behaviorism differs from methodological behaviorism primarily in its treatment of:",
        "question_type": "multiple_choice",
        "options": {
            "A": "Observable behavior",
            "B": "Private events",
            "C": "Environmental variables",
            "D": "Learning principles"
        },
        "correct_answer": "B",
        "explanation": "Radical behaviorism, as developed by B.F. Skinner, includes private events (thoughts, feelings) as legitimate subject matter for scientific analysis, viewing them as behavior governed by the same principles as public behavior. Methodological behaviorism, in contrast, excludes private events from scientific study because they cannot be directly observed. Both approaches study observable behavior, environmental variables, and learning principles.",
        "content_area": "Philosophical Underpinnings"
    },
    {
        "content": "When using partial interval recording, the observer records whether the behavior occurred at any point during the interval.",
        "question_type": "true_false",
        "options": {
            "True": "True",
            "False": "False"
        },
        "correct_answer": "True",
        "explanation": "Partial interval recording involves dividing the observation period into equal intervals and recording whether the behavior occurred at ANY point during each interval. This method tends to overestimate the occurrence of behavior, especially for behaviors of short duration. It is most appropriate for behaviors that are difficult to count discretely or when an estimate of behavior occurrence is sufficient.",
        "content_area": "Measurement, Data Display, and Interpretation"
    },
    {
        "content": "A behavior analyst is supervising a new RBT and notices they are consistently providing reinforcement on an FR1 schedule when the behavior plan specifies VR3. The BEST course of action is to:",
        "question_type": "multiple_choice",
        "options": {
            "A": "Immediately take over the session",
            "B": "Provide corrective feedback after the session",
            "C": "Report the RBT to their credentialing body",
            "D": "Modify the behavior plan to match current practice"
        },
        "correct_answer": "B",
        "explanation": "Effective supervision includes providing timely feedback to supervisees. The appropriate response to a procedural error is to provide corrective feedback, which should include identifying the error, explaining the correct procedure, and allowing practice with feedback. Taking over the session may be warranted in cases of potential harm, but for a reinforcement schedule error, feedback after the session allows for a teaching moment without disrupting the client's session.",
        "content_area": "Personnel Supervision and Management"
    },
    {
        "content": "Functional communication training (FCT) is an example of:",
        "question_type": "multiple_choice",
        "options": {
            "A": "Differential reinforcement of alternative behavior (DRA)",
            "B": "Differential reinforcement of other behavior (DRO)",
            "C": "Differential reinforcement of low rates (DRL)",
            "D": "Differential reinforcement of incompatible behavior (DRI)"
        },
        "correct_answer": "A",
        "explanation": "Functional communication training teaches a communicative response as an alternative to problem behavior. Because it involves reinforcing an alternative behavior that serves the same function as the problem behavior, FCT is a specific application of DRA. DRO reinforces the absence of behavior, DRL reinforces lower rates of behavior, and DRI reinforces a behavior that is physically incompatible with the problem behavior.",
        "content_area": "Behavior-Change Procedures"
    },
    {
        "content": "When selecting an intervention, the behavior analyst should consider the least restrictive effective intervention that is also acceptable to the client and caregivers.",
        "question_type": "true_false",
        "options": {
            "True": "True",
            "False": "False"
        },
        "correct_answer": "True",
        "explanation": "The BACB Ethics Code and best practices in ABA require consideration of the least restrictive effective intervention. Additionally, social validity—including the acceptability of procedures to clients and caregivers—is an important factor in intervention selection. Interventions that are technically effective but not acceptable are unlikely to be implemented with fidelity or maintained over time.",
        "content_area": "Selecting and Implementing Interventions"
    },
    {
        "content": "A graph showing cumulative records is most useful for evaluating:",
        "question_type": "multiple_choice",
        "options": {
            "A": "Variability in behavior",
            "B": "Rate of responding",
            "C": "Duration of behavior",
            "D": "Latency to respond"
        },
        "correct_answer": "B",
        "explanation": "Cumulative records display the total number of responses over time, with steeper slopes indicating higher rates of responding. The slope of the line on a cumulative record directly represents the rate of behavior. While cumulative records can show overall response patterns, they are not ideal for showing variability, duration, or latency, which are better displayed using other graphing methods.",
        "content_area": "Measurement, Data Display, and Interpretation"
    },
]


async def seed_questions():
    """Add sample questions to the database."""
    settings = get_settings()

    # Initialize database
    await initialize_database(settings.database_path)

    # Connect to repository
    repo = Repository(settings.database_path)
    await repo.connect()

    print(f"Seeding {len(SAMPLE_QUESTIONS)} questions...")

    for i, q in enumerate(SAMPLE_QUESTIONS, 1):
        question_id = await repo.create_question(
            content=q["content"],
            question_type=q["question_type"],
            options=q["options"],
            correct_answer=q["correct_answer"],
            explanation=q["explanation"],
            content_area=q["content_area"],
        )
        print(f"  [{i}/{len(SAMPLE_QUESTIONS)}] Created question {question_id}: {q['content_area']}")

    await repo.close()
    print("\nDone! Questions seeded successfully.")


if __name__ == "__main__":
    asyncio.run(seed_questions())

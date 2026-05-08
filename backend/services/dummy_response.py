import asyncio
import random


RESPONSES = {
    "explain_how_what_define": [
        "Great question! In {course}, this concept is fundamental. When studying it, break it down into smaller parts: understand the definition first, then look at real-world examples, and finally practice applying it in problem sets.",
        "In {course}, understanding this topic deeply will help you throughout the semester. I recommend reviewing your lecture notes alongside the textbook — cross-referencing both sources really solidifies comprehension.",
        "That's a core concept in {course}. Think of it this way: start with the 'why' before the 'how'. Once you understand the motivation behind it, the mechanics become much easier to remember.",
    ],
    "exam_test_quiz": [
        "Preparing for exams in {course}? Here's a proven strategy: use active recall — close your notes and try to summarize each topic from memory. Then check what you missed. Repeat daily in the week before the exam.",
        "For {course} exams, focus on past papers if available. Examiners often revisit similar problem types. Also, make sure you understand *why* answers are correct, not just *what* they are.",
        "Great that you're thinking ahead about {course} assessments! Create a revision timetable, prioritize topics by weight, and don't forget to rest — sleep consolidates memory better than last-minute cramming.",
    ],
    "assignment_homework_project": [
        "For {course} assignments, always start by reading the requirements twice. Identify what's being asked, then plan your approach before writing a single line of code or text. Breaking the task into milestones helps a lot.",
        "Working on a {course} project? Make sure to document your approach as you go. Professors appreciate clear reasoning, not just a correct answer. Version control (Git) is your best friend for coding projects.",
        "In {course}, assignments are designed to reinforce lecture material. If you're stuck, revisit the relevant lecture slides first — the solution pattern is usually hinted at there.",
    ],
    "syllabus_topics_schedule": [
        "The {course} syllabus is your roadmap for the semester. I'd recommend mapping each topic to the weeks remaining and creating a personal study schedule. Would you like tips on any specific topic from the course?",
        "For {course}, the key topics are typically outlined in the course outline document shared by your instructor. Make sure to check the learning outcomes — they tell you exactly what you'll be assessed on.",
        "Planning your {course} study schedule early is a great habit! Allocate more time to topics you find challenging. If you share which topics you're unsure about, I can give more targeted advice.",
    ],
}

FALLBACK = (
    "I don't have enough information on that in my current knowledge base for {course}. "
    "Please try rephrasing your question, or consider asking your instructor or checking the course portal."
)


async def get_dummy_response(message: str, course: str) -> tuple[str, float, str]:
    """
    Return a context-aware dummy response based on keywords in the message.
    Simulates processing delay of 0.5–1.0 second.

    Returns:
        (reply, confidence, source)
    """
    delay = random.uniform(0.5, 1.0)
    await asyncio.sleep(delay)

    msg_lower = message.lower()
    reply = None
    confidence = 0.0
    source = "dummy_knowledge_base"

    if any(kw in msg_lower for kw in ["what", "explain", "how", "define", "why", "describe"]):
        reply = random.choice(RESPONSES["explain_how_what_define"]).format(course=course)
        confidence = round(random.uniform(0.78, 0.95), 2)

    elif any(kw in msg_lower for kw in ["exam", "test", "quiz", "midterm", "final"]):
        reply = random.choice(RESPONSES["exam_test_quiz"]).format(course=course)
        confidence = round(random.uniform(0.82, 0.97), 2)

    elif any(kw in msg_lower for kw in ["assignment", "homework", "project", "task", "submission"]):
        reply = random.choice(RESPONSES["assignment_homework_project"]).format(course=course)
        confidence = round(random.uniform(0.75, 0.92), 2)

    elif any(kw in msg_lower for kw in ["syllabus", "topics", "schedule", "outline", "curriculum", "plan"]):
        reply = random.choice(RESPONSES["syllabus_topics_schedule"]).format(course=course)
        confidence = round(random.uniform(0.80, 0.94), 2)

    else:
        reply = FALLBACK.format(course=course)
        confidence = round(random.uniform(0.20, 0.45), 2)
        source = "fallback"

    return reply, confidence, source

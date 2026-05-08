import re
from typing import Iterable, Optional

COURSE_CODE_RE = re.compile(r"\b([A-Z]{2,4})[\s_-]?(\d{3})\b", re.IGNORECASE)

DEFAULT_COURSE_MAP = {
    "CSE220": "CSE220_Data_Structure",
    "CSE221": "CSE221_Algorithm",
    "CSE340": "CSE340_Computer_Architecture",
    "CSE341": "CSE341_Microprocessors",
    "CSE422": "CSE422_Artificial_Intelligence",
    "CSE423": "CSE423_Computer_Graphics",
    "CSE440": "CSE440_NLP",
    "CSE470": "CSE470_System_Design_and_Analysis",
    "CSE471": "CSE471_Software_Engineering",
    "HST103": "HST103_History_of_Bangladesh",
}


def normalize_course_code(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    match = COURSE_CODE_RE.search(value.strip())
    if match:
        return f"{match.group(1).upper()}{match.group(2)}"

    compact = re.sub(r"[\s_-]+", "", value.strip().upper())
    return compact or None


def detect_course_code(text: Optional[str]) -> Optional[str]:
    if not text:
        return None

    match = COURSE_CODE_RE.search(text)
    if not match:
        return None

    return f"{match.group(1).upper()}{match.group(2)}"


def strip_course_code(text: str) -> str:
    stripped = COURSE_CODE_RE.sub("", text)
    stripped = re.sub(r"\s+([?.!,])", r"\1", stripped)
    stripped = re.sub(r"\b(in|from|for|of)\s*([?.!,])", r"\2", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"\b(in|from|for|of)\s*$", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"\s+([?.!,])", r"\1", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    return stripped or text


def resolve_course_name(
    requested_course: Optional[str],
    available_courses: Optional[Iterable[str]] = None,
) -> Optional[str]:
    if not requested_course:
        return None

    requested = requested_course.strip()
    requested_code = normalize_course_code(requested)

    if available_courses:
        courses = [course for course in available_courses if course]

        for course in courses:
            if course == requested:
                return course

        for course in courses:
            course_code = normalize_course_code(course)
            if requested_code and course_code == requested_code:
                return course
            if requested_code and course.upper().startswith(requested_code):
                return course

    if requested in DEFAULT_COURSE_MAP.values():
        return requested

    if requested_code:
        return DEFAULT_COURSE_MAP.get(requested_code)

    return None


def detect_course(question: str) -> Optional[str]:
    """Backward-compatible helper returning the resolved default course name."""
    return resolve_course_name(detect_course_code(question))

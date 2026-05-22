"""
core/router.py — Fast Rule-Based Router

Intercepts obvious commands BEFORE they reach the LLM.
Simple commands like "open spotify" become instant.
"""
import re
from core.intent import Intent

RULES = [
    # Workflows — specific first
    (r"\b(start|begin|enable|activate|launch)\b.*(coding|code)",   "run_workflow", "coding_mode"),
    (r"\b(start|begin|enable|activate|launch)\b.*(study|studies)", "run_workflow", "study_mode"),
    (r"\bstudy\s+mode\b",                                          "run_workflow", "study_mode"),
    (r"\bcoding\s+mode\b",                                         "run_workflow", "coding_mode"),
    (r"\bmorning\s+routine\b",                                     "run_workflow", "morning_routine"),
    (r"\bfocus\s+mode\b",                                          "run_workflow", "focus_mode"),
    (r"\binternship\s+(hunt|mode|search)\b",                       "run_workflow", "internship_hunt"),
    (r"\bentertainment\s+mode\b",                                  "run_workflow", "entertainment_mode"),

    # Screenshot
    (r"\b(take|grab|capture)\b.*(screenshot|screen shot)\b",       "take_screenshot", None),
    (r"\bscreenshot\b",                                            "take_screenshot", None),

    # Read screen
    (r"\b(read|describe|what.s on|whats on)\b.*screen\b",         "read_screen", None),

    # Web search
    (r"\b(search|google|look up|find)\b\s+(for\s+)?(.+)",         "web_search", None),

    # Open app
    (r"\bopen\s+(\w+)\b",                                         "open_app", None),

    # Close app
    (r"\bclose\s+(\w+)\b",                                        "close_app", None),

    # Type text
    (r"\btype\s+(.+)",                                            "type_text", None),
]


def fast_route(text: str) -> Intent | None:
    t = text.lower().strip()

    for pattern, action, target in RULES:
        match = re.search(pattern, t)
        if not match:
            continue

        if action == "run_workflow":
            return Intent(action=action, target=target, confidence=1.0)

        elif action == "take_screenshot":
            return Intent(action=action, confidence=1.0)

        elif action == "read_screen":
            return Intent(action=action, confidence=1.0)

        elif action == "web_search":
            query = match.group(3) if match.lastindex and match.lastindex >= 3 else text
            return Intent(action=action, query=query.strip(), confidence=1.0)

        elif action == "open_app":
            return Intent(action=action, target=match.group(1).strip(), confidence=1.0)

        elif action == "close_app":
            return Intent(action="close_app", target=match.group(1).strip(), confidence=1.0)

        elif action == "type_text":
            return Intent(action=action, query=match.group(1).strip(), confidence=1.0)

    return None
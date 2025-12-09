"""
Authors: Erik Bailey, Team Alpha fall 2025
Contributers: Jackie
Date 12/1/2025
Email Detector
=========================================
Detects instructor email addresses in syllabus documents.
Prefers emails near typical headings; falls back to first valid email.

We basically look for unh emails (@unh.edu, @ wildcats.unh.edu)
notably, you should modify this to exclude certain emails that belong to specific departments at UNH, as they are always
on a syllabus and may get picked up accidentally.
"""

import re
import logging
from typing import Dict, Any, Optional, List

# Detection Configuration
MAX_HEADING_SCAN_LINES = 150
MAX_HEADER_CHARS = 1200
EMAIL_CONFIDENCE_SCORE = 0.95

EMAIL_RX = re.compile(
    r"[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)*@(?:unh|usnh)\.edu"
)

# Heading keywords to look for (will be normalized during search)
HEADING_CLUES = [
    "email", "e-mail", "contact", "contact information",
    "preferred contact method", "instructor", "professor"
]


class EmailDetector:
    def __init__(self):
        self.field_name = 'email'
        self.logger = logging.getLogger('detector.email')

    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        Normalize text for consistent matching.
        Handles:
        - Lowercasing
        - Unicode punctuation (full-width colon, em-dash, etc.)
        - Extra whitespace
        """
        if not text:
            return ""

        # Lowercase first
        normalized = text.lower()

        # Replace Unicode punctuation with ASCII equivalents
        # Full-width colon, em-dash, en-dash, etc.
        normalized = normalized.replace('：', ':')  # Full-width colon
        normalized = normalized.replace('—', '-')  # Em-dash
        normalized = normalized.replace('–', '-')  # En-dash
        normalized = normalized.replace('\u2014', '-')  # Em-dash (unicode)
        normalized = normalized.replace('\u2013', '-')  # En-dash (unicode)

        # Normalize whitespace (multiple spaces -> single space)
        normalized = ' '.join(normalized.split())

        return normalized

    def detect(self, text: str) -> Dict[str, Any]:
        self.logger.info("Starting detection for field: email")

        if not text:
            return self._not_found()

        # 1) Try: scan first N lines for heading + email on the same/next line
        lines = text.splitlines()
        window_lines = lines[:MAX_HEADING_SCAN_LINES] if len(lines) > MAX_HEADING_SCAN_LINES else lines
        candidate = self._find_near_heading(window_lines)
        if candidate:
            email = candidate
            method = "heading_window"
        else:
            # 2) Try: any valid email in the first N chars (header area)
            header = text[:MAX_HEADER_CHARS]
            header_emails = EMAIL_RX.findall(header)
            if header_emails:
                email = header_emails[0]
                method = "header_any"
            else:
                # 3) Fallback: first valid email anywhere in the doc
                all_emails = EMAIL_RX.findall(text)
                if all_emails:
                    email = all_emails[0]
                    method = "fallback_any"
                else:
                    return self._not_found()

        # Exclude specific emails at the very end
        if email in {"Janessa.zurek@unh.edu", "sas.office@unh.edu", "unhm.studentdevelopment@unh.edu"}:
            return self._not_found()
        return self._found(email, method=method)

    # ---------------- helpers ----------------

    def _find_near_heading(self, lines: List[str]) -> Optional[str]:
        """Find an email on a line that contains a clue word, or the next line."""
        for i, raw in enumerate(lines):
            line = raw.strip()
            # Normalize the line for comparison
            normalized_line = self._normalize_text(line)

            # Check if any heading clue appears in the normalized line
            if any(self._normalize_text(clue) in normalized_line for clue in HEADING_CLUES):
                # same line (search in original, not normalized)
                m = EMAIL_RX.search(line)
                if m:
                    return m.group(0)
                # next line
                if i + 1 < len(lines):
                    m2 = EMAIL_RX.search(lines[i+1])
                    if m2:
                        return m2.group(0)
        return None

    def _found(self, content: str, method: str) -> Dict[str, Any]:
        """Return found result with email as string (consistent with other detectors)."""
        self.logger.info(f"FOUND: email via {method}")
        return {
            "field_name": self.field_name,
            "found": True,
            "content": content,
            "confidence": EMAIL_CONFIDENCE_SCORE,
            "metadata": {"method": method}
        }

    def _not_found(self) -> Dict[str, Any]:
        self.logger.info("NOT_FOUND: email")
        return {
            "field_name": self.field_name,
            "found": False,
            "content": "Missing",
            "confidence": 0.0,
            "metadata": {}
        }

if __name__ == "__main__":
    # Test cases (avoiding Unicode in console output for Windows compatibility)
    test_cases = [
        ("Email: jane.doe@unh.edu", "Standard email with colon"),
        ("E-mail: john.smith@unh.edu", "E-mail variant"),
        ("Contact   :   test@unh.edu", "Extra spaces around colon"),
        ("Instructor\nEmail: prof@unh.edu", "Email on next line"),
    ]

    detector = EmailDetector()
    print("Testing Email Detector:")
    print("=" * 60)
    for test_text, description in test_cases:
        result = detector.detect(test_text)
        print(f"\nTest: {description}")
        print(f"Found: {result.get('found')}")
        print(f"Email: {result.get('content')}")
        print(f"Method: {result.get('metadata', {}).get('method')}")
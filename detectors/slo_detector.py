"""
Student Learning Outcomes (SLO) Detector

Finds Student Learning Outcomes sections in syllabi.
Examples: "Student Learning Outcomes", "Learning Objectives", "SLOs"

Business Rule: Only "Student Learning" or "Learning" titles are valid.
"Course Objectives" and "Course Goals" are NOT valid SLO sections.

How it works:
1. Searches for approved SLO titles (Student Learning Outcomes, etc.)
2. Validates title appears as section header (not in sentence)
3. Scores matches based on header characteristics
4. Extracts content following the highest-scoring match
5. Returns title + content or "Missing" if not found

Example:
    Input: "Student Learning Outcomes:\n- Understand key concepts\n- Apply knowledge"
    Output: "Student Learning Outcomes:\n- Understand key concepts\n- Apply knowledge"
"""

import re
import logging
from typing import Dict, Any, Tuple


class SLODetector:
    """Detects Student Learning Outcomes in syllabi"""

    # Document processing limits
    MAX_DOCUMENT_LENGTH = 20000  # Prevent hanging on large files
    MAX_CONTENT_LINES = 10       # Lines to extract after title
    MAX_CONTENT_LENGTH = 500     # Max characters to extract

    # Scoring weights for header detection
    SCORE_STARTS_WITH_TITLE = 10    # Title at start of line
    SCORE_SHORT_LINE = 5            # Short line (likely header)
    SCORE_LONG_LINE_PENALTY = -5    # Long line (likely sentence)
    SCORE_HAS_COLON = 3             # Has colon (section header)
    SCORE_ALL_CAPS = 2              # All caps (section header)
    MIN_SCORE_THRESHOLD = 5         # Minimum score to accept

    # Line length thresholds
    SHORT_LINE_THRESHOLD = 50       # Short line cutoff
    LONG_LINE_THRESHOLD = 100       # Long line cutoff
    MAX_EXTRA_WORDS_HEADER = 2      # Max extra words in short title
    MAX_EXTRA_WORDS_START = 4       # Max extra words when title at start
    MAX_EXTRA_WORDS_END = 3         # Max extra words when title at end

    # Section headers that indicate end of SLO content
    SECTION_HEADERS = [
        'course description', 'course objectives', 'course goals',
        'prerequisites', 'textbook', 'grading', 'schedule'
    ]

    def __init__(self):
        """Initialize with strict business rules for valid SLO titles"""
        self.field_name = 'slos'
        self.logger = logging.getLogger('detector.slos')

        # STRICT BUSINESS RULE: Only these titles are valid SLO sections
        # Must contain "Student Learning" or just "Learning" (without "Course")
        # "Course Objectives" and "Course Goals" are NOT valid
        self.approved_titles = [
            "student learning outcomes",
            "student learning outcome",
            "student learning objectives",
            "student learning objective",
            "student/program learning outcomes",
            "learning outcomes",
            "learning outcome",
            "learning objectives",
            "learning objective"
        ]

        # Abbreviated forms
        self.approved_abbreviations = [
            "slos",
            "slo"
        ]

    def detect(self, text: str) -> Dict[str, Any]:
        """
        Detect Student Learning Outcomes in syllabus.
        
        Returns dict with:
            - 'field_name': 'slos'
            - 'found': bool
            - 'content': SLO text or 'Missing'
        """
        self.logger.info("Starting SLO detection")

        # Limit text size to prevent hanging
        original_length = len(text)
        if len(text) > self.MAX_DOCUMENT_LENGTH:
            text = text[:self.MAX_DOCUMENT_LENGTH]
            self.logger.info(f"Truncated document from {original_length} to {self.MAX_DOCUMENT_LENGTH} chars")

        try:
            found, content = self._simple_title_detection(text)

            if found:
                result = {
                    'field_name': self.field_name,
                    'found': True,
                    'content': content
                }
                self.logger.info(f"FOUND: {self.field_name}")
            else:
                result = {
                    'field_name': self.field_name,
                    'found': False,
                    'content': 'Missing'
                }
                self.logger.info(f"NOT_FOUND: {self.field_name}")

            return result

        except Exception as e:
            self.logger.error(f"Error in SLO detection: {e}")
            return {
                'field_name': self.field_name,
                'found': False,
                'content': 'Missing'
            }

    def _simple_title_detection(self, text: str) -> Tuple[bool, str]:
        """
        Find approved SLO titles and extract content.
        
        Validation:
        - Title must appear as section header (not in sentence)
        - Three valid formats:
          1. Very short line with proper formatting
          2. Title at start with colon or short line
          3. Title at end if short line
        
        Returns:
            tuple: (found, content)
        """
        lines = text.split('\n')
        potential_matches = []

        for i, line in enumerate(lines):
            line_normalized = line.strip().lower()
            line_without_punctuation = line_normalized.replace(':', '').replace('.', '').strip()

            # Check if line contains approved title
            contains_approved_title = False
            for title in self.approved_titles:
                if title in line_without_punctuation:
                    line_words = line_without_punctuation.split()
                    title_words = title.split()

                    # Validate it's a header (not just mentioned in text)
                    is_valid_header = False

                    # Case 1: Very short line (title + max 2 extra words)
                    if len(line_words) <= len(title_words) + self.MAX_EXTRA_WORDS_HEADER:
                        has_proper_formatting = (
                            ':' in line or
                            line.strip().isupper() or
                            (len(line_words) == len(title_words) and
                             not line_normalized.endswith((',', ';', '.', '!', '?')))
                        )
                        if has_proper_formatting:
                            is_valid_header = True

                    # Case 2: Title at start (with colon or short)
                    elif line_without_punctuation.startswith(title):
                        if ':' in line or len(line_words) <= len(title_words) + self.MAX_EXTRA_WORDS_START:
                            is_valid_header = True

                    # Case 3: Title at end (if short line)
                    elif line_without_punctuation.endswith(title):
                        if len(line_words) <= len(title_words) + self.MAX_EXTRA_WORDS_END:
                            is_valid_header = True

                    if is_valid_header:
                        contains_approved_title = True
                        break

            if contains_approved_title:
                # Score this match
                score = 0

                # Check if starts with approved title
                starts_with_approved = False
                for title in self.approved_titles:
                    if line_without_punctuation.startswith(title):
                        starts_with_approved = True
                        break
                
                if starts_with_approved:
                    score += self.SCORE_STARTS_WITH_TITLE

                # Score based on line characteristics
                if len(line_without_punctuation) < self.SHORT_LINE_THRESHOLD:
                    score += self.SCORE_SHORT_LINE

                if len(line_without_punctuation) > self.LONG_LINE_THRESHOLD:
                    score += self.SCORE_LONG_LINE_PENALTY

                if ':' in line:
                    score += self.SCORE_HAS_COLON

                if line.strip().isupper():
                    score += self.SCORE_ALL_CAPS

                potential_matches.append((score, i, line))

        # Select best match
        if potential_matches:
            potential_matches.sort(key=lambda x: x[0], reverse=True)
            best_score, best_i, best_line = potential_matches[0]

            # Only accept if score is high enough
            if best_score < self.MIN_SCORE_THRESHOLD:
                return False, ""

            # Extract content after title
            title = best_line.strip()
            content_lines = [title]
            content_length = len(title)

            for j in range(best_i + 1, min(best_i + self.MAX_CONTENT_LINES, len(lines))):
                if j >= len(lines):
                    break

                next_line = lines[j].strip()
                if not next_line:
                    continue

                # Stop at next section header
                if any(section in next_line.lower() for section in self.SECTION_HEADERS):
                    break

                content_lines.append(next_line)
                content_length += len(next_line)

                # Stop after reasonable amount
                if content_length > self.MAX_CONTENT_LENGTH:
                    break

            content = '\n'.join(content_lines)
            return True, content

        return False, ""
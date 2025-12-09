"""
Workload Detector
=================

This detector identifies workload/engaged time declarations in syllabus documents.
It looks for patterns like:
- "minimum 3 hours of engaged time per week per credit"
- "45 hours of student academic work per credit per term"
- "12 hours/week (4 credits x 3 hours per credit)"
- "180 hours total student work"
- "expected to involve a minimum of X hours"

Developer Notes:
---------------
Detects workload expectations and time commitments for courses.
"""

import re
import logging
from typing import Dict, Any, Optional, Tuple

# Detection Configuration Constants
MAX_DOCUMENT_LENGTH = 30000


class WorkloadDetector:
    """
    Detector for workload/engaged time information in syllabus documents.

    This detector identifies workload expectations and time commitment declarations
    commonly found in academic syllabi. It searches for patterns describing:
    - Hours of engaged time per week per credit
    - Total hours of student work per term
    - Expected study hours outside of class
    - Minimum work hour requirements

    Attributes:
        field_name (str): The name of the field being detected ('workload').
        logger (logging.Logger): Logger instance for this detector.
        word_to_number (dict): Mapping of word numbers to digit strings.
        workload_patterns (list): List of regex patterns for workload detection.
    """

    def __init__(self):
        """
        Initialize the Workload detector.

        Sets up the field name, logger, word-to-number mappings, and compiles
        the list of regex patterns used to detect workload declarations.
        """
        self.field_name = 'workload'
        self.logger = logging.getLogger('detector.workload')

        # Word-to-number mapping
        self.word_to_number = {
            'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
            'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10'
        }

        # Patterns for workload declarations
        # Note: Order matters - more specific patterns should come first
        self.workload_patterns = [
            # "minimum of 3 hours of engaged time per week per credit over a 15-week semester"
            r'minimum\s+of\s+(\d+(?:-\d+)?)\s+hours?\s+of\s+engaged\s+time\s+per\s+week\s+per\s+credit\s+over\s+(?:a\s+)?(\d+)[-\s]+week\s+semester',

            # "minimum 3 hours of engaged time per week per credit over a 15-week semester"
            r'minimum\s+(\d+)\s+hours?\s+of\s+engaged\s+time\s+per\s+week\s+per\s+credit\s+over\s+(?:a\s+)?(\d+)[-\s]+week\s+semester',

            # "3 hours of engaged time per week per credit over a 15-week semester" (without "minimum")
            r'(\d+)\s+hours?\s+of\s+engaged\s+time\s+per\s+week\s+per\s+credit\s+over\s+(?:a\s+)?(\d+)[-\s]+week\s+semester',

            # "minimum of 3-4 hours per week for the completion of homework"
            r'minimum\s+of\s+(\d+(?:-\d+)?)\s+hours?\s+per\s+week\s+for\s+the\s+completion\s+of',

            # "12 hours of student academic work per week for a 15 week course"
            r'(\d+)\s+hours?\s+of\s+student\s+academic\s+work\s+per\s+week\s+for\s+(?:a\s+)?(\d+)[-\s]+week\s+course',

            # "minimum of 4 hours engaged time per week per credit"
            r'minimum\s+of\s+(\d+)\s+hours?\s+engaged\s+time\s+per\s+week\s+per\s+credit',

            # "minimum 3 hours engaged time per week per credit"
            r'minimum\s+(\d+)\s+hours?\s+engaged\s+time\s+per\s+week\s+per\s+credit',

            # "three hours of student academic work and engagement each week" (word numbers)
            r'(three|four|five|six|seven|eight|nine|ten|one|two)\s+hours?\s+of\s+student\s+academic\s+work\s+and\s+engagement\s+each\s+week',

            # "three hours of student academic work each week" (word numbers)
            r'(three|four|five|six|seven|eight|nine|ten|one|two)\s+hours?\s+of\s+student\s+academic\s+work\s+each\s+week',

            # "minimum of 180 hours of total student work"
            r'minimum\s+of\s+(\d+)\s+hours?\s+of\s+total\s+student\s+work',

            # "minimum of three hours of student academic work" (with word numbers)
            r'minimum\s+of\s+(three|four|five|six|seven|eight|nine|ten|one|two)\s+hours?\s+(?:of\s+)?student\s+academic\s+work',

            # "minimum of three hours of academic work each week for each credit hour"
            r'minimum\s+of\s+(three|four|five|six|seven|eight|nine|ten|one|two|\d+)\s+hours?\s+(?:of\s+)?academic\s+work\s+each\s+week\s+for\s+each\s+credit',

            # "45 hours of student academic work per credit per term"
            r'(\d+)\s+hours?\s+(?:of\s+)?(?:student\s+)?academic\s+work\s+per\s+credit',

            # "45 hours of course work per credit"
            r'(\d+)\s+hours?\s+(?:of\s+)?course\s+work\s+per\s+credit',

            # "expected to involve a minimum of X hours"
            r'expected\s+to\s+involve\s+a\s+minimum\s+of\s+(\d+)\s+hours?',

            # "expected to spend a minimum of X hours each week on their academic work"
            r'expected\s+to\s+spend\s+a\s+minimum\s+of\s+(\d+)\s+hours?\s+each\s+week\s+on\s+their\s+academic\s+work',

            # "expected to spend at least X hours per week on this class"
            r'expected\s+to\s+spend\s+at\s+least\s+(\d+)\s+hours?\s+per\s+week\s+on\s+this\s+class',

            # "You are expected to study at least X hours outside class every week" (very common!)
            r'expected\s+to\s+study\s+at\s+least\s+(\d+(?:-\d+)?)\s+hours?\s+outside\s+(?:of\s+)?class\s+every\s+week',

            # "You are expected to study at least X hours outside class" (without "every week")
            r'expected\s+to\s+study\s+at\s+least\s+(\d+(?:-\d+)?)\s+hours?\s+outside\s+(?:of\s+)?class',

            # "You are expected to study X hours outside class every week" (without "at least")
            r'expected\s+to\s+study\s+(\d+(?:-\d+)?)\s+hours?\s+outside\s+(?:of\s+)?class\s+every\s+week',

            # "expected to at least study X hours outside class" (different word order)
            r'expected\s+to\s+at\s+least\s+study\s+(\d+(?:-\d+)?)\s+hours?\s+outside\s+(?:of\s+)?class',

            # "expected to allocate X to Y hours outside of class"
            r'expected\s+to\s+allocate\s+(\d+)\s+to\s+(\d+)\s+hours?\s+outside\s+(?:of\s+)?class',

            # "You are expected to engage in outside class learning X hours every week"
            r'expected\s+to\s+engage\s+in\s+outside\s+class\s+learning\s+(\d+)\s+hours\s+every\s+week',

            # "You are expected to engage in outside class learning X hours" (without every week)
            r'expected\s+to\s+engage\s+in\s+outside\s+class\s+learning\s+(\d+)\s+hours',

            # "minimum of 180 hours in a professional setting"
            r'minimum\s+of\s+(\d+)\s+hours?\s+in\s+a\s+professional\s+setting',

            # "complete the minimal X hours of onsite work"
            r'complete\s+the\s+minim(?:al|um)\s+(\d+)\s+hours?\s+(?:of\s+)?(?:onsite|on-site)\s+work',

            # "X hours per week for graduate students" or "X hours per week"
            r'(\d+)\s+hours?\s+per\s+week(?:\s+for\s+(?:graduate|undergraduate)\s+students)?',

            # "1 credit = 3 hours of academic work per week"
            r'(\d+)\s+credit\s*=\s*(\d+)\s+hours?\s+(?:of\s+)?academic\s+work\s+per\s+week',

            # "X work hours for Y credits" or "X hours for Y credit"
            r'(\d+)\s+(?:work\s+)?hours?\s+for\s+(\d+)\s+credits?',

            # "12 hours/week (4 credits x 3 hours per credit)" - this should be lower priority
            r'(\d+)\s+hours?/week\s*\([^)]*credits?\s*x\s*\d+\s+hours?\s+per\s+credit[^)]*\)',
        ]

    def detect(self, text: str) -> Dict[str, Any]:
        """
        Detect workload declarations in the text.

        Args:
            text (str): Document text to analyze

        Returns:
            Dict[str, Any]: Detection result with workload if found
        """
        self.logger.info("Starting Workload detection")

        # Limit text size
        if len(text) > MAX_DOCUMENT_LENGTH:
            text = text[:MAX_DOCUMENT_LENGTH]

        try:
            # Look for workload mentions
            found, workload_text = self._find_workload(text)

            if found:
                result = {
                    'field_name': self.field_name,
                    'found': True,
                    'content': workload_text
                }
                self.logger.info(f"FOUND: {workload_text}")
            else:
                result = {
                    'field_name': self.field_name,
                    'found': False,
                    'content': None
                }
                self.logger.info("NOT_FOUND: No workload declaration")

            return result

        except Exception as e:
            self.logger.error(f"Error in Workload detection: {e}")
            return {
                'field_name': self.field_name,
                'found': False,
                'content': None
            }

    def _find_workload(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Find workload declarations in text.

        Args:
            text (str): Text to search

        Returns:
            Tuple[bool, Optional[str]]: (found, workload_text)
        """
        # Clean up text: normalize whitespace and remove special characters
        # First, normalize various dash/hyphen characters to standard hyphen
        cleaned_text = text
        # Unicode dashes: en-dash, em-dash, hyphen, non-breaking hyphen, figure dash, etc.
        cleaned_text = re.sub(r'[\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFE58\uFE63\uFF0D]', '-', cleaned_text)
        # Replace newlines with spaces
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        # Remove remaining special characters like bullets, diamonds, etc.
        cleaned_text = re.sub(r'[^\x00-\x7F]+', ' ', cleaned_text)

        # Collect all potential matches with their positions and pattern index
        candidates = []

        # Generic boilerplate patterns (UNH policy text) - these should be deprioritized
        # These patterns often appear in syllabi as policy text, not course-specific workload
        generic_patterns = {
            r'(\d+)\s+hours?\s+(?:of\s+)?(?:student\s+)?academic\s+work\s+per\s+credit',
            r'(\d+)\s+hours?\s+(?:of\s+)?course\s+work\s+per\s+credit',
            r'(\d+)\s+credit\s*=\s*(\d+)\s+hours?\s+(?:of\s+)?academic\s+work\s+per\s+week',
            r'(three|four|five|six|seven|eight|nine|ten|one|two)\s+hours?\s+of\s+student\s+academic\s+work\s+each\s+week',
        }

        for pattern_idx, pattern in enumerate(self.workload_patterns):
            is_generic = pattern in generic_patterns
            for match in re.finditer(pattern, cleaned_text, re.IGNORECASE):
                full_match = match.group(0).strip()
                position = match.start()

                # Add to candidates with (is_generic, position, pattern_idx, match)
                # Non-generic patterns (is_generic=False=0) sort before generic (is_generic=True=1)
                candidates.append((is_generic, position, pattern_idx, full_match))
                self.logger.debug(f"Found potential workload: {full_match} at position {position} (generic={is_generic})")

        # If we found candidates, prefer non-generic patterns, then earliest position
        if candidates:
            candidates.sort(key=lambda x: (x[0], x[1]))  # Sort by is_generic, then position
            is_generic, position, pattern_idx, best_match = candidates[0]
            self.logger.info(f"Found workload declaration: {best_match} (generic={is_generic})")
            return True, best_match

        return False, None

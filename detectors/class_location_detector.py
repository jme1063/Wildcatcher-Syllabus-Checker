"""
Class Location Detector
=========================================

This detector identifies class meeting locations including:
- Online/Remote/Virtual locations (e.g., "Online", "Zoom", "Canvas", "Remote")
- Physical classroom locations (e.g., "Room 105", "Pandora 380")
- Appointment-based locations (e.g., "By appointment")

Priority order:
1. Online/Remote/Virtual patterns (highest priority)
2. Appointment-based patterns
3. Physical room locations (if not online/remote)

Examples of detected formats:
- "Online", "Remote through Zoom", "Canvas", "UNH MyCourses"
- "By appointment (in-person or remote)"
- "Room 105", "Rm 139, Pandora Mill building"
- "Hamilton Smith 129", "P380"
- "Classroom: 302"
"""

import re
import logging
import unicodedata
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

# Detection Configuration Constants
MAX_LINES_TO_SCAN = 150
CONTEXT_WINDOW_BEFORE = 2
CONTEXT_WINDOW_AFTER = 15  # Increased from 5 to handle form layouts with large gaps
HEADER_LINE_THRESHOLD = 20  # Lines considered part of header section
HEADER_CONFIDENCE_BOOST = 0.15  # Boost for locations in header
EXPLICIT_KEYWORD_BOOST = 0.25  # Boost for explicit location keywords (higher than header)

# Confidence levels
HIGH_CONFIDENCE = 0.95
MEDIUM_CONFIDENCE = 0.85
LOW_CONFIDENCE = 0.70


class ContextType(Enum):
    """Enumeration for context types to avoid magic strings."""
    CLASS = 'class'
    OFFICE = 'office'
    NEUTRAL = 'neutral'


@dataclass
class LocationCandidate:
    """Data class for location candidates to improve maintainability."""
    location: str
    confidence: float
    line_idx: int
    context_type: ContextType
    has_explicit_label: bool


class ClassLocationDetector:
    """
    Detector for physical class meeting locations.

    This detector looks for:
    - Physical locations: "Room 105", "Pandora Mill Rm 139", "Hamilton Smith 129"
    - Classroom designations: "Classroom: 302", "P380"

    Uses advanced disambiguation to distinguish between:
    - Class meeting location (what we want)
    - Office hours location (reject)
    - Instructor office location (reject)
    - Support/admin offices (reject)
    """

    def __init__(self):
        """Initialize the class location detector with disambiguation rules."""
        self.field_name = 'class_location'
        self.logger = logging.getLogger('detector.class_location')

        # ONLINE/REMOTE/VIRTUAL location patterns (checked FIRST before physical rooms)
        # These patterns detect online/remote course locations with high confidence
        # IMPORTANT: Only match when there's an explicit location label to avoid false positives
        self.online_location_patterns = [
            # Pattern 1: Simple "Online" after location label (most common)
            # Include standalone "Location:" label
            # Allow periods in text to handle cases like "Tuesday 1:10pm-4pm. Online"
            (re.compile(r'(?:time\s+and\s+location|location\s+and\s+time|class\s+location|meeting\s+location|class\s+meetings?|^location)[\s:]+[^\n]{0,100}?\b(online)\b',
                       re.IGNORECASE | re.MULTILINE), 0.98),

            # Pattern 1b: "Course Format: Online" or "Meeting Times/Locations" + "online asynchronous"
            (re.compile(r'(?:course\s+format|class\s+format|modality)[\s:]+[^\n]{0,50}?\b(online(?:\s+asynchronous)?)',
                       re.IGNORECASE), 0.98),
            (re.compile(r'meeting\s+times?/locations?[^\n]{0,200}?\b(online\s+asynchronous)',
                       re.IGNORECASE), 0.98),
            # Pattern 1c: Time info followed by pipe/bar and "Online" (e.g., "Wed, 6:10-9:00 PM | Online, Synchronous")
            (re.compile(r'(?:mon|tue|wed|thu|fri|sat|sun)[^\n]{0,50}?\|\s*(online(?:,?\s+synchronous)?)',
                       re.IGNORECASE), 0.98),
            # Pattern 1d: Standalone "Asynchronous online" (handles reversed order)
            (re.compile(r'\b(asynchronous\s+online)\b', re.IGNORECASE), 0.98),
            # Pattern 1e: "As an online class/course" format
            (re.compile(r'(?:as|is)\s+an?\s+(online\s+(?:class|course))', re.IGNORECASE), 0.98),

            # Pattern 2: "Online" with context in parentheses
            (re.compile(r'(?:time\s+and\s+location|location\s+and\s+time|class\s+location|meeting\s+location|where|^location)[\s:]+[^\n]{0,50}?\b(online\s*\([^)]{0,100}\))',
                       re.IGNORECASE | re.MULTILINE), 0.98),

            # Pattern 3: Remote with context
            (re.compile(r'(?:time\s+and\s+location|location\s+and\s+time|class\s+location|meeting\s+location|where|^location)[\s:]+[^\n]{0,50}?\b(remote(?:\s+through\s+zoom)?)',
                       re.IGNORECASE | re.MULTILINE), 0.98),

            # Pattern 4: Canvas/MyCourses with "online" context
            (re.compile(r'\b(canvas\s*\([^)]*(?:online|learning\s+management\s+system|my\s+courses)[^)]*\))',
                       re.IGNORECASE), 0.98),
            (re.compile(r'\b((?:unh\s+)?mycourses\s*\([^)]*online[^)]*\))',
                       re.IGNORECASE), 0.98),
            # Pattern for "use/will use UNH MyCourses"
            (re.compile(r'(?:students?\s+)?(?:will\s+)?use\s+((?:unh\s+)?mycourses)',
                       re.IGNORECASE), 0.98),
            # CPRM-style: "in Canvas, our learning management system (LMS)"
            # Special marker pattern - will be handled specially in code
            (re.compile(r'\basynchronous(?:ly)?\s+online[^\n]{0,100}?\bin\s+(canvas)[,\s]+(?:our\s+)?learning\s+management\s+system',
                       re.IGNORECASE), 0.98),
            # Broader Canvas LMS pattern: "Canvas is the learning management system"
            (re.compile(r'\b(canvas)\s+is\s+(?:the\s+)?learning\s+management\s+system',
                       re.IGNORECASE), 0.98),
            # Pattern for "online course" + "course site on Canvas"
            (re.compile(r'(?:in\s+this|this\s+is\s+an?)\s+online\s+course[^\n]{0,100}?\bcourse\s+site\s+on\s+(canvas)',
                       re.IGNORECASE), 0.98),

            # Pattern 5: Zoom/Teams in location field
            (re.compile(r'(?:location|where)[\s:]+[^\n]{0,50}?\b((?:remote\s+)?\(?\s*zoom\s*\))',
                       re.IGNORECASE), 0.95),

            # Pattern 5b: Zoom/online platform used for class meetings
            # Capture "online" when Zoom is mentioned for online meetings
            (re.compile(r'\b(?:zoom|teams)\s+used\s+to\s+hold\s+(?:weekly\s+)?(online)\s+class\s+meetings?',
                       re.IGNORECASE), 0.98),
            (re.compile(r'(?:location|where)[\s:]+[^\n]{0,50}?\b(zoom/teams[^\n]{0,60})',
                       re.IGNORECASE), 0.95),

            # Pattern 6: "By appointment" (for thesis/project courses)
            (re.compile(r'(?:location|where)[\s:]+[^\n]{0,30}?\b(by\s+appointment(?:\s+\([^)]{0,60}\))?)',
                       re.IGNORECASE), 0.95),

            # Pattern 7: Hybrid patterns
            (re.compile(r'(?:location|where|modality)[\s:]+[^\n]{0,50}?\b(hybrid[^\n]{0,100})',
                       re.IGNORECASE), 0.93),

            # Pattern 8: TBD with remote indicator
            (re.compile(r'\b(tbd\s*\(\s*remote\s*\))',
                       re.IGNORECASE), 0.92),

            # Pattern 9: Field sites
            (re.compile(r'(?:location|where)[\s:]+[^\n]{0,30}?\b(field\s+sites?[^\n]{0,80})',
                       re.IGNORECASE), 0.90),

            # Pattern 10: Zoom room provided in Canvas
            (re.compile(r'\b(zoom\s+room\s+provided\s+in\s+canvas)',
                       re.IGNORECASE), 0.95),
        ]

        # POSITIVE indicators: class location section keywords
        self.class_location_keywords = [
            r'class\s+location',
            r'class\s+meets?',
            r'class\s+meeting',
            r'meeting\s+location',
            r'meeting\s+place',
            r'meeting\s+time\s+and\s+place',
            r'location\s+and\s+time',
            r'time\s+and\s+location',
            r'where\s+we\s+meet',
            r'where\s+the\s+class\s+meets',
            r'course\s+location',
            r'course\s+room',
            r'lecture\s+location',
            r'when\s+and\s+where',
            r'schedule\s+and\s+location',
            r'classroom',
            r'lecture\s+room',
            r'\(lecture[;,]',  # "(Lecture;" or "(Lecture," indicates class context
        ]

        # NEGATIVE indicators: non-class location contexts (REJECT these)
        self.non_class_keywords = [
            r'office\s+hours?',
            r'office\s+location',
            r'instructor\s+office',
            r'professor\s+office',
            r'my\s+office',
            r'office\s+address',
            r'\boffice:',  # Simple "Office:" label
            r'instructor\s+location',
            r'contact\s+information',
            r'contact\s+info',
            r'tutoring\s+center',
            r'writing\s+center',
            r'help\s+center',
            r'support\s+center',
            r'academic\s+support',
            r'drop[-\s]in\s+hours',
            r'consultation\s+hours',
            r'availability',
            r'\blab:',  # Lab location (different from class)
            r'lab\s+location',
            r'lab\s+sessions?',
            # Support/Admin offices
            r'tech\s+consultancy',
            r'tech\s+consultant',
            r'workroom',
            r'student\s+tech',
            r'title\s+ix',
            r'deputy\s+intake',
            r'coordinator.*room',
            r'advisors?\s+office',
            r'loan.*laptop',
            r'borrow.*laptop',
        ]

        # PRE-COMPILED regex patterns for performance (compiled once at init)
        self.course_code_patterns = [
            re.compile(r'\b[A-Z]{2,4}\s+\d{3,4}[A-Z]?\b'),  # COMP 405, BIOL 413A
            re.compile(r'\b[A-Z]{2,4}-\d{3,4}[A-Z]?\b'),    # COMP-405
            re.compile(r'\b[A-Z]{2,4}\d{3,4}[A-Z]?\b'),     # COMP405
        ]

        # PRE-COMPILED room extraction patterns (performance optimization)
        # Format: (compiled_pattern, confidence_level)
        self.room_patterns = [
            # Pattern 0: Explicit class meeting formats "in ROOM" or "Section X: ... Room Y"
            (re.compile(r'\b(?:class\s+meetings?|section\s+\w+).*?\b((?:in|room|rm\.?)\s+[A-Za-z]?\d{2,4})\b', re.IGNORECASE | re.DOTALL),
             HIGH_CONFIDENCE + 0.01),  # Slightly higher than other high confidence

            # Pattern 0b: "Course Room Number: X" format
            (re.compile(r'\bcourse\s+room\s+(?:number)?[\s:]+([A-Za-z]?\d{2,4})\b', re.IGNORECASE),
             HIGH_CONFIDENCE + 0.01),

            # Pattern 1: "Room/Rm [Number]" possibly followed by building
            (re.compile(r'\b((?:room|rm\.?)\s+[A-Za-z]?\d{2,4}(?:\s*[,\-]?\s*[\w\s]+?(?:hall|building|bldg|mill|lab))?)\b', re.IGNORECASE),
             HIGH_CONFIDENCE),

            # Pattern 2: Known building name followed by room number
            # Allow parenthetical content like "(UNHM)" between building and room
            (re.compile(r'\b((?:pandora|pandra|hamilton\s+smith|dimond|parsons|kingsbury|morse|rudman|murkland)'
                       r'(?:\s+mill|\s+hall|\s+building|\s+lab)?(?:\s*\([^)]{1,20}\))?\s*[,\-]?\s*(?:room|rm\.?)?\s*[A-Za-z]?\d{2,4})\b', re.IGNORECASE),
             HIGH_CONFIDENCE),

            # Pattern 3: Just "Room [Number]" or "Rm [Number]"
            (re.compile(r'\b((?:room|rm\.?)\s+[A-Za-z]?\d{2,4})\b', re.IGNORECASE),
             LOW_CONFIDENCE),

            # Pattern 4: "Classroom: [Number]" or "Classroom [Number]"
            (re.compile(r'\b(classroom:?\s+[A-Za-z]?\d{2,4})\b', re.IGNORECASE),
             MEDIUM_CONFIDENCE),

            # Pattern 5: "Rm" or "Room" directly attached to number (no space)
            (re.compile(r'\b((?:room|rm)\.?[A-Za-z]?\d{2,4})\b', re.IGNORECASE),
             MEDIUM_CONFIDENCE),

            # Pattern 6: Single letter + 3-4 digits (like P380, R540)
            # Must NOT be preceded by alphanumeric (avoids "MegaFix P1135")
            (re.compile(r'(?<![A-Za-z0-9])([A-Z]\d{3,4})\b'),
             MEDIUM_CONFIDENCE),

            # Pattern 6b: Single letter + space + 3-4 digits (like "P 146")
            (re.compile(r'(?<![A-Za-z0-9])([A-Z]\s+\d{3,4})\b'),
             MEDIUM_CONFIDENCE),

            # Pattern 7: Bare 3-digit number followed by "(Lecture" context
            # e.g., "380 (Lecture; MW 2:10-3:30 pm)"
            (re.compile(r'\b(\d{3})\s*\(\s*lecture[;,]', re.IGNORECASE),
             HIGH_CONFIDENCE),

            # Pattern 8: Room number in "Room P380" format (P prefix with Room)
            (re.compile(r'\b(room\s+p\s*\d{3,4})\b', re.IGNORECASE),
             HIGH_CONFIDENCE),

            # Pattern 9: "Pandora Building (UNHM) P 146" - building + optional parens + P-room
            (re.compile(r'\b((?:pandora|pandra)\s+(?:building|mill|hall)?\s*(?:\([^)]+\))?\s*p\s*\d{3,4})\b', re.IGNORECASE),
             HIGH_CONFIDENCE),

            # Pattern 10: Lab room format "Lab (Rm 560)"
            (re.compile(r'\blab\s*\(\s*(rm\.?\s*\d{3,4})\s*\)', re.IGNORECASE),
             MEDIUM_CONFIDENCE),
        ]

        # PRE-COMPILED patterns for context checking
        self.explicit_location_pattern = re.compile(r'\b(?:class\s+)?location\s*:', re.IGNORECASE)
        self.year_pattern = re.compile(r'\b20\d{2}\b')
        self.course_code_context_pattern = re.compile(r'[A-Z]{2,4}\s*$')
        self.room_normalize_pattern = re.compile(r'((?:room|rm)\.?)([A-Za-z]?\d)', re.IGNORECASE)

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for consistent matching.

        Applies Unicode normalization (NFKC) and collapses multiple spaces/tabs
        into single spaces to ensure consistent pattern matching.

        Args:
            text (str): The raw text to normalize.

        Returns:
            str: The normalized text with standardized whitespace.
        """
        if not text:
            return ""
        t = unicodedata.normalize("NFKC", text)
        t = re.sub(r'[ \t]+', ' ', t)
        return t.strip()

    def _check_line_context(self, lines: List[str], line_index: int) -> ContextType:
        """
        Check the context of a specific line by examining surrounding lines.

        Determines whether a line containing a potential location is in a class
        context (what we want), office context (reject), or neutral context.

        Args:
            lines (List[str]): All lines from the document.
            line_index (int): The index of the line to check context for.

        Returns:
            ContextType: The context type enum value:
                - ContextType.CLASS: Line is in a class location context (accept)
                - ContextType.OFFICE: Line is in an office/non-class context (reject)
                - ContextType.NEUTRAL: No clear context indicator found

        Priority:
            1. If CURRENT line has class keywords -> 'CLASS' (overrides everything)
            2. If CURRENT line has office keywords -> 'OFFICE' (reject)
            3. Check surrounding lines for context
        """
        if line_index >= len(lines):
            return ContextType.NEUTRAL

        current_line = lines[line_index].lower()

        # PRIORITY 1: Current line has explicit class location keywords -> ACCEPT as 'CLASS'
        for pattern in self.class_location_keywords:
            if re.search(pattern, current_line):
                return ContextType.CLASS

        # PRIORITY 2: Current line has office keywords -> REJECT as 'OFFICE'
        for pattern in self.non_class_keywords:
            if re.search(pattern, current_line):
                return ContextType.OFFICE

        # PRIORITY 3: Check surrounding lines for additional context
        start_idx = max(0, line_index - CONTEXT_WINDOW_BEFORE)
        end_idx = min(len(lines), line_index + CONTEXT_WINDOW_AFTER + 1)
        context_lines = lines[start_idx:end_idx]
        context_text = ' '.join(context_lines).lower()

        # Check if surrounding context mentions class keywords
        for pattern in self.class_location_keywords:
            if re.search(pattern, context_text):
                return ContextType.CLASS

        # Check if surrounding context is office-related
        # (but be less aggressive - only reject if office keywords are close)
        for pattern in self.non_class_keywords:
            if re.search(pattern, context_text):
                # Only reject if office keyword is in immediate context (within 1 line)
                immediate_context = ' '.join(lines[max(0, line_index-1):min(len(lines), line_index+2)]).lower()
                if re.search(pattern, immediate_context):
                    return ContextType.OFFICE

        return ContextType.NEUTRAL

    def _is_course_code(self, text: str) -> bool:
        """
        Check if text looks like a course code.

        Identifies course codes to avoid false positives where course codes
        might be mistaken for room numbers (e.g., "COMP 405" vs "Room 405").

        Args:
            text (str): The text string to check.

        Returns:
            bool: True if the text matches a course code pattern, False otherwise.

        Examples:
            - "COMP 405" -> True
            - "BIOL 413A" -> True
            - "Room 405" -> False
        """
        for pattern in self.course_code_patterns:
            if pattern.search(text):
                return True
        return False

    def _extract_room_with_building(self, text: str) -> Optional[Tuple[str, float]]:
        """
        Extract room number with optional building name.
        Returns (location_string, confidence) or None.

        Examples:
        - "Room 105" -> ("Room 105", 0.85)
        - "Rm 139, Pandora Mill building" -> ("Rm 139, Pandora Mill", 0.95)
        - "Hamilton Smith 129" -> ("Hamilton Smith 129", 0.90)
        - "P380" -> ("P380", 0.70)
        """
        for pattern, confidence in self.room_patterns:
            match = pattern.search(text)
            if match:
                location = match.group(1).strip()

                # REJECT if it looks like a course code
                if self._is_course_code(location):
                    continue

                # REJECT if it looks like a year (2020-2029, Fall 2025, etc.)
                if self.year_pattern.search(location):
                    continue

                # REJECT product model numbers (e.g., "MegaFix P1135")
                # Check if preceded by product/model keywords within 20 chars
                context_before = text[max(0, match.start()-20):match.start()].lower()
                product_keywords = ['megafix', 'model', 'product', 'part', 'item', 'catalog', 'screw']
                if any(keyword in context_before for keyword in product_keywords):
                    continue  # Skip product models

                # For pattern6 (single letter + digits), only accept if NOT a course code context
                if pattern == self.room_patterns[5][0]:  # Pattern 6
                    # Check if this is in a course code context (e.g., "COMP 405")
                    context_check = text[max(0, match.start()-10):match.start()]
                    if self.course_code_context_pattern.search(context_check):
                        continue  # Skip if preceded by capital letters (likely course code)

                # Clean up extra spaces and normalize format
                location = re.sub(r'\s+', ' ', location)
                # Add space after Rm/Room if missing: "Rm126" → "Rm 126"
                location = self.room_normalize_pattern.sub(r'\1 \2', location)
                return (location, confidence)

        return None

    def _find_all_location_candidates(self, lines: List[str]) -> List[LocationCandidate]:
        """
        Find all potential location candidates in the document.
        Returns list of LocationCandidate objects.
        """
        candidates = []

        for i, line in enumerate(lines):
            line_lower = line.lower()

            # Check context of this line
            context_type = self._check_line_context(lines, i)

            # REJECT if in office/non-class context
            if context_type == ContextType.OFFICE:
                self.logger.debug(f"Line {i}: Rejected (office context) - {line[:50]}")
                continue

            # Check if line has a class location header/keyword
            has_class_header = any(
                re.search(pattern, line_lower)
                for pattern in self.class_location_keywords
            )

            # Check for EXPLICIT location labels (strongest signal)
            has_explicit_label = bool(self.explicit_location_pattern.search(line_lower))

            # Extract room from this line
            room_result = self._extract_room_with_building(line)
            if room_result:
                location, base_conf = room_result

                # Boost confidence if we have a positive class header
                if has_class_header or context_type == ContextType.CLASS:
                    confidence = HIGH_CONFIDENCE
                elif context_type == ContextType.NEUTRAL:
                    confidence = base_conf * 0.7  # Reduce for neutral context
                else:
                    confidence = base_conf

                candidate = LocationCandidate(
                    location=location,
                    confidence=confidence,
                    line_idx=i,
                    context_type=context_type,
                    has_explicit_label=has_explicit_label
                )
                candidates.append(candidate)
                self.logger.debug(f"Line {i}: Candidate '{location}' (conf: {confidence}, ctx: {context_type.value}, explicit: {has_explicit_label})")

        return candidates

    def _select_best_candidate(self, candidates: List[LocationCandidate]) -> Optional[Tuple[str, float]]:
        """
        Select the best location from multiple candidates.

        Prioritization (in order):
        1. Context type: CLASS > NEUTRAL > other
        2. Explicit keyword bonus: "Location: [room]" gets highest boost
        3. Header bonus: Locations in first HEADER_LINE_THRESHOLD lines get boost
        4. Confidence score (higher is better)
        5. Line index (earlier in document is better)
        """
        if not candidates:
            return None

        # Calculate scores for all candidates
        scored_candidates = []
        for candidate in candidates:
            # Priority 1: Context type (CLASS=0, NEUTRAL=1, other=2)
            if candidate.context_type == ContextType.CLASS:
                context_priority = 0
            elif candidate.context_type == ContextType.NEUTRAL:
                context_priority = 1
            else:
                context_priority = 2

            # Priority 2-4: Confidence with boosts
            adjusted_confidence = candidate.confidence

            # Explicit keyword boost (highest priority - stronger than header)
            if candidate.has_explicit_label:
                adjusted_confidence += EXPLICIT_KEYWORD_BOOST

            # Header boost (second priority)
            in_header = candidate.line_idx < HEADER_LINE_THRESHOLD
            if in_header:
                adjusted_confidence += HEADER_CONFIDENCE_BOOST

            # Create sort key
            sort_key = (context_priority, -adjusted_confidence, candidate.line_idx)
            scored_candidates.append((sort_key, candidate, in_header))

        # Sort by the key
        scored_candidates.sort(key=lambda x: x[0])

        # Get the best
        _, best_candidate, in_header = scored_candidates[0]

        self.logger.info(f"Best candidate: '{best_candidate.location}' at line {best_candidate.line_idx} "
                        f"(conf: {best_candidate.confidence}, ctx: {best_candidate.context_type.value}, "
                        f"explicit: {best_candidate.has_explicit_label}, in_header: {in_header})")
        self.logger.debug(f"Total candidates considered: {len(candidates)}")

        if len(scored_candidates) > 1:
            # Log runner-up for debugging
            _, runner_up, ru_header = scored_candidates[1]
            self.logger.debug(f"Runner-up: '{runner_up.location}' at line {runner_up.line_idx} "
                            f"(conf: {runner_up.confidence}, ctx: {runner_up.context_type.value}, "
                            f"explicit: {runner_up.has_explicit_label}, in_header: {ru_header})")

        return (best_candidate.location, best_candidate.confidence)

    def _find_online_or_remote_location(self, text: str) -> Optional[Tuple[str, float]]:
        """
        Check if course is online/remote/virtual.
        Returns (location_string, confidence) or None.

        Examples:
        - "Time and Location: Tuesday 1:10pm-4pm. Online" -> ("Online", 0.98)
        - "Location: Remote through Zoom" -> ("Remote through Zoom", 0.98)
        - "Canvas (online learning management system)" -> ("Canvas (online learning management system)", 0.98)
        """
        # Check first 50 lines for online/remote indicators
        lines = text.split('\n')[:50]
        text_to_search = '\n'.join(lines)

        for pattern, confidence in self.online_location_patterns:
            match = pattern.search(text_to_search)
            if match:
                location = match.group(1).strip()

                # Special case: CPRM-style "in Canvas, our learning management system"
                # Or "online course...course site on Canvas"
                # If we matched just "canvas" from these patterns, expand it
                if location.lower() == "canvas" and ("learning management system" in match.group(0).lower() or
                                                      "online course" in match.group(0).lower()):
                    location = "Canvas (online learning management system)"

                # Normalize "asynchronous online" to just "Online"
                if location.lower() == "asynchronous online":
                    location = "Online"

                # Normalize "online class" or "online course" to just "Online"
                if location.lower() in ("online class", "online course"):
                    location = "Online"

                # Normalize "mycourses" to "UNH MyCourses (online)"
                if "mycourses" in location.lower() and "(" not in location:
                    # Preserve UNH prefix if present
                    if location.lower().startswith("unh"):
                        location = "UNH MyCourses (online)"
                    else:
                        location = "UNH MyCourses (online)"

                # Clean up the location string
                location = re.sub(r'\s+', ' ', location)
                location = location.strip(',;:')
                # Limit length to avoid capturing too much
                if len(location) > 100:
                    # Try to find a reasonable cutoff point (period, newline, etc.)
                    for i, char in enumerate(location):
                        if char in '.;\n' and i > 20:
                            location = location[:i].strip()
                            break
                    else:
                        location = location[:100].strip()
                self.logger.info(f"Found online/remote location: '{location}' (confidence: {confidence})")
                return (location, confidence)

        return None

    def _find_location_in_document(self, text: str) -> Optional[Tuple[str, float]]:
        """
        Search entire document for class location.
        Returns (location, confidence) or None.

        Strategy:
        1. Check for EXPLICIT class room patterns first (e.g., "Class Meeting Room 341")
        2. Check for online/remote/virtual/appointment locations
        3. Find ALL potential physical location candidates
        4. Filter out office/non-class contexts
        5. Score each candidate
        6. Select best candidate
        """
        lines = text.split('\n')[:MAX_LINES_TO_SCAN]

        # PRIORITY 0: Check for explicit class meeting patterns with room in header (first 20 lines)
        # This handles hybrid courses where both room and "online" appear later
        # Patterns: "Class meetings: ... P149", "Class Meeting Room 341", "Class meets in Room 105"
        explicit_class_patterns = [
            # "Class Time & Location: ... P146" or "Class Time & Location: ... Pandora Building (UNHM) P146"
            re.compile(r'class\s+time\s*[&]\s*location\s*:[^\n]*\b((?:pandora|pandra)?\s*(?:building)?\s*(?:\([^)]+\))?\s*P\s*\d{3,4})\b', re.IGNORECASE),
            re.compile(r'class\s+time\s*[&]\s*location\s*:[^\n]*\b(room\s*\d{2,4})\b', re.IGNORECASE),
            # "Class meetings: Tuesday, 9:00 - 11:50 AM. P149" or "Class meetings: ... Room 105"
            re.compile(r'class\s+meetings?\s*[:\s][^P\n]*\b(P\d{3,4})\b', re.IGNORECASE),
            re.compile(r'class\s+meetings?\s*[:\s][^\n]*\b(room\s*\d{2,4})\b', re.IGNORECASE),
            # "Class Meeting Room 341"
            re.compile(r'class\s+meeting\s+room\s*[:\s]*([A-Za-z]?\d{2,4})', re.IGNORECASE),
            # "Class meets in Room 105" or "Class meets in P149"
            re.compile(r'class\s+meets?\s+(?:in\s+)?((?:room\s+)?[A-Za-z]?\d{2,4})', re.IGNORECASE),
            # "Lecture: P502" or "Lecture – P502"
            re.compile(r'lecture\s*[:\-–]\s*(P\d{3,4})', re.IGNORECASE),
            # "Location and Times: Lecture – P502"
            re.compile(r'location[^:]*:\s*lecture\s*[:\-–]\s*(P\d{3,4})', re.IGNORECASE),
        ]
        for line in lines[:20]:  # Only check first 20 lines (header area)
            for pattern in explicit_class_patterns:
                match = pattern.search(line)
                if match:
                    room = match.group(1).strip()
                    # Normalize: add "Room" prefix if just a number
                    if room.isdigit():
                        room = f"Room {room}"
                    self.logger.info(f"Found explicit class location in header: {room}")
                    return (room, HIGH_CONFIDENCE + 0.02)

        # PRIORITY 1: Check for online/remote/virtual/appointment locations
        online_result = self._find_online_or_remote_location(text)
        if online_result:
            return online_result

        # PRIORITY 2: Look for physical room locations
        # Find all physical location candidates with context analysis
        candidates = self._find_all_location_candidates(lines)

        # Select best candidate (only physical locations)
        if candidates:
            return self._select_best_candidate(candidates)

        # No location found - return None
        return None

    def detect(self, text: str) -> Dict[str, Any]:
        """
        Detect class meeting location in the text.

        Args:
            text (str): Document text to analyze

        Returns:
            Dict[str, Any]: Detection result with location if found
                {
                    'field_name': 'class_location',
                    'found': bool,
                    'content': str or None,
                    'confidence': float
                }
        """
        self.logger.info(f"Starting detection for field: {self.field_name}")

        # Input validation
        if not isinstance(text, str):
            self.logger.error(f"Invalid input type: {type(text)}, expected str")
            return self._not_found()

        if not text:
            return self._not_found()

        text = self._normalize_text(text)

        try:
            result = self._find_location_in_document(text)

            if result:
                location, confidence = result
                self.logger.info(f"FOUND: {self.field_name} = '{location}' (confidence: {confidence})")
                return {
                    'field_name': self.field_name,
                    'found': True,
                    'content': location,
                    'confidence': confidence
                }
            else:
                self.logger.info(f"NOT_FOUND: {self.field_name}")
                return self._not_found()

        except (ValueError, AttributeError, re.error) as e:
            self.logger.error(f"Error in class location detection: {e}", exc_info=True)
            return self._not_found()

    def _not_found(self) -> Dict[str, Any]:
        """Return not found result."""
        return {
            'field_name': self.field_name,
            'found': False,
            'content': None,
            'confidence': 0.0
        }


if __name__ == "__main__":
    # Unit tests for class location detector
    # NOTE: This detector ONLY finds physical locations, not "Online"
    test_cases = [
        # Basic physical location detection
        ("Class Location: Room 105", "Simple class room", True, "Room 105"),
        ("Meeting Location: Rm 139, Pandora Mill building", "Room with building", True, "Rm 139"),
        ("Class meets in Hamilton Smith 129", "Building with room", True, "Hamilton Smith 129"),

        # Disambiguation tests - should find class room, not office
        ("Office Hours: Room 201\nClass Location: Room 105", "Distinguish office from class", True, "Room 105"),
        ("Instructor Office: Room 301\nOffice Hours: Room 301\nClass meets in Room 105",
         "Multiple rooms - pick class", True, "Room 105"),
        ("Contact Info\nEmail: prof@unh.edu\nOffice: Room 201", "Only office location", False, None),

        # Online courses - should return NOT FOUND (physical location only)
        ("This course is fully online via Zoom", "Online with platform", False, None),
        ("100% online - no classroom meetings", "Definitive online statement", False, None),
        ("Location: Online", "Online explicit", False, None),

        # Complex syllabus structure
        ("Instructor: Dr. Smith\nOffice: Hamilton Smith 201\nOffice Hours: MWF 2-3pm\n\n"
         "Class Schedule:\nLocation: Kingsbury Hall 101\nTime: TR 10-11:30am",
         "Complex syllabus structure", True, "Kingsbury Hall 101"),

        # Edge cases
        ("Lab: Room 205\nTutoring Center: Room 110\nClass Location: Room 105",
         "Multiple non-class locations", True, "Room 105"),
    ]

    detector = ClassLocationDetector()
    print("Testing Class Location Detector (Physical Locations Only):")
    print("=" * 70)

    passed = 0
    failed = 0

    for test_text, description, should_find, expected_content in test_cases:
        result = detector.detect(test_text)
        found = result.get('found', False)
        content = result.get('content')

        # Check if result matches expectation
        success = (found == should_find)
        if should_find and expected_content:
            success = success and (expected_content in str(content) if content else False)

        status = "[PASS]" if success else "[FAIL]"
        if success:
            passed += 1
        else:
            failed += 1

        print(f"\n{status} - Test: {description}")
        print(f"  Input: {test_text[:60].replace(chr(10), ' | ')}...")
        print(f"  Expected: Found={should_find}, Content={expected_content}")
        print(f"  Got:      Found={found}, Content={content}")

    print(f"\n{'='*70}")
    print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print(f"Success rate: {passed/len(test_cases)*100:.1f}%")

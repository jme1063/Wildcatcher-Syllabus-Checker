"""
Detects professor office location, office hours, and phone number from syllabus text.
This detector uses regex patterns to find various formats of office information.
office_information_detection.py starts in the OfficeInformationDetector class and
contains three sub-detectors: LocationDetector and HoursDetector and PhoneDetector.

"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

# Detection Configuration Constants
DEFAULT_LOCATION_SEARCH_LIMIT = 5000
DEFAULT_HOURS_SEARCH_LIMIT = 8000  # Increased to catch office hours further in document
DEFAULT_PHONE_SEARCH_LIMIT = 2000
OFFICE_CONTEXT_SEARCH_LIMIT = 2000


@dataclass
class DetectionResult:
    """
    Result of a detection operation.
    """
    found: bool = False
    content: Optional[str] = None
    all_matches: List[str] = None

    def __post_init__(self):
        """Initialize all_matches as empty list if None."""
        if self.all_matches is None:
            self.all_matches = []


class BaseDetector:
    """
    Base class for field detection with common functionality.

    """

    def __init__(self, field_name: str, search_limit: int = 5000):
        """
        Initialize the base detector.
        Args:
            field_name (str): Name of the field being detected.
            search_limit (int): Character limit for searching text.
        """
        self.field_name = field_name
        self.search_limit = search_limit
        self.logger = logging.getLogger(f'detector.{field_name}')
        self.patterns = self._init_patterns()

    def _init_patterns(self) -> List[re.Pattern]:
        """
        Initialize regex patterns for this detector.
        Returns:
            List[re.Pattern]: Compiled regex patterns for detection.
        """
        raise NotImplementedError

    def detect(self, text: str) -> DetectionResult:
        """
        Detect the field in the given text.
        Args:
            text (str): The syllabus text to search.
        Returns:
            DetectionResult: The result of the detection.
        """
        # Limit search to first N characters for performance
        search_text = text[:self.search_limit] if len(text) > self.search_limit else text
        matches = self._find_all_matches(search_text)

        if matches:
            # Process raw matches (clean, validate, deduplicate)
            processed = self._process_matches(matches, text)
            if processed:
                return DetectionResult(
                    found=True,
                    content=processed[0],  # Best match
                    all_matches=processed  # All valid matches
                )

        return DetectionResult()  # No matches found

    def _find_all_matches(self, text: str) -> List[Any]:
        """
        Apply all regex patterns to find matches.
        Returns list that may contain strings or tuples depending on regex capture groups.
        Args:
            text (str): Text to search
        Returns:
            List[Any]: List of all raw matches found
        """
        all_matches = []
        for i, pattern in enumerate(self.patterns):
            matches = pattern.findall(text)
            if matches:
                self.logger.debug(f"Pattern {i+1} found: {matches}")
                all_matches.extend(matches)
        return all_matches

    def _process_matches(self, matches: List, text: str) -> List[str]:
        """
        Process and validate raw matches.
        Args:
            matches (List): Raw regex matches.
            text (str): Full syllabus text for context.
        Returns:
            List[str]: Processed, valid field strings.
        """
        raise NotImplementedError


class LocationDetector(BaseDetector):
    """
    Detector for office location information.
    """

    def __init__(self):
        """Initialize location detector with DEFAULT_LOCATION_SEARCH_LIMIT char search limit."""
        super().__init__('location', DEFAULT_LOCATION_SEARCH_LIMIT)

        # Patterns that indicate a room is a classroom, not an office
        self.classroom_indicators = [
            r'Class\s*Meeting',      # "Class Meeting: Room 105"
            r'Lab\s*Meeting',        # "Lab Meeting: Room 244"
            r'Time\s*and\s*Location.*room'  # "Time and Location: Room 139"
        ]
    
    def _init_patterns(self) -> List[re.Pattern]:
        """
        Initialize all location detection patterns.
        Returns:
            List[re.Pattern]: Compiled regex patterns for location detection.
        """
        patterns = [
            # Pattern 1: "Office Hours: ..., Room 105"
            # Captures room number after office hours mention
            r'Office\s*Hours?:.*?,\s*Room\s*(\d+[A-Z]?)',

            # Pattern 2: "Office: Room 628"
            # Direct office-to-room association
            r'Office:\s*Room\s*(\d+[A-Z]?)',
            # Pattern 2a: "Office: Rm 628" or "Office: Rm. 628"
            r'Office:\s*Rm\s*(\d+[A-Z]?)',

            # Pattern 3: "Pandora Rm. 103" or "Pandora Room 103"
            # Note: Pand[o]?ra handles common typo "Pandra"
            r'Pand[o]?ra\s+(?:Rm\.?|Room)\s*(\d+[A-Z]?)',

            # Pattern 4: "Office: Pandora Building, Room 244"
            # Full format with building name
            r'Office:\s*Pand[o]?ra\s*(?:Building)?,?\s*Room\s*(\d+[A-Z]?)',

            # Pattern 5: "Office Location/Hours: Pandora Building, Room 481"
            # Combined location/hours label
            r'Office\s*(?:Location)?/?(?:Hours)?:\s*Pand[o]?ra\s*(?:Building)?,?\s*Room\s*(\d+[A-Z]?)',

            # Pattern 6: Parenthetical "(office: room 141)"
            # Inline office mention
            r'\(office:\s*room\s*(\d+[A-Z]?)',

            # Pattern 7: "Pandora Lab 443"
            # Lab rooms (also office locations)
            r'Pand[o]?ra\s+Lab\s*(\d+[A-Z]?)',

            # Pattern 8: "P569" - Shorthand for Pandora Room
            # Matches P followed by room number in office context
            r'(?:Office|Contact)[^\n]{0,50}P(\d+[A-Z]?)',

            # Pattern 9: Simple "Room 139" in office context
            # Room number within 50 chars of "Office" or "Contact Information"
            r'(?:Office|Contact\s*Information)[^\n]{0,50}Room\s*(\d+[A-Z]?)',

            # Pattern 10: Generic - any Room/Rm in instructor section
            # Fallback: room number within 150 chars of instructor mention
            r'(?:Instructor|Professor|Faculty|Office|OFFICE)[^\n]{0,150}(?:Room|Rm\.?)\s*(\d+[A-Z]?)',
        ]

        return [re.compile(p, re.IGNORECASE) for p in patterns]
    
    def _process_matches(self, matches: List[str], text: str) -> List[str]:
        """
        Process location matches to return unique, valid room numbers.
        Args:
            matches (List[str]): Raw regex matches.
            text (str): syllabus text for context.
        Returns:
            List[str]: Processed, valid office location strings.
        """
        unique_rooms = []
        seen = set()

        for match in matches:
            # Handle tuple matches from regex capture groups
            if isinstance(match, tuple):
                match = match[0] if match else ''

            room = match.strip() if match else ''

            # Validate format: digits optionally followed by a letter (e.g., "529", "105A")
            if room and re.match(r'^\d+[A-Z]?$', room) and room not in seen:
                # Check if this is actually an office (not a classroom)
                if self._is_office_context(room, text):
                    # Check how this room appears in the document to match the format
                    formatted = self._format_room_number(room, text)
                    unique_rooms.append(formatted)
                    seen.add(room)

        return unique_rooms

    def _format_room_number(self, room: str, text: str) -> str:
        """
        Format room number to match how it appears in the document.
        Priority: P### > Pandora Room ### > Room ###
        Args:
            room (str): Room number (e.g., "529")
            text (str): syllabus text for context.
        Returns:
            str: Formatted room string.
        """
        search_text = text[:DEFAULT_LOCATION_SEARCH_LIMIT]

        # Check for P### format (shorthand)
        p_pattern = rf'\bP{re.escape(room)}\b'
        if re.search(p_pattern, search_text, re.IGNORECASE):
            return f"P{room}"

        # Check for "Pandora Room ###" or "Pandora, Room ###"
        pandora_pattern = rf'Pand[o]?ra\s*,?\s*(?:Rm\.?|Room)\s*{re.escape(room)}\b'
        pandora_match = re.search(pandora_pattern, search_text, re.IGNORECASE)
        if pandora_match:
            building_name = pandora_match.group(0)
            # Normalize "Pandra" to "Pandora"
            if 'pandra' in building_name.lower():
                # Extract the full match and replace Pandra with Pandora
                return re.sub(r'Pandra', 'Pandora', building_name, flags=re.IGNORECASE)
            return building_name

        # Default to "Room ###" format
        return f"Room {room}"

    def _extract_building_name(self, room: str, text: str) -> str:
        """
        Extract building name from text near the room number.
        Returns building name if found, empty string otherwise.
        Args:
            room (str): Room number (e.g., "529")
            text (str): syllabus text for context.
        Returns:
            str: Building name if found, else empty string.
        """
        # Search for "Pandora" (or "Pandra" typo) near this room number
        # Look in first 5000 chars for performance
        search_text = text[:DEFAULT_LOCATION_SEARCH_LIMIT]

        # Pattern: Pandora/Pandra followed by optional "Building", then Room/Rm and the room number
        building_pattern = rf'(Pand[o]?ra)\s*(?:Building)?\s*,?\s*(?:Rm\.?|Room|Lab)\s*{re.escape(room)}\b'
        building_match = re.search(building_pattern, search_text, re.IGNORECASE)

        if building_match:
            # Return the building name (e.g., "Pandora")
            return building_match.group(1).capitalize()

        return ""

    def _is_office_context(self, room: str, text: str) -> bool:
        """
        Check if room number is in office context (not classroom).
        Args:
            room (str): Room number (e.g., "529")
            text (str): syllabus text for context.
        Returns:
            bool: True if room is in office context, False if likely a classroom.
        """
        room_pattern = rf'(?:Room|Rm\.?)\s*{re.escape(room)}'

        # REJECT: Check if it's a classroom
        for indicator in self.classroom_indicators:
            pattern = rf'{indicator}.{{0,100}}{room_pattern}'
            if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
                self.logger.debug(f"Room {room} appears to be classroom")
                return False

        # ACCEPT: Check if it's in office context
        office_patterns = [
            rf'Office[^{{}}]*{room_pattern}',           # "Office ... Room 529"
            rf'Instructor[^{{}}]*{room_pattern}',        # "Instructor ... Room 529"
            rf'Professor[^{{}}]*{room_pattern}',         # "Professor ... Room 529"
            rf'{room_pattern}[^{{}}]*(?:Phone|Email|Hours)'  # "Room 529 ... Phone:"
        ]

        for pattern in office_patterns:
            # Check first OFFICE_CONTEXT_SEARCH_LIMIT chars for performance
            if re.search(pattern, text[:OFFICE_CONTEXT_SEARCH_LIMIT], re.IGNORECASE | re.DOTALL):
                return True

        return True  # Default to office if context unclear


class HoursDetector(BaseDetector):
    """
    Detector for office hours information.
    """

    # Phrases that indicate false positives (not actual office hours)
    # Made more specific to avoid blocking valid office hours text
    INVALID_PHRASES = [
        'to discuss ideas', 'questions about the material', 'meeting agenda',
        'click here for', 'assignment submission', 'to join the meeting',
        'feel free to contact me about', 'hours of free individual tutoring',
        'tutoring appointment and access'
    ]

    # Patterns that indicate valid office hours content
    VALID_INDICATORS = [
        r'\d{1,2}:\d{2}',  # Time like "4:00"
        r'\d{1,2}\s*[ap]\.?m',  # Time like "4pm" or "4 p.m."
        r'monday|tuesday|wednesday|thursday|friday',  # Day names
        r'\b[MTWRF]\s+\d',  # Abbreviated days with times "T 5:15"
        r'appointment',  # "By appointment"
        r'arrangement',  # "By Arrangement"
        r'contact\s+(?:the\s+)?(?:instructor|professor)',  # "Please contact the instructor"
        r'zoom',  # "via Zoom"
        r'virtual',  # "Virtual office hours"
        r'TBD',  # "TBD"
        r'anytime',  # "Anytime"
        r'available',  # "Available"
        r'scheduled',  # "Scheduled by appointment"
        r'office\s*hours?',  # "Office hours" (fallback)
        r'canvas\s+inbox',  # "Canvas Inbox tool"
        r'after\s*[- ]?class',  # "After class" or "after-class"
        r'help\s+session',  # "help session"
        r'calendly\.com',  # Calendly URL
        r'see\s+schedule',  # "See schedule on Canvas"
        r'section\s+[A-Z]\d+',  # "Section M2"
        r'Sunday|Saturday',  # Weekend days
        r'meetings?\s+by',  # "Meetings by appointment"
        r'to\s+be\s+determined',  # "To be determined"
        r'after\s+lecture',  # "After lecture"
        r'as\s+posted',  # "As posted outside my office"
        r'outside\s+(?:my\s+)?office',  # "Outside my office"
        r'private\s+(?:zoom|teams)',  # "Private Zoom/Teams sessions"
        r'from\s+a\s+link',  # "from a link"
    ]

    def __init__(self):
        """Initialize hours detector with DEFAULT_HOURS_SEARCH_LIMIT char search limit."""
        super().__init__('hours', DEFAULT_HOURS_SEARCH_LIMIT)
    
    def _init_patterns(self) -> List[re.Pattern]:
        """
        Initialize all hours detection patterns.

        Returns:
            List[re.Pattern]: Compiled regex patterns for hours detection.
        """
        patterns = [
            # TBD patterns - highest priority
            r'(?:Office\s*)?Hours?\s*[:]\s*(TBD)',
            r'hours\s+(TBD)',
            r'Office\s+hours\s+(TBD)',

            # NEW: Canvas Inbox tool pattern
            r'(?:To\s+)?schedule\s+(?:in-person\s+or\s+)?Zoom\s+meetings\s+use\s+the\s+(Canvas\s+Inbox\s+tool)',
            # "Make an appointment using MyCourses Canvas Inbox tool"
            r'[Mm]ake\s+an?\s+appointment\s+using\s+(?:the\s+)?(MyCourses\s+Canvas\s+Inbox\s+tool)',

            # NEW: After-class help session patterns (with en-dash support)
            r'(?:Office\s*Hours?[\s:]+)?([MTWRF][a-z]*,?\s+\d{1,2}(?::\d{2})?\s*[-\u2013]\s*\d{1,2}(?::\d{2})?\s*[ap]m\s+\(after-class\s+help\s+session\))',
            r'(?:Office\s*Hours?[\s:]+)?(\d{1,2}(?::\d{2})?\s*[ap]m\s*[-\u2013]\s*\d{1,2}(?::\d{2})?\s*[ap]m\s+\(after-class\s+help\s+session\))',
            # Help session before the time (e.g., "help session, Tuesday, 1-3 pm") - with en-dash
            r'help\s+session,?\s+([MTWRF][a-z]*,?\s+\d{1,2}(?::\d{2})?\s*[-\u2013]\s*\d{1,2}(?::\d{2})?\s*[ap]m)',
            # "The after-class help session, Monday, 4 - 6 pm"
            r'after-class\s+help\s+session,?\s+([MTWRF][a-z]*,?\s+\d{1,2}(?::\d{2})?\s*[-\u2013]\s*\d{1,2}(?::\d{2})?\s*[ap]m)',

            # NEW: Section-specific hours
            r'(?:Office\s*Hours?[\s:]+)?(Section\s+[A-Z]\d+:\s+After\s+class;\s+By\s+appointment)',

            # NEW: Standalone URL pattern (calendly links)
            # Allow newlines/spaces within URL (PDFs sometimes break URLs across lines)
            r'(?:Office\s*Hours?[\s:]*)?(https?://\s*(?:www\.)?calendly\.com/[a-zA-Z0-9_/-]+)',

            # NEW: "See schedule on Canvas" pattern
            r'(?:Office\s*Hours?[\s:]+)?(See\s+schedule\s+on\s+Canvas(?:;\s+By\s+appointment)?)',
            # "See Instructor office hours from a link"
            # Limit capture and stop at sentence boundaries to avoid capturing unrelated text
            r'(?:Office\s*Hours?[\s:]+)?(See\s+Instructor\s+office\s+hours\s+from\s+a\s+link[^.!\n]{0,40})',

            # NEW: After class pattern (simple)
            r'(?:Office\s*Hours?[\s:]+)?(After\s+class;\s+By\s+appointment)',
            # "After lecture or private Zoom/Teams sessions"
            r'(?:Office\s*Hours?[\s:]+)?(After\s+lecture\s+or\s+private\s+(?:Zoom|Teams)[^\n]{0,80})',

            # NEW: "Meetings by Appointment" pattern (with en-dash)
            r'Meetings?\s+by\s+Appointment[\s:�\u2013-]+([^\n]{5,100})',

            # NEW: "available to meet" pattern
            r'(?:Office\s*Hours?[\s:]+)?([Aa]vailable\s+to\s+meet\s+by\s+appointment[^\n]{0,80})',

            # NEW: "to be determined" pattern
            r'(?:Office\s*Hours?[\s:]+)?((?:Office\s+hours\s+)?to\s+be\s+determined[^\n]{0,80})',

            # NEW: By appointment with day ranges (e.g., "By appointment Sunday - Thursday 7pm - 9pm")
            r'(?:Office\s*Hours?[\s:]+)?([Bb]y\s+appointment\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s*[-]\s*(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)[^\n]{0,100})',

            # NEW: Compact time format without am/pm (e.g., "Mondays 1-2, Thursdays 2-4")
            r'(?:Office\s*Hours?[\s:]+)?([MTWRF][a-z]+s?\s+\d{1,2}\s*[-\u2013]\s*\d{1,2},?\s+[MTWRF][a-z]+s?\s+\d{1,2}\s*[-\u2013]\s*\d{1,2})',

            # NEW: "As posted outside my office" pattern
            r'(?:Office\s*Hours?[\s:]+)?(As\s+posted\s+outside\s+my\s+office[^\n]{0,80})',

            # Standard patterns
            # Special case: if line contains semicolon, allow newline continuation (up to 250 chars total)
            # This captures: "Hours: X; Y\nZ" where Z continues from Y
            # Use greedy match, then stop at clear boundaries
            r'Office\s*(?:Hours?|Hrs?)[\s:]+([^\n]+;[\s\S]{1,250}?)(?=\n[A-Z][a-z]+\s*(?:Prerequisite|Text|Course|Description|Location|Meeting|Schedule|Required|Recommended)|$)',
            # Regular single-line pattern (no semicolon)
            r'Office\s*(?:Hours?|Hrs?)[\s:]+([^\n;]{5,150}?)(?=\n|$|Phone|Email|Web|Course|Prerequisite|Text|Instructor)',
            r'OFFICE\s*HOURS?[\s:]+([^\n]{5,150}?)(?=\n|$|PHONE|EMAIL|COURSE)',

            # Virtual office hours
            r'virtual\s*office\s*hrs?\.?:?\s*([^\n]{5,100}?)(?=\n|$|I am)',
            r'Virtual\s*office\s*hours?\s*([^\n]{5,100}?)(?=\n|$)',

            # Special combined pattern for Klenotic-style
            r'Office\s*Location/?Hours?:[^;]+;\s*([TWMRF]\s+\d{1,2}:\d{2}[^.\n]+)',

            # IMPROVED: Multi-line semicolon pattern for PSYC_511 style
            # Captures: "Tuesday - 4:00 - 5:00;Thursday - 3:00 - 5:00;\nFriday - 1:00 - 2:00"
            # Also captures: "Wednesdays 10:30 am - 12:00 pm; alternatively, Zoom and phone appointments..."
            # Allow newlines within semicolon-separated clauses (up to 200 chars after semicolon)
            r'(?:Office\s*)?Hours?[\s:]+([^;\n]+(?:;[\s\S]{0,200}?)*?)(?=\s*(?:Phone|Email|Course|Office|Instructor|Prerequisites?|Text|$))',

            # IMPROVEMENT 4a: Pattern for multi-day hours separated by newlines (document_processing extraction)
            # Matches: "Tuesday - 4:00 � 5:00\nThursday - 3:00 � 5:00\nFriday - 1:00 � 2:00"

            r'(?:Office\s*)?Hours?[\s:]+\n((Monday|Tuesday|Wednesday|Thursday|Friday)\s*[-:]\s*\d{1,2}:\d{2}\s*[-�\u2013\u2014]\s*\d{1,2}:\d{2}\s*(?:\n(Monday|Tuesday|Wednesday|Thursday|Friday)\s*[-:]\s*\d{1,2}:\d{2}\s*[-�\u2013\u2014]\s*\d{1,2}:\d{2})+)',

            # IMPROVEMENT 4b: Pattern for multi-day hours separated by spaces (PyPDF2 extraction format)
            # Matches: "Tuesday - 4:00 - 5:00   Thursday - 3:00 - 5:00   Friday - 1:00 - 2:00"
            r'(?:Office\s*)?Hours?[\s:]+((Monday|Tuesday|Wednesday|Thursday|Friday)\s*[-:]\s*\d{1,2}:\d{2}\s*[-�]\s*\d{1,2}:\d{2}\s*(?:\s+(Monday|Tuesday|Wednesday|Thursday|Friday)\s*[-:]\s*\d{1,2}:\d{2}\s*[-�]\s*\d{1,2}:\d{2})+)',

            # Day-based patterns
            # Increased from 80 to 200 chars to capture full multi-clause hours with semicolons
            # Use [\s\S] to allow newlines when semicolons are present
            r'(?:Hours?|Hrs?)[\s:]+([MTWRF][a-z]*[^.;]+;[\s\S]{1,180}?)(?=\n[A-Z][a-z]+:|\n[A-Z][a-z]+\s+[A-Z]|$)',
            # Single-line day pattern (no semicolon)
            r'(?:Hours?|Hrs?)[\s:]+([MTWRF][a-z]*[^\n.;]{5,150}?)(?=\.|$|\n|Phone|Email|Course)',

            # Time-based patterns
            r'(?:Hours?|Hrs?)[\s:]+(\d{1,2}:\d{2}\s*[ap]m[^.\n]{0,80}?)(?=\.|$|\n)',

            # IMPROVED: By appointment patterns with more variations
            # Increased from 80 to 120 chars to avoid truncation
            r'(?:Office\s*)?Hours?[\s:]+([Bb]y\s+appointment[^.\n]{0,120})(?=\.|$|\n)',
            r'Office\s*hours?\s+are\s+(schedule[d]?\s+by\s+appointment[^\n]{0,50})',

            # NEW: By Arrangement pattern (similar to "By appointment")
            r'(?:Office\s*)?Hours?[\s:]+([Bb]y\s+[Aa]rrangement[^.\n]{0,100})(?=\.|$|\n)',

            # NEW: "Please contact" style office hours
            r'(?:Office\s*)?Hours?[\s:]+([Pp]lease\s+contact\s+(?:the\s+)?(?:instructor|professor)[^.\n]{0,100})',

            # IMPROVED: Available/By appointment combined pattern for Karen Jin style
            r'(?:Office\s*)?Hours?[\s:]+([Bb]y\s+appointment[^;]*;\s*(?:available\s+)?in\s+person\s+or\s+virtual[^\n]*)',

            # IMPROVEMENT 3: Enhanced Available patterns - capture full context
            r'(?:Office\s*)?Hours?[\s:]+([Aa]vailable\s+in\s+person\s+or\s+virtually[^\n.]{0,100})',
            r'(?:Office\s*)?Hours?[\s:]+([Aa]vailable\s+(?:in\s+person|virtually)[^\n]{0,80})',

            # Anytime patterns
            r'OFFICE\s*HOURS?[\s:]+([Aa]nytime\s+by\s+(?:ZOOM|zoom|Zoom)[^\n]{0,80})(?=\.|$|\n)',

            # IMPROVED: Monday patterns for NSIA_898 - handles "Mondays 4-5 pm via Zoom"
            r'(?:Office\s*hours?\s+are\s+)?([Mm]ondays?\s+\d{1,2}(?:[-:]\d{1,2})?\s*[ap]m\s*via\s*Zoom[^\n]{0,50})',
            r'([Mm]ondays?\s+\d{1,2}[-:]\d{1,2}\s*[ap]m[^,\n]*(?:,\s*plus\s+by\s+appointment)?)',

            # Day/time specific patterns
            r'(?:Office\s*)?Hours?[\s:]+(?:on\s+)?([MTWRF][^\n]{5,80}?)(?=\.|$|\n|,\s*Room)',
            r'(?:Office\s*)?Hours?[\s:]+(\d{1,2}(?::\d{2})?\s*[ap]m[^\n]{0,80}?)(?=\.|$|\n|,\s*Room)',
        ]
        
        return [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in patterns]
    
    def detect(self, text: str) -> DetectionResult:
        """
        Special detection for hours to handle TBD priority.
        
        Args:
            text (str): The syllabus text to search.
        Returns:
            DetectionResult: The result of the detection."""
        search_text = text[:self.search_limit] if len(text) > self.search_limit else text
        
        # Check for TBD first
        tbd_patterns = [
            re.compile(r'(?:Office\s*)?Hours?\s*[:]\s*(TBD)', re.IGNORECASE),
            re.compile(r'hours\s+(TBD)', re.IGNORECASE),
            re.compile(r'Office\s+hours\s+(TBD)', re.IGNORECASE),
        ]
        
        for pattern in tbd_patterns:
            if pattern.search(search_text):
                return DetectionResult(found=True, content='TBD', all_matches=['TBD'])
        
        # Continue with normal detection
        return super().detect(text)
    
    def _process_matches(self, matches: List[str], text: str) -> List[str]:
        """
        Process hours matches.
        
        args:
            matches (List[str]): Raw regex matches.
            text (str): Full syllabus text for context.
        Returns:
            List[str]: Processed, valid office hours strings.
        """
        valid_hours = []
        seen = set()

        for match in matches:
            if isinstance(match, tuple):
                match = match[0] if match else ''

            if match and len(match.strip()) > 2:  # Allow shorter matches (was >3) for URLs, "TBD", etc.
                # Handle tuple matches from regex groups
                if isinstance(match, tuple):
                    # Take the first capturing group (the full match)
                    original_match = match[0] if match[0] else (match[1] if len(match) > 1 and match[1] else '')
                else:
                    original_match = match

                original_match = original_match.strip()

                
                # All converted to standard hyphen (-) for consistent processing
                original_match = re.sub(r'[\u2013\u2014\u2015\u2212�]', '-', original_match)

                # Both converted to standardized format:
                #   "Tuesday - 4:00 - 5:00;Thursday - 3:00 - 5:00;\nFriday - 1:00 - 2:00"
                #   (semicolons between all days, newline before last day)

                day_pattern = r'(Monday|Tuesday|Wednesday|Thursday|Friday)\s*[-:]\s*\d{1,2}:\d{2}\s*[-]\s*\d{1,2}:\d{2}'
                day_matches = re.findall(day_pattern, original_match, re.IGNORECASE)

                if len(day_matches) >= 2:  # Multiple days found - this is a multi-day schedule
                    # Extract all complete "Day - StartTime - EndTime" patterns
                    segments = re.findall(r'((?:Monday|Tuesday|Wednesday|Thursday|Friday)\s*[-:]\s*\d{1,2}:\d{2}\s*[-]\s*\d{1,2}:\d{2})', original_match, re.IGNORECASE)
                    if len(segments) >= 2:
                        # Convert to standard format: "Day1;Day2;\nDay3"
                        # Join all but last with ';', then add ';\n' before last day
                        first_parts = ';'.join(segments[:-1])
                        original_match = first_parts + ';\n' + segments[-1]

                # ===================================================================
                # IMPROVEMENT 3: Whitespace Normalization (Preserving Structure)
                # ===================================================================
                # For multi-day schedules with semicolons, normalize whitespace
                # while carefully preserving newlines that indicate structure
                if ';' in original_match and any(day in original_match for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday']):
                    cleaned = original_match

                    # Step 1: Protect newlines from whitespace normalization
                    # Use placeholder that won't appear in real text
                    cleaned = cleaned.replace('\n', '<<<NEWLINE>>>')

                    # Step 2: Normalize all other whitespace (multiple spaces → single space)
                    cleaned = re.sub(r'\s+', ' ', cleaned)

                    # Step 3: Restore newlines
                    cleaned = cleaned.replace('<<<NEWLINE>>>', '\n')

                    # Step 4: Clean up spacing around semicolons
                    # First handle semicolon-newline (protect it)
                    cleaned = re.sub(r';\s*\n\s*', ';\n', cleaned)

                    # Then clean up other semicolons (but not semicolon-newline)
                    # Split by ';\n', clean each part, then rejoin
                    parts = cleaned.split(';\n')
                    cleaned_parts = [re.sub(r';\s+', ';', part) for part in parts]
                    cleaned = ';\n'.join(cleaned_parts)
                elif 'by appointment' in original_match.lower() and ';' in original_match:
                    # "By appointment; in person or virtual" style
                    cleaned = original_match
                    cleaned = re.sub(r'\s+', ' ', cleaned)
                elif 'monday' in original_match.lower() and 'zoom' in original_match.lower():
                    # "Mondays 4-5 pm via Zoom" style - preserve as is
                    cleaned = re.sub(r'\s+', ' ', original_match)
                elif 'calendly.com' in original_match.lower():
                    # URL pattern - preserve as is (no cleaning)
                    cleaned = original_match.strip()
                elif 'canvas inbox' in original_match.lower() or 'mycourses canvas inbox' in original_match.lower():
                    # Canvas Inbox tool - preserve as is
                    cleaned = original_match.strip()
                elif 'by arrangement' in original_match.lower():
                    # "By Arrangement" - minimal cleaning (just whitespace)
                    cleaned = re.sub(r'\s+', ' ', original_match).strip()
                elif 'please contact' in original_match.lower():
                    # "Please contact" style - minimal cleaning
                    cleaned = re.sub(r'\s+', ' ', original_match).strip()
                elif 'after-class' in original_match.lower() or 'help session' in original_match.lower():
                    # After-class help session - minimal cleaning (just whitespace)
                    cleaned = re.sub(r'\s+', ' ', original_match).strip()
                elif 'see schedule' in original_match.lower():
                    # "See schedule on Canvas" - preserve as is
                    cleaned = original_match.strip()
                elif re.match(r'^Section\s+[A-Z]\d+:', original_match, re.IGNORECASE):
                    # Section-specific hours - minimal cleaning
                    cleaned = re.sub(r'\s+', ' ', original_match).strip()
                elif 'meetings by appointment' in original_match.lower():
                    # "Meetings by Appointment" - minimal cleaning
                    cleaned = re.sub(r'\s+', ' ', original_match).strip()
                elif 'to be determined' in original_match.lower():
                    # "To be determined" - minimal cleaning
                    cleaned = re.sub(r'\s+', ' ', original_match).strip()
                elif 'after lecture' in original_match.lower():
                    # "After lecture" - minimal cleaning
                    cleaned = re.sub(r'\s+', ' ', original_match).strip()
                elif 'as posted' in original_match.lower():
                    # "As posted outside my office" - minimal cleaning
                    cleaned = re.sub(r'\s+', ' ', original_match).strip()
                elif 'from a link' in original_match.lower():
                    # "from a link" - minimal cleaning
                    cleaned = re.sub(r'\s+', ' ', original_match).strip()
                else:
                    cleaned = self._clean_hours(original_match)

                # Avoid duplicates but consider variations as unique
                normalized_for_comparison = re.sub(r'[^\w\d]+', '', cleaned.lower())
                if self._is_valid_hours(cleaned) and normalized_for_comparison not in seen:
                    valid_hours.append(cleaned)
                    seen.add(normalized_for_comparison)

        if valid_hours:
            return [self._select_best_hours(valid_hours)]

        return []
    
    def _clean_hours(self, hours: str) -> str:
        """
        Clean office hours text.
        Args:
            hours (str): Raw office hours text.
        Returns:
            str: Cleaned office hours text.
        """
        # IMPROVEMENT 1: Normalize various dash characters (en-dash, em-dash, hyphen)
        # Replace en-dash (–), em-dash (—), and other dash variants with standard hyphen
        hours = re.sub(r'[\u2013\u2014\u2015\u2212]', '-', hours)

        # Normalize whitespace
        hours = ' '.join(hours.split())

        # IMPROVED: More comprehensive room information removal (including building names)
        hours = re.sub(r',?\s*(?:Pandora|P)\s*\d+[A-Z]?\b', '', hours, flags=re.IGNORECASE)
        hours = re.sub(r',?\s*Room\s*\d+[A-Z]?', '', hours, flags=re.IGNORECASE)
        hours = re.sub(r',?\s*Rm\.?\s*\d+[A-Z]?', '', hours, flags=re.IGNORECASE)

        # Remove trailing punctuation
        hours = hours.rstrip('.,;,')

        # Remove common suffixes and incomplete sentences
        hours = re.sub(r'\s*(?:Students are|I am|Please|You may|You are).*$', '', hours, flags=re.IGNORECASE)

        # IMPROVED: Remove incomplete sentence fragments at the end
        # If it ends with " in my" or " or an" or similar incomplete phrases, remove them
        hours = re.sub(r'\s+(?:in\s+my|or\s+an|and\s+|to\s+)$', '', hours, flags=re.IGNORECASE)

        # Standardize appointment text
        hours = re.sub(r'by\s+appt\.?', 'by appointment', hours, flags=re.IGNORECASE)
        hours = re.sub(r'&\s+by\s+appt\.?', '& by appointment', hours, flags=re.IGNORECASE)

        # Standardize "appt." to "appointment" in other contexts
        hours = re.sub(r'\bappt\.?\b', 'appointment', hours, flags=re.IGNORECASE)

        # IMPROVED: Standardize "in advance" vs "in adv"
        hours = re.sub(r'\bin\s+adv\b', 'in advance', hours, flags=re.IGNORECASE)

        return hours.strip()
    
    def _is_valid_hours(self, text: str) -> bool:
        """
        Check if text is likely valid office hours.
        Args:
            text (str): Office hours text to validate.
        Returns:
            bool: True if valid hours, False otherwise.
        """
        if not text:
            return False

        text_lower = text.lower()

        # Reject invalid phrases
        if any(phrase in text_lower for phrase in self.INVALID_PHRASES):
            return False

        # Reject class/lecture times (not office hours)
        # These patterns indicate class meeting times, not office hours
        class_time_indicators = [
            r'class\s+(?:meets|meeting|schedule|time)',
            r'lecture\s+(?:meets|time|schedule)',
            r'course\s+(?:meets|meeting|schedule)',
            r'session\s+time',
            r'class\s+(?:is\s+)?held',
        ]
        if any(re.search(pattern, text_lower) for pattern in class_time_indicators):
            return False

        # Accept valid indicators
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in self.VALID_INDICATORS)
    
    def _select_best_hours(self, hours_list: List[str]) -> str:
        """
        Select the most descriptive office hours.
        Args:
            hours_list (List[str]): List of valid office hours strings.
        Returns:
            str: The most descriptive office hours string.
        """
        if not hours_list:
            return None

        # Debug: look at what we have
        self.logger.debug(f"Selecting from hours options: {hours_list}")

        # Priority 1: Multi-line/multi-day patterns with semicolons (most complete)
        for hours in hours_list:
            if ';' in hours and any(day in hours.lower() for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']):
                # This looks like a complete weekly schedule
                return hours

        # Priority 2: "By appointment/arrangement" with day range and specific times
        # e.g., "By appointment Sunday - Thursday 7pm - 9pm"
        for hours in hours_list:
            if ('by appointment' in hours.lower() or 'by arrangement' in hours.lower()) and \
               re.search(r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s*[-–]\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', hours, re.IGNORECASE) and \
               re.search(r'\d{1,2}\s*[ap]m', hours, re.IGNORECASE):
                return hours

        # Priority 3: Entries with specific times and days
        for hours in hours_list:
            if re.search(r'\d{1,2}:\d{2}', hours) and re.search(r'[MTWRF]|Monday|Tuesday|Wednesday|Thursday|Friday', hours, re.IGNORECASE):
                return hours

        # Priority 4: "By appointment" with additional context (in person/virtual)
        for hours in hours_list:
            if 'by appointment' in hours.lower() and (';' in hours or 'person' in hours.lower() or 'virtual' in hours.lower()):
                return hours

        # Priority 5: Monday patterns with Zoom (specific virtual hours)
        for hours in hours_list:
            if 'monday' in hours.lower() and 'zoom' in hours.lower():
                return hours

        # Priority 6: Just specific times
        for hours in hours_list:
            if re.search(r'\d{1,2}:\d{2}', hours):
                return hours
        
        # Priority 6: Just day names
        for hours in hours_list:
            if re.search(r'[MTWRF]|Monday|Tuesday|Wednesday|Thursday|Friday', hours, re.IGNORECASE):
                return hours
        
        # Priority 7: "scheduled" or "available" patterns
        for hours in hours_list:
            if 'scheduled' in hours.lower() or 'available' in hours.lower():
                return hours

        # Before default: Filter out generic "see...link" patterns if there are other options
        # These are less useful than almost anything else
        non_generic = [h for h in hours_list if not re.search(r'see\s+.*\s+from\s+a\s+link', h, re.IGNORECASE)]
        if non_generic:
            # Return longest of the non-generic options
            return max(non_generic, key=len)

        # Default: Return longest (most complete)
        return max(hours_list, key=len)


class PhoneDetector(BaseDetector):
    """Detector for phone number information."""

    def __init__(self):
        """Initialize phone detector with DEFAULT_PHONE_SEARCH_LIMIT char search limit."""
        super().__init__('phone', DEFAULT_PHONE_SEARCH_LIMIT)
    
    def _init_patterns(self) -> List[re.Pattern]:
        """
        Initialize all phone detection patterns.

        Returns:
            List[re.Pattern]: Compiled regex patterns for phone detection.
        """

        digit_pattern = r'([(\d][\d\s().-]{8,14})'
        
        patterns = [
            # Standard phone labels
            rf'(?:Office\s*)?Phone[\s:]+{digit_pattern}',
            rf'PHONE[\s:]+{digit_pattern}',
            
            # Contact section
            rf'Contact:.*?Phone[\s:]+{digit_pattern}',
            
            # Phone after office location
            rf'(?:Room|Rm\.?)\s*\d+[A-Z]?\s*[\n,]\s*(?:Office\s*)?Phone[\s:]+{digit_pattern}',
            
            # Combined with office info
            rf'Office:.*?,\s*{digit_pattern}',
            
            # Telephone pattern
            rf'Telephone[\s:]+{digit_pattern}',
            
            # Generic phone number patterns
            r'603[\s.-]?\d{3}[\s.-]?\d{4}',
            r'\(603\)[\s.-]?\d{3}[\s.-]?\d{4}',
            r'434[\s.-]?\d{3}[\s.-]?\d{4}',  # For the 434 area code
        ]
        
        return [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in patterns]
    
    def _process_matches(self, matches: List[str], text: str) -> List[str]:
        """
        Process phone matches.
        
        Args:
            matches (List[str]): List of matched phone strings.
            text (str): The original text being analyzed.
        
        Returns:
            List[str]: List of cleaned and validated unique phone numbers.
        """
        unique_phones = []
        seen_normalized = set()
        
        for match in matches:
            if isinstance(match, tuple):
                match = match[0] if match else ''
            
            if match:
                cleaned = self._clean_phone(match)
                if cleaned and self._validate_phone(cleaned):
                    normalized = re.sub(r'\D', '', cleaned)
                    if normalized not in seen_normalized:
                        unique_phones.append(cleaned)
                        seen_normalized.add(normalized)
        
        return unique_phones
    
    def _clean_phone(self, phone: str) -> str:
        """
        Clean phone number formatting.
        args:
            phone (str): Raw phone number string.
        Returns:
            str: Cleaned phone number string.
        """
        # Keep only valid phone characters
        phone = re.sub(r'[^0-9().\-\s]', '', phone)
        # Normalize whitespace
        phone = ' '.join(phone.split())
        return phone.strip()
    
    def _validate_phone(self, phone: str) -> bool:
        """
        Validate phone number.
        Args:
            phone (str): Cleaned phone number string.
        Returns:
            bool: True if valid phone number, False otherwise.
        """
        digits = re.sub(r'\D', '', phone)
        return len(digits) in [7, 10]  # US phone formats


class OfficeInformationDetector:
    """
    Main office information detector - combines all field detectors.
    This detector identifies office information commonly found in academic syllabi. 
    It searches for patterns describing:
    - Office location
    - Office hours
    - Office Phone number

    Attributes:
        field_name (str): The name of the field being detected ('office_information').
        logger (logging.Logger): Logger instance for this detector.
        location_detector (LocationDetector): Detector for office location.
        hours_detector (HoursDetector): Detector for office hours.
        phone_detector (PhoneDetector): Detector for office phone number.
    """

    def __init__(self):
        """
        Initialize the office information detector with all sub-detectors.
        Sets up the field name, logger, location_detector, hours_detector, phone_detector, and compiles
        the list of regex patterns used to detect office information declarations.
        """
        self.field_name = 'office_information'
        self.logger = logging.getLogger('detector.office_information')

        # Initialize specialized sub-detectors
        self.location_detector = LocationDetector()
        self.hours_detector = HoursDetector()
        self.phone_detector = PhoneDetector()

    def detect(self, text: str) -> Dict[str, Any]:
        """
        Detect all office information declarations in the text.

        Args:
            text (str): Document text to analyze

        Returns:
            Dict[str, Any]: Detection result with office information if found
        """
        self.logger.info(f"Starting detection for field: {self.field_name}")

        # Run each detector independently
        location_result = self.location_detector.detect(text)
        hours_result = self.hours_detector.detect(text)
        phone_result = self.phone_detector.detect(text)

        # Compile results into unified structure
        result = {
            'field_name': self.field_name,
            'office_location': {
                'found': location_result.found,
                'content': location_result.content,
                'all_matches': location_result.all_matches
            },
            'office_hours': {
                'found': hours_result.found,
                'content': hours_result.content,
                'all_matches': hours_result.all_matches
            },
            'phone': {
                'found': phone_result.found,
                'content': phone_result.content,
                'all_matches': phone_result.all_matches
            }
        }

        # Set overall found flag (true if ANY field was detected)
        result['found'] = any([
            location_result.found,
            hours_result.found,
            phone_result.found
        ])

        return result
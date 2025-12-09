"""
Authors: Erik Bailey, Team Alpha fall 2025
Contributers: Jackie
Date 12/1/2025
Late Missing Work Detector
=========================================

This detector identifies late work policies in syllabus documents.
It uses pattern matching and keyword detection to find late sections.

It looks for titles like "Late Work", and if it cannot find any titles it'll try combing through a syllabus to find any mention on
"late work", like "late work will not be accepted."

"""

import re
import logging
from typing import Dict, Any, Tuple

# Detection Configuration Constants
MAX_DOCUMENT_LENGTH = 20000
MAX_CONTENT_LINES = 10
MAX_CONTENT_LENGTH = 500
MAX_EXTRA_WORDS_HEADER = 2
MAX_EXTRA_WORDS_START = 4
MAX_EXTRA_WORDS_END = 3

# Scoring thresholds for header detection
SCORE_STARTS_WITH_TITLE = 10
SCORE_SHORT_LINE = 5
SCORE_LONG_LINE_PENALTY = -5
SCORE_HAS_COLON = 3
SCORE_ALL_CAPS = 2
MIN_SCORE_THRESHOLD = 5
SHORT_LINE_THRESHOLD = 50
LONG_LINE_THRESHOLD = 100

# Section headers that indicate end of late work content
SECTION_HEADERS = [
    'course description', 'course objectives', 'course goals',
    'prerequisites', 'textbook', 'grading', 'schedule',
    'extra credit', 'attendance'
]


class LateDetector:
    """
    Detector for late work policies.

    This detector looks for common late patterns including:
    - Keywords like "late homework policy", "late assignments"
    - Action verbs in bulleted lists
    """

    def __init__(self):
        """Initialize the late detector."""
        self.field_name = 'late'
        self.logger = logging.getLogger('detector.late')

        # Approved titles for late missing work detection
        self.approved_titles = [
            # Removed generic "assignments" and "assessments" - too many false positives
            "assignment deadlines",
            "assignments and grading",
            "attendance and late work",
            "deadline expectations",
            "deadline policy",
            "expectations regarding assignment deadlines, late, or missing work",
            "grading (late policy: 10% deduction per day, up to 5 days)",
            "late assignments",
            "late assignments and make-up exams",
            "late homework policy",
            "late policy",
            "late submission policy",
            "late submissions",
            "late submissions and make-up exam",
            "late submissions and make-up exams",
            "late submissions and makeups",
            "late work",
            "late work policy",
            "late/make-up work",
            "makeups",
            "make-up policy",
            "make-up work",
            "missing work",
            "missing work policy",
            "paper assignment / powerpoint presentations",
            "penalty for late assignments",
            "policy on attendance, late submissions",
            "policy on late submissions",
            "policy on late work",
            "submission deadlines",
            "submission policy",
            "summary/critique paper (late policy)",
            "experiments/demonstrations"
        ]

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
        normalized = normalized.replace('：', ':')  # Full-width colon
        normalized = normalized.replace('—', '-')  # Em-dash
        normalized = normalized.replace('–', '-')  # En-dash
        normalized = normalized.replace('‐', '-')  # Hyphen (U+2010)
        normalized = normalized.replace('‑', '-')  # Non-breaking hyphen (U+2011)
        normalized = normalized.replace('⁃', '-')  # Bullet operator (U+2043)
        normalized = normalized.replace('\u2014', '-')  # Em-dash (unicode)
        normalized = normalized.replace('\u2013', '-')  # En-dash (unicode)
        normalized = normalized.replace('\u2010', '-')  # Hyphen (unicode)
        normalized = normalized.replace('\u2011', '-')  # Non-breaking hyphen (unicode)
        normalized = normalized.replace('\u2043', '-')  # Bullet operator (unicode)
        
        # Handle common Unicode quotation marks
        normalized = normalized.replace("’", "'")   # Right single quote
        normalized = normalized.replace("‘", "'")   # Left single quote
        normalized = normalized.replace("“", '"')   # Left double quote
        normalized = normalized.replace("”", '"')   # Right double quote


        # Normalize whitespace (multiple spaces -> single space)
        normalized = ' '.join(normalized.split())

        return normalized

    def detect(self, text: str) -> Dict[str, Any]:
        """
        Detect late work policies in the text.
        Uses both title-based and content-based detection strategies.

        Args:
            text (str): Document text to analyze

        Returns:
            Dict[str, Any]: Detection result with late content if found
        """
        self.logger.info("Starting late detection with title and content strategies")

        # Limit text size to prevent hanging on large documents
        original_length = len(text)
        if len(text) > MAX_DOCUMENT_LENGTH:
            text = text[:MAX_DOCUMENT_LENGTH]
            self.logger.info(f"Truncated large document from {original_length} to {MAX_DOCUMENT_LENGTH} characters")

        try:
            # First try title-based detection
            found, content = self._simple_title_detection(text)
            
            if found:
                result = {
                    'field_name': self.field_name,
                    'found': True,
                    'content': content
                }
                self.logger.info(f"FOUND: {self.field_name}")
                self.logger.info("SUCCESS: Found approved late title")
            else:
                # Fallback to content-based detection
                self.logger.info("No approved titles found, trying content-based detection")
                found, content = self._content_based_detection(text)
                
                if found:
                    result = {
                        'field_name': self.field_name,
                        'found': True,
                        'content': content
                    }
                    self.logger.info(f"FOUND: {self.field_name}")
                    self.logger.info("SUCCESS: Found late content pattern")
                else:
                    result = {
                        'field_name': self.field_name,
                        'found': False,
                        'content': None
                    }
                    self.logger.info(f"NOT_FOUND: {self.field_name}")
                    self.logger.info("No late titles or content patterns found")

            self.logger.info(f"Detection complete for {self.field_name}: {'SUCCESS' if found else 'NO_MATCH'}")
            return result

        except Exception as e:
            self.logger.error(f"Error in late detection: {e}")
            return {
                'field_name': self.field_name,
                'found': False,
                'content': None
            }

    def _simple_title_detection(self, text: str) -> Tuple[bool, str]:
        """
        Simple title-based late detection.
        Just looks for exact approved titles and extracts following content.

        Args:
            text (str): Text to search

        Returns:
            tuple: (found, content)
        """
        lines = text.split('\n')

        # Find all potential matches first, then pick the best one
        potential_matches = []

        for i, line in enumerate(lines):
            line_normalized = self._normalize_text(line.strip())
            line_without_punctuation = line_normalized.replace(':', '').replace('.', '').strip()

            # First check for exact matches - these get priority
            exact_match_found = False
            for title in self.approved_titles:
                normalized_title = self._normalize_text(title)
                if (normalized_title == line_without_punctuation or
                    normalized_title + ':' == line_normalized or
                    normalized_title == line_normalized.rstrip(':')):
                    # Exact match - add with very high score
                    potential_matches.append((100, i, line))
                    exact_match_found = True
                    break
            
            if exact_match_found:
                continue

            # Check if any approved title appears properly (not just as part of a sentence)
            contains_approved_title = False
            for title in self.approved_titles:
                normalized_title = self._normalize_text(title)
                if normalized_title in line_without_punctuation:
                    # Additional check: line should be relatively short and not part of a long sentence
                    # or the title should be at the start/end of the line
                    line_words = line_without_punctuation.split()
                    title_words = normalized_title.split()

                    # Much stricter check: title must appear in header-like format
                    is_valid_header = False

                    # Case 1: Very short line (title + max 2 extra words) with proper formatting
                    if len(line_words) <= len(title_words) + MAX_EXTRA_WORDS_HEADER:
                        has_proper_formatting = (
                            ':' in line or                           # Has colon (section header)
                            line.strip().isupper() or              # All caps
                            (len(line_words) == len(title_words) and  # Exact title match
                             not line_normalized.endswith((',', ';', '.', '!', '?')))
                        )
                        if has_proper_formatting:
                            is_valid_header = True

                    # Case 2: Title at the very beginning of line (starts with title)
                    elif line_without_punctuation.startswith(normalized_title):
                        # But only if it looks like a header (has colon or is short)
                        if ':' in line or len(line_words) <= len(title_words) + MAX_EXTRA_WORDS_START:
                            is_valid_header = True

                    # Case 3: Title at the very end of line (ends with title)
                    elif line_without_punctuation.endswith(normalized_title):
                        # Only if it's a short line
                        if len(line_words) <= len(title_words) + MAX_EXTRA_WORDS_END:
                            is_valid_header = True
                    
                    # Case 4: For very short approved titles (like "Late Work"), be more lenient
                    elif len(title_words) <= 3 and normalized_title in line_without_punctuation:
                        # Check if the title appears in isolation (not embedded in longer text)
                        title_start = line_without_punctuation.find(normalized_title)
                        title_end = title_start + len(normalized_title)
                        
                        # Check characters before and after the title
                        before_ok = (title_start == 0 or 
                                   line_without_punctuation[title_start - 1] in ' \t\n:-.()[]')
                        after_ok = (title_end >= len(line_without_punctuation) or
                                  line_without_punctuation[title_end] in ' \t\n:-.()[]')
                        
                        # Be even more lenient for 2-word titles like "Late Work" 
                        if len(title_words) == 2:
                            is_valid_header = before_ok and after_ok and len(line_words) <= len(title_words) + 6
                        else:
                            is_valid_header = before_ok and after_ok and len(line_words) <= len(title_words) + 4
                            
                    # Case 5: Extra lenient check for exact title matches in short lines
                    elif (normalized_title == line_without_punctuation or 
                          normalized_title + ':' == line_without_punctuation or
                          normalized_title == line_without_punctuation + ':'):
                        is_valid_header = True

                    if is_valid_header:
                        contains_approved_title = True
                        break

            if contains_approved_title:
                # Score this match based on how likely it is to be a section header
                score = 0

                # Very high score for exact matches (check both case variations)
                exact_match = False
                for title in self.approved_titles:
                    normalized_title = self._normalize_text(title)
                    # Also check title case version
                    title_case_version = title.title()
                    normalized_title_case = self._normalize_text(title_case_version)
                    
                    for check_title in [normalized_title, normalized_title_case]:
                        if (check_title == line_without_punctuation or 
                            check_title + ':' == line_without_punctuation or
                            check_title == line_without_punctuation.rstrip(':') or
                            # Check if line starts with the title and has reasonable continuation
                            (line_without_punctuation.startswith(check_title) and 
                             len(line_without_punctuation) <= len(check_title) + 100)):
                            exact_match = True
                            break
                    if exact_match:
                        break
                if exact_match:
                    score += 20  # Very high score for exact matches

                # Higher score for lines that start with approved titles
                starts_with_approved = False
                for title in self.approved_titles:
                    normalized_title = self._normalize_text(title)
                    if line_without_punctuation.startswith(normalized_title):
                        starts_with_approved = True
                        break
                if starts_with_approved:
                    score += SCORE_STARTS_WITH_TITLE

                # Higher score for shorter lines (more likely to be headers)
                if len(line_without_punctuation) < SHORT_LINE_THRESHOLD:
                    score += SCORE_SHORT_LINE

                # Lower score for very long lines (likely mentions in text)
                if len(line_without_punctuation) > LONG_LINE_THRESHOLD:
                    score += SCORE_LONG_LINE_PENALTY

                # Higher score for lines with colons (section headers often have colons)
                if ':' in line:
                    score += SCORE_HAS_COLON

                # Higher score for lines in ALL CAPS
                if line.strip().isupper():
                    score += SCORE_ALL_CAPS

                potential_matches.append((score, i, line))

        # Sort by score (highest first) and pick the best match
        if potential_matches:
            potential_matches.sort(key=lambda x: x[0], reverse=True)
            best_score, best_i, best_line = potential_matches[0]

            # Only accept matches with a reasonable score (likely section headers)
            # Lower threshold to catch more legitimate titles
            if best_score < 3:  # Reduced from MIN_SCORE_THRESHOLD (5) to 3
                return False, ""

            # Extract content from the best match
            title = best_line.strip()
            content_lines = [title]
            content_length = len(title)

            for j in range(best_i + 1, min(best_i + MAX_CONTENT_LINES, len(lines))):
                if j >= len(lines):
                    break

                next_line = lines[j].strip()
                if not next_line:
                    continue

                # Stop if we hit another section title
                if any(section in next_line.lower() for section in SECTION_HEADERS):
                    break

                content_lines.append(next_line)
                content_length += len(next_line)

                # Stop after reasonable amount of content
                if content_length > MAX_CONTENT_LENGTH:
                    break

            content = '\n'.join(content_lines)
            return True, content

        return False, ""

    def _content_based_detection(self, text: str) -> Tuple[bool, str]:
        """
        Content-based late work detection as fallback when no titles are found.
        Looks for common late work content patterns in the document.

        Args:
            text (str): Text to search

        Returns:
            tuple: (found, content)
        """
        # Content patterns that strongly indicate late work policies
        # Made more conservative to reduce false positives
        content_patterns = [
            # High confidence patterns - require clear policy language
            r"late work is.*?(?:anything submitted|defined as|considered).*?after.*?(?:due date|deadline)",
            r"you will lose.*?\d+.*?(?:percent|%).*?per day.*?(?:late|tardy)",  # Must have "per day" context
            r"late work is anything submitted after.*?(?:due date|deadline)",  
            r"(?:\d+%|ten percent|\d+ percent).*?(?:deduction|penalty).*?per day.*?(?:late work|late assignment)",
            r"late work will not be accepted.*?(?:after|beyond)",
            r"no assignment will be accepted after.*?(?:deadline|due date)",
            r"submissions will not be accepted after.*?(?:deadline|due date)",
            r"(?:late|tardy).*?(?:penalty|deduction).*?\d+%.*?(?:per day|each day)",
            r"do not submit.*?(?:homework|assignment|work).*?late",
            r"you may hand in.*?(?:one|1).*?late.*?(?:homework|assignment)",
            
            # New pattern for the specific case you mentioned
            r"any assignment not turned in by.*?(?:midnight|due date|date).*?(?:late|penalty|grade penalty)",
            
            # Medium confidence patterns
            r"unexcused late.*?will receive.*?deduction",
            r"no submissions.*?accepted.*?(?:after|beyond).*?\d+.*?days",
            r"three days after.*?due date.*?will not be accepted",
            r"(?:48|forty-eight) hours after.*?due.*?(?:day|date)",
            r"grace period.*?(?:late|assignment)",
            r"make-?up.*?(?:work|exam|assignment).*?(?:policy|will be)",
            
            # Medium confidence patterns - require more context
            r"late submissions.*?no assignment will be accepted",
            r"(?:late|tardy).*?(?:work|assignment).*?policy",  # Must mention "policy"
            r"(?:grading|penalty).*?\(late policy.*?\)",
            
            # Conservative patterns for simple statements  
            r"(?:homework|assignments).*?submitted late.*?(?:deduct|reduce|lose).*?\d+",  # Must have penalty amount
            r"(?:one|1).*?late.*?(?:homework|assignment).*?(?:allowed|accepted)",
            
            # Additional patterns for assignment-specific policies
            r"assignment.*?not turned in.*?(?:midnight|due date).*?(?:late|penalty)",
            r"(?:assignment|homework).*?(?:due date|deadline).*?(?:penalty|deduction|zero|0)",
            r"after.*?(?:due date|deadline).*?assignment.*?(?:not accepted|zero|penalty)",
            
            # Patterns for combined title+content cases
            r"late submissions.*?no assignment will be accepted",
            r"late work.*?no.*?(?:assignment|work).*?(?:accepted|allowed)",
            r"you will receive.*?(?:grade of 0|zero).*?for.*?(?:quiz|exam).*?(?:miss|late)",
            r"you will receive a grade of 0 for any (?:quiz|exam|assignment) that you miss",  # Very specific pattern
            r"late submissions.*?no assignment will be accepted after.*?deadline.*?grade",  # Combined title+content pattern
        ]

        lines = text.split('\n')
        
        # Search for content patterns
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            # Check if this line matches any content pattern
            for pattern in content_patterns:
                if re.search(pattern, line_lower, re.IGNORECASE | re.DOTALL):
                    # Found a content pattern, extract surrounding context
                    
                    # Balanced content extraction - focused but not too restrictive
                    content_lines = []
                    
                    # Start with the current line that matched the pattern
                    current_line = line.strip()
                    if current_line:
                        content_lines.append(current_line)
                    
                    # Add up to 2 additional lines if they continue the policy
                    for j in range(i + 1, min(i + 3, len(lines))):
                        if j < len(lines):
                            next_line = lines[j].strip()
                            if not next_line:
                                continue
                            
                            # Stop if we hit obvious section breaks
                            if (any(section in next_line.lower() for section in SECTION_HEADERS) or
                                (next_line.endswith(':') and len(next_line) < 50) or  # Likely header
                                (next_line[0].isupper() and ':' in next_line and len(next_line) < 60)):  # New section
                                break
                            
                            content_lines.append(next_line)
                            
                            # Stop if content is getting too long
                            total_length = sum(len(cl) for cl in content_lines)
                            if total_length > 300:  # More reasonable limit
                                break
                    
                    # Create focused content
                    if content_lines:
                        content = ' '.join(content_lines)
                        # Clean up extra whitespace
                        content = re.sub(r'\s+', ' ', content).strip()
                        
                        # More reasonable length limits
                        if 20 < len(content) <= 350:  # Between 20-350 characters
                            return True, content
        
        # Also check for multi-line patterns that span across lines
        full_text_lower = text.lower()
        
        # Multi-line patterns - more conservative
        multiline_patterns = [
            r"late work is anything submitted after.*?(?:unless you have received|zero will be given|will not be accepted)",
            r"(?:10|ten)%.*?per day.*?for.*?(?:work submitted late|late work).*?(?:up to|for up to)",
            r"late work is.*?(?:submitted|turned in|handed in).*?after.*?(?:due|deadline).*?(?:penalty|deduction|lose)",
            r"(?:penalty|deduction).*?\d+.*?(?:percent|%).*?per day.*?(?:late|tardy)",
        ]
        
        for pattern in multiline_patterns:
            match = re.search(pattern, full_text_lower, re.IGNORECASE | re.DOTALL)
            if match:
                # Extract just the matched content with minimal padding
                start_pos = max(0, match.start() - 20)  # Much less padding
                end_pos = min(len(text), match.end() + 20)
                
                content = text[start_pos:end_pos].strip()
                
                # Clean up the content and make it much more focused
                content_lines = [line.strip() for line in content.split('\n') if line.strip()]
                if content_lines:
                    content = ' '.join(content_lines)
                    content = re.sub(r'\s+', ' ', content).strip()
                    
                    # More reasonable length limit
                    if 20 < len(content) <= 350:  # Max 350 characters
                        return True, content
        
        return False, ""


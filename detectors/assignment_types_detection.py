"""
Assignment Types Title Detector

Finds section headers about assignment types in syllabi.
Examples: "Homework Assignments", "Course Activities", "Assignments & Grading"

How it works:
1. Searches for assignment-related headers (homework, assignments, etc.)
2. Uses scoring system - more specific titles get higher scores
3. Skips grading policy headers (those belong to grading_procedures_title)
4. Skips schedule sections (weekly homework lists)
5. Returns highest-scoring match

Example:
    Input: "Homework Assignments (10%): Complete weekly problem sets"
    Output: "Homework Assignments:" (confidence: high)
"""
import re
from typing import Dict, Any

class AssignmentTypesDetector:
    """Finds assignment types section titles in syllabi"""
    
    def __init__(self):
        # Exact patterns - complete phrases that must be standalone
        # Format: (pattern, score)
        self.exact_patterns = [
            (r'(?i)^\s*assignments?\s*&\s*grades?\s*:?\s*$', 150),
            (r'(?i)^\s*assignments?\s*&\s*grading\s*:?\s*$', 150),
            (r'(?i)^\s*textbook\s+chapter\s+quizzes\s*,?\s*discussions', 140),
            (r'(?i)^\s*methods\s+of\s+testing\s+/\s+evaluation\s*:?\s*$', 135),
            (r'(?i)^\s*course\s+requirements?\s+and\s+assessments?\s+overview\s*:?\s*$', 135),
            (r'(?i)^\s*required\s+paperwork\s+and\s+submissions?\s*\.?\s*$', 130),
            (r'(?i)^\s*assignments?\s+and\s+course\s+specific\s+policies\s*:?\s*$', 130),
            (r'(?i)^\s*assignment\s+and\s+grading\s+details?\s+lab\s*:?\s*$', 125),
            (r'(?i)^\s*summary\s+of\s+student\s+evaluation\s*:?\s*$', 120),
            (r'(?i)^\s*methods\s*,\s*grade\s+components', 115),
        ]
        
        # Multiword standalone - phrases on their own line (higher scores)
        # Can include weight info like "(10%)" which we'll remove later
        self.multiword_standalone = [
            (r'(?i)^\s*homework\s+assignments?\s+and\s+projects?\s*(?:\([^)]+\))?\s*:?\s*$', 112),
            (r'(?i)^\s*reading\s+assignments?\s*(?:\([^)]+\))?\s*:?\s*$', 110),
            (r'(?i)^\s*laboratory\s+assignments?\s*(?:\([^)]+\))?\s*:?\s*$', 110),
            (r'(?i)^\s*lab\s+assignments?\s*(?:\([^)]+\))?\s*:?\s*$', 110),
            (r'(?i)^\s*homework\s+problems\s*(?:\([^)]+\))?\s*:?\s*$', 110),
            (r'(?i)^\s*homework\s+assignments?\s*(?:\([^)]+\))?\s*:?\s*$', 110),
            (r'(?i)^\s*course\s+assignments?\s*(?:\([^)]+\))?\s*:?\s*$', 108),
            (r'(?i)^\s*class\s+assignments?\s*(?:\([^)]+\))?\s*:?\s*$', 108),
            (r'(?i)^\s*assessment\s+overview\s*:?\s*$', 106),
            (r'(?i)^\s*major\s+projects?\s*:?\s*$', 105),
            (r'(?i)^\s*course\s+activities\s*:?\s*$', 105),
            (r'(?i)^\s*assignment\s+details?\s*:?\s*$', 102),
            (r'(?i)^\s*quizzes\s+and\s+exams?\s*:?\s*$', 100),
            (r'(?i)^\s*assignments?\s+and\s+grading\s*:?\s*$', 98),
            (r'(?i)^\s*student\s+evaluation\s*:?\s*$', 90),
            (r'(?i)^\s*assessment\s*,\s*participation\s+assignments?\s*:?\s*$', 88),
        ]
        
        # Multiword with content - header followed by text on same line (lower scores)
        # We extract just the header part using capture group
        self.multiword_with_content = [
            (r'(?i)^\s*(homework\s+assignments?\s+and\s+projects?)\s*(?:\([^)]+\))?\s*:', 87),
            (r'(?i)^\s*(reading\s+assignments?)\s*(?:\([^)]+\))?\s*:', 85),
            (r'(?i)^\s*(laboratory\s+assignments?)\s*(?:\([^)]+\))?\s*:', 85),
            (r'(?i)^\s*(lab\s+assignments?)\s*(?:\([^)]+\))?\s*:', 85),
            (r'(?i)^\s*(homework\s+problems)\s*(?:\([^)]+\))?\s*:', 85),
            (r'(?i)^\s*(homework\s+assignments?)\s*(?:\([^)]+\))?\s*:', 85),
            (r'(?i)^\s*(course\s+assignments?)\s*:', 83),
            (r'(?i)^\s*(class\s+assignments?)\s*:', 83),
            (r'(?i)^\s*(assessment\s+overview)\s*:', 81),
            (r'(?i)^\s*(major\s+projects?)\s*:', 80),
            (r'(?i)^\s*(course\s+activities)\s*:', 80),
            (r'(?i)^\s*(assignment\s+details?)\s*:', 77),
            (r'(?i)^\s*(quizzes\s+and\s+exams?)\s*:', 75),
            (r'(?i)^\s*(assignments?\s+and\s+grading)\s*:', 73),
            (r'(?i)^\s*(methods\s+of\s+testing\s*/\s*evaluation)\s*:', 130),
        ]
        
        # Singleword standalone - one word on its own line (higher scores)
        self.singleword_standalone = [
            (r'(?i)^\s*assessment\s*:?\s*$', 70),
            (r'(?i)^\s*homework\s*(?:\([^)]+\))?\s*:?\s*$', 65),
            (r'(?i)^\s*assignments?\s*:?\s*$', 60),
            (r'(?i)^\s*evaluation\s*:?\s*$', 50),
        ]
        
        # Singleword with content - one word followed by text (lower scores)
        self.singleword_with_content = [
            (r'(?i)^\s*(assessment)\s*:', 55),
            (r'(?i)^\s*(homework)\s*(?:\([^)]+\))?\s*:', 50),
            (r'(?i)^\s*(assignments?)\s*:', 45),
        ]
        
        # Schedule indicators - patterns that suggest this is a weekly schedule, not a section header
        self.schedule_patterns = [
            r'(?i)week\s*#?\d+',
            r'(?i)homework\s*:\s*(reading|complete|work\s+on|finish|continue|start)',
            r'(?i)due\s+(by\s+)?next\s+week',
            r'(?i)lecture\s*[-–]\s*review',
        ]
        
        # Exclude patterns - these belong to grading_procedures_title, NOT assignment_types_title
        # Important: Skip anything about grading policies/procedures/scales
        self.exclude_patterns = [
            r'(?i)grading\s+and\s+evaluation\s+of\s+student\s+work',
            r'(?i)evaluation\s+of\s+student\s+work',
            r'(?i)grading\s+policy',
            r'(?i)grading\s+procedure',
            r'(?i)grading\s+distribution',
            r'(?i)grading\s+scale',
            r'(?i)grade\s+distribution',
            r'(?i)final\s+grade\s+(calculation|scale)',
            r'(?i)course\s+grading',
            r'(?i)rubric\s+and\s+evaluation',
        ]
    
    def _is_in_schedule(self, line: str, context: str) -> bool:
        """Check if line is part of a weekly schedule section"""
        for p in self.schedule_patterns:
            if re.search(p, line):
                return True
        context_lower = context.lower()
        for kw in ['week #', 'homework: reading', 'due by next week']:
            if kw in context_lower:
                return True
        return False
    
    def _should_exclude(self, line: str) -> bool:
        """
        Check if line is a grading section header (should be excluded).
        These belong to grading_procedures_title, not assignment_types_title.
        """
        line_lower = line.lower().strip()
        
        for pattern in self.exclude_patterns:
            if re.search(pattern, line_lower):
                return True
        
        # If contains both "grading" and "evaluation", likely a grading procedures header
        if 'grading' in line_lower and 'evaluation' in line_lower:
            return True
            
        return False
    
    def _normalize_title(self, line: str) -> str:
        """
        Remove weight/percentage info from title.
        Example: "Homework Problems (10%)" -> "Homework Problems"
        """
        line = re.sub(r'\s*\([^)]+\)\s*', ' ', line)
        line = ' '.join(line.split())
        return line.strip()
    
    def _is_valid_with_content(self, line: str) -> bool:
        """Check if line with content after header is valid (not schedule-like)"""
        if len(line) > 200:
            return False
        if re.search(r'(?i)(reading|complete|work\s+on|due|week\s+\d+)', line):
            return False
        return True
    
    def detect(self, text: str) -> Dict[str, Any]:
        """
        Find assignment types section title in syllabus.
        
        Returns dict with 'found' (bool) and 'content' (str)
        Example: {'found': True, 'content': 'Homework Assignments:'}
        """
        if not text:
            return {"found": False, "content": ""}
        
        lines = text.split("\n")
        candidates = []
        
        for i, line in enumerate(lines):
            l = line.strip()
            
            if len(l) < 2 or len(l) > 250:
                continue
            
            # CRITICAL: Skip grading-related headers first
            if self._should_exclude(l):
                continue
            
            # Get surrounding context to check for schedules
            start, end = max(0, i - 5), min(len(lines), i + 6)
            context = " ".join(lines[start:end])
            
            if self._is_in_schedule(l, context):
                continue
            
            # Try patterns in order of specificity
            # 1. Exact patterns (highest scores)
            for pat, score in self.exact_patterns:
                if re.match(pat, l):
                    candidates.append({"content": l, "score": score, "line": i})
                    break
            else:
                # 2. Multiword standalone
                for pat, score in self.multiword_standalone:
                    if re.match(pat, l):
                        normalized = self._normalize_title(l)
                        candidates.append({"content": normalized, "score": score, "line": i})
                        break
                else:
                    # 3. Multiword with content
                    matched = False
                    for pat, score in self.multiword_with_content:
                        match = re.match(pat, l)
                        if match and self._is_valid_with_content(l):
                            header = match.group(1) + ":"
                            candidates.append({"content": header, "score": score, "line": i})
                            matched = True
                            break
                    
                    if not matched:
                        # 4. Singleword standalone
                        for pat, score in self.singleword_standalone:
                            if re.match(pat, l):
                                normalized = self._normalize_title(l)
                                candidates.append({"content": normalized, "score": score, "line": i})
                                matched = True
                                break
                        
                        if not matched:
                            # 5. Singleword with content
                            for pat, score in self.singleword_with_content:
                                match = re.match(pat, l)
                                if match and self._is_valid_with_content(l):
                                    header = match.group(1) + ":"
                                    candidates.append({"content": header, "score": score, "line": i})
                                    break
        
        if candidates:
            # Return highest scoring candidate (earlier line breaks ties)
            best = max(candidates, key=lambda x: (x["score"], -x["line"]))
            return {"found": True, "content": best["content"]}
        
        return {"found": False, "content": ""}


def detect_assignment_types_title(text: str) -> str:
    """Simple wrapper - returns title or 'Missing'"""
    detector = AssignmentTypesDetector()
    result = detector.detect(text)
    return result.get("content", "") if result.get("found") else "Missing"
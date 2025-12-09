"""
Authors: Jackie E, Team Alpha fall 2025
Date 12/1/2025

Grading scale detection module.

This module provides the GradingScaleDetector class for extracting letter-based grading scales 
from syllabus text by finding A-F grade patterns.

we literally just look for A-F grading scales. They need to have all 12 letters (A, A-, B+, B, etc...) to be considered

"""

from typing import Dict, Any, List, Set
import re
import logging

# Required grade letters - must have all 12
REQUIRED_GRADES = {'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F'}
# Optional grade letter
OPTIONAL_GRADES = {'A+'}
# All valid grades
ALL_VALID_GRADES = REQUIRED_GRADES | OPTIONAL_GRADES

class GradingScaleDetector:
    """
    Simple grading scale detector that looks for A-F grade patterns.
    
    Searches through the document to find all 12 required grades (A, A-, B+, B, B-, C+, C, C-, D+, D, D-, F)
    and optionally A+. Returns the complete block when found.
    """
    
    def __init__(self):
        """Initialize the detector."""
        self.field_name = 'grading_scale'
        self.logger = logging.getLogger('detector.grading_scale')
        
        # Pattern to match grade letters with optional + or -
        # More flexible pattern that handles various contexts
        self.grade_pattern = re.compile(r'([ABCDF][+-]?)(?=[\s:=\d]|$)', re.IGNORECASE)
    
    def find_grades_in_text(self, text: str) -> List[str]:
        """Find all grade letters in a piece of text."""
        matches = []
        
        # Pattern 1: Standard format (A:, A , A-, etc)
        standard_matches = self.grade_pattern.findall(text)
        matches.extend(standard_matches)
        
        # Pattern 2: After equals sign (90-100=A)
        equals_pattern = re.compile(r'=\s*([ABCDF][+-]?)', re.IGNORECASE)
        equals_matches = equals_pattern.findall(text)
        matches.extend(equals_matches)
        
        # Normalize to uppercase and filter to valid grades only
        valid_grades = []
        for match in matches:
            normalized = match.upper()
            if normalized in ALL_VALID_GRADES:
                valid_grades.append(normalized)
        
        return valid_grades
    
    def has_all_required_grades(self, found_grades: Set[str]) -> bool:
        """Check if we found all 12 required grades."""
        return REQUIRED_GRADES.issubset(found_grades)
    
    def extract_block(self, lines: List[str], start_idx: int) -> str:
        """Extract a block of text that contains the grading scale."""
        found_grades = set()
        block_lines = []
        
        # Look through lines starting from start_idx
        for i in range(start_idx, len(lines)):
            line = lines[i].strip()
            if not line:
                continue
                
            # Find grades in this line
            line_grades = self.find_grades_in_text(line)
            
            if line_grades:
                # This line has grades, add it to our block
                block_lines.append(line)
                found_grades.update(line_grades)
                
                # Check if we have all required grades
                if self.has_all_required_grades(found_grades):
                    # We found a complete scale!
                    block_text = " ".join(block_lines)
                    
                    # Clean the block text to remove extra content
                    cleaned_block = self.clean_grading_scale_block(block_text)
                    
                    # Limit to 300 characters
                    if len(cleaned_block) <= 300:
                        return cleaned_block
                    else:
                        # Try to truncate at a reasonable point
                        truncated = cleaned_block[:300]
                        # If we still have all required grades in the truncated version
                        if self.has_all_required_grades(set(self.find_grades_in_text(truncated))):
                            return truncated
                
                # If block is getting too long without finding all grades, give up
                if len(" ".join(block_lines)) > 400:
                    break
            else:
                # Line has no grades
                if found_grades:
                    # We already found some grades, so this might be end of scale
                    # But let's check one more line in case grades continue
                    if i + 1 < len(lines):
                        next_line_grades = self.find_grades_in_text(lines[i + 1])
                        if not next_line_grades:
                            # No more grades coming, stop here
                            break
                    else:
                        break
        
        return ""
    
    def clean_grading_scale_block(self, text: str) -> str:
        """Clean the grading scale block to remove extra text and keep only the scale."""
        import re
        
        # Remove common prefixes that aren't part of the scale
        prefixes_to_remove = [
            r'^.*?guidelines using this schema:\s*',
            r'^.*?grading scale:\s*',
            r'^.*?final grades.*?scale:\s*',
            r'^.*?letter grades?\s*are\s*as\s*follows?:\s*',
            r'^.*?grading\s*criteria:?\s*',
            r'^.*?scale\s*is:?\s*',
        ]
        
        for prefix in prefixes_to_remove:
            text = re.sub(prefix, '', text, flags=re.IGNORECASE)
        
        # Remove assignment percentages and other non-scale content
        # Pattern to match things like "E-Portfolio 20%" or "Assignment 30%"
        text = re.sub(r'\b[A-Z][\w\-]*\s+\d+%\b', '', text)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # If the text starts with a grade letter, we're good
        if re.match(r'^[A-F][+-]?', text.strip()):
            return text.strip()
        
        # Try to find where the actual scale starts
        grade_start = re.search(r'\b([A-F][+-]?)\s*[:=<>\d]', text)
        if grade_start:
            return text[grade_start.start():].strip()
        
        return text.strip()
    
    def detect(self, text: str) -> Dict[str, Any]:
        """
        Detect grading scale in the text.
        
        Args:
            text (str): The syllabus text to search.
            
        Returns:
            Dict[str, Any]: Dictionary with 'found', 'content', and 'grades_found'.
        """
        self.logger.info(f"Starting detection for field: {self.field_name}")
        
        lines = text.split('\n')
        
        # Go through each line looking for grades
        for i, line in enumerate(lines):
            line_grades = self.find_grades_in_text(line)
            
            if line_grades:
                # Found some grades, try to extract a block starting here
                block = self.extract_block(lines, i)
                
                if block:
                    # Verify the block has all required grades
                    block_grades = set(self.find_grades_in_text(block))
                    if self.has_all_required_grades(block_grades):
                        self.logger.info(f"FOUND: {self.field_name} - Grades: {sorted(block_grades)}")
                        return {
                            'found': True,
                            'content': block,
                            'grades_found': sorted(list(block_grades))
                        }
        
        # No valid grading scale found
        self.logger.info(f"NOT_FOUND: {self.field_name}")
        return {
            'found': False,
            'content': 'Missing',
            'grades_found': []
        }

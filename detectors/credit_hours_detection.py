"""
Credit Hours Detector (Simplified)
===================================

This detector identifies explicit credit hour declarations in syllabus documents.
It looks for direct mentions of credit numbers only.

Developer Notes:
---------------
Simplified to only detect explicit credit statements like "4 credits", "3-credit", etc.
"""

import re
import logging
from typing import Dict, Any, Optional


class CreditHoursDetector:
    """
    Simplified detector for Credit Hours information.
    
    Only looks for explicit credit declarations with numbers.
    """
    
    def __init__(self):
        """Initialize the Credit Hours detector."""
        self.field_name = 'credit_hours'
        self.logger = logging.getLogger('detector.credit_hours')
        
        # Simple patterns for credit declarations
        # These patterns capture the number and surrounding credit text
        self.credit_patterns = [
            # "4 credits", "3 credit", "4.0 credits"
            r'(\d+(?:\.\d+)?)\s*credits?\b',

            # "(4 credit hour)", "(3.0 credit hours)"
            r'(\(\d+(?:\.\d+)?)\s*credits?\shour\s\)\b',
            
            # "4-credit", "3-credit course"
            r'(\d+(?:\.\d+)?)-credits?\b',
            
            # "(4-credits)", "(3-credit)"
            r'\((\d+(?:\.\d+)?)-credits?\)\b',

            # "Credits: 4", "Credit: 3.0"
            r'\bCredits?:\s*(\d+(?:\.\d+)?)\b',
            
            # "Variable credits 3-5", "Variable credits 2–4"
            r'\bVariable credits\s*(\d+\s*[-–]\s*\d+)\b',

            # "credit hours: 4", "Credit Hours: 3"
            r'\bCredit\s+Hours?:\s*(\d+(?:\.\d+)?)\b',

            # "4.0 credit course", "3 credit hours"
            r'(\d+(?:\.\d+)?)\s*credit\s+(?:hours?|course)\b',
            
            # "This is a 4-credit course"
            r'\ba\s+(\d+(?:\.\d+)?)-credits?\s+course\b',
            
            # "A three-credit hour course", "A 4 credit hours"
            r'\b[aA]n?\s+(?:(?:zero|one|two|three|four|five|six)|\d+)[-\s]?credits?\s+hours?\b',

            # "A 4-credit course"
            r'\ba\s+(\d+(?:\.\d+)?)-credits?\s+course\b',
                        
            # "4 cr.", "3 cr.", "4.0 cr."
            r'(\d+(?:\.\d+)?)\s*cr\.?\b',
            
            # "This is a 4.0 credit course"
            r'\ba\s+(\d+(?:\.\d+)?)\s*credits?\s+course\b',
        ]
        
    def detect(self, text: str) -> Dict[str, Any]:
        """
        Detect explicit Credit Hours declarations in the text.
        
        Args:
            text (str): Document text to analyze
            
        Returns:
            Dict[str, Any]: Detection result with credit hours if found
        """
        self.logger.info("Starting simplified Credit Hours detection")
        
        # Limit text size
        if len(text) > 20000:
            text = text[:20000]
            
        try:
            # Look for explicit credit mentions
            found, credit_text = self._find_credits(text)
            
            if found:
                result = {
                    'field_name': self.field_name,
                    'found': True,
                    'content': credit_text
                }
                self.logger.info(f"FOUND: {credit_text}")
            else:
                result = {
                    'field_name': self.field_name,
                    'found': False,
                    'content': "Missing"
                }
                self.logger.info("NOT_FOUND: No explicit credit declaration")
                
            return result
            
        except Exception as e:
            self.logger.error(f"Error in Credit Hours detection: {e}")
            return {
                'field_name': self.field_name,
                'found': False,
                'content': "ERROR"
            }
    
    def _find_credits(self, text: str) -> tuple[bool, Optional[str]]:
        """
        Find explicit credit declarations in text.

        Args:
            text (str): Text to search

        Returns:
            tuple: (found, credit_text)
        """
        # Search in the first 5000 characters to catch credits mentioned in course info
        # Increased from 3000 to handle syllabi where credit info appears later
        search_text = text[:5000]

        # Collect all potential matches with their positions
        candidates = []

        for pattern in self.credit_patterns:
            for match in re.finditer(pattern, search_text, re.IGNORECASE):
                full_match = match.group(0)
                position = match.start()

                # Get context around the match
                start = max(0, match.start() - 30)
                end = min(len(search_text), match.end() + 100)
                context = search_text[start:end].lower()

                # Skip if it's about prerequisites or other courses
                skip_keywords = [
                    'prerequisite', 'prereq', 'corequisite', 'co-requisite',
                    'must have completed', 'required before', 'prior to taking',
                    'must complete', 'completion of', 'before taking'
                ]
                if any(keyword in context for keyword in skip_keywords):
                    self.logger.debug(f"Skipping prerequisite mention: {full_match}")
                    continue

                # Skip if it's about repeating/retaking courses (maximum credits)
                repeat_keywords = [
                    'may be repeated', 'can be repeated', 'maximum of',
                    'may be retaken', 'up to', 'for a maximum'
                ]
                if any(keyword in context for keyword in repeat_keywords):
                    self.logger.debug(f"Skipping repeat/maximum mention: {full_match}")
                    continue

                # Extract just the number from the match
                number_match = re.search(r'(\d+(?:\.\d+)?)', full_match)
                if number_match:
                    credit_number = float(number_match.group(1))

                    # Sanity check: typical course credits are 0 to 12
                    # Allow 0-credit courses (co-requisites, labs, etc.)
                    # This filters out obvious false positives like CRNs
#                    if not (0.0 <= credit_number <= 12.0):
                    if not (credit_number <= 12.0):
                        self.logger.debug(f"Skipping unrealistic credit value: {full_match}")
                        continue

                # Clean up the match text
                credit_text = full_match.strip()

                # Don't normalize - return exact text as it appears in the PDF
                # This ensures we match the ground truth exactly

                # Add to candidates with position (earlier is better)
                candidates.append((position, credit_text))
                self.logger.debug(f"Found potential credit: {credit_text} at position {position}")

        # If we found candidates, return the earliest one
        # (credits are typically mentioned near the top of the syllabus)
        if candidates:
            candidates.sort(key=lambda x: x[0])  # Sort by position
            _, best_match = candidates[0]
            self.logger.info(f"Found credit declaration: {best_match}")
            return True, best_match

        return False, None
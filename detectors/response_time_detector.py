"""
Response Time Detector

Finds instructor email response time commitments in syllabi.
Examples: "within 24 hours", "24-48 hours", "one business day"

How it works:
1. Finds contact/communication sections in syllabus
2. Searches for time commitments using comprehensive patterns
3. Filters out false positives (assignment deadlines, tech support)
4. Validates matches have explicit time mentions
5. Returns best match with highest score

Example:
    Input: "I respond to emails within 24 hours on weekdays"
    Output: "within 24 hours on weekdays"
"""

import re
from typing import Dict, Any, List, Tuple


class ResponseTimeDetector:
    """Detects instructor email response time commitments"""

    def __init__(self):
        self.field_name = 'response_time'
        
        # ================================================================
        # COMPREHENSIVE REGEX PATTERNS
        # Organized by phrase type for better maintainability
        # ================================================================
        
        self.time_patterns = [
            # Group 1: Direct "Response Time" mentions
            r'(?i)response\s+time\s*:?\s*([^\n.;]{0,100}?(?:\d+(?:-\d+)?\s*(?:hour|hr|day|business\s+day)s?[^\n.;]{0,50}?))',
            r'(?i)email\s+response\s+time\s*:?\s*([^\n.;]{0,80})',
            r'(?i)(\d+(?:-\d+)?\s*(?:hour|hr|day|business\s+day)s?)\s+response\s+time',
            
            # Group 2: "Within" patterns (most common)
            r'(?i)(within\s+\d+(?:-\d+)?\s*(?:hour|hr|day|business\s+day)s?(?:\s+on\s+\w+)?(?:\s*\([^)]{0,30}\))?)',
            r'(?i)(within\s+one\s+(?:business\s+)?day)',
            r'(?i)(within\s+a\s+(?:business\s+)?day)',
            r'(?i)(within\s+24-48\s*hours?)',
            r'(?i)(within\s+24\s*hours?)',
            r'(?i)(within\s+48\s*hours?)',
            
            # Group 3: "I respond/reply within..." patterns
            r'(?i)I\s+(?:will\s+)?(?:respond|reply|get\s+back|answer)\s+(within\s+\d+(?:-\d+)?\s*(?:hour|hr|day|business\s+day)s?)',
            r'(?i)I\s+(?:will\s+)?(?:respond|reply|get\s+back|answer)\s+(in\s+\d+(?:-\d+)?\s*(?:hour|hr|day|business\s+day)s?)',
            r'(?i)I\s+(?:will\s+)?(?:respond|reply|get\s+back|answer)\s+(by\s+(?:the\s+)?next\s+(?:business\s+)?(?:day|weekday))',
            r'(?i)I\'ll\s+(?:respond|reply|get\s+back|answer)\s+(within\s+\d+(?:-\d+)?\s*(?:hour|hr|day)s?)',
            r'(?i)I\'ll\s+(?:respond|reply|get\s+back|answer)\s+(in\s+\d+(?:-\d+)?\s*(?:hour|hr|day)s?)',
            
            # Group 4: "Respond within..." (without "I")
            r'(?i)(?:respond(?:s)?|reply|replies?|get\s+back|answer)\s+(within\s+\d+(?:-\d+)?\s*(?:hour|hr|day|business\s+day)s?(?:\s+on\s+\w+)?)',
            r'(?i)(?:respond(?:s)?|reply|replies?|get\s+back|answer)\s+(in\s+\d+(?:-\d+)?\s*(?:hour|hr|day|business\s+day)s?)',
            
            # Group 5: "Typically/Usually" patterns
            r'(?i)(typically|usually|generally)\s+(?:respond(?:s)?|reply|replies?|get\s+back|answer)?\s*(?:to\s+emails?\s*)?(within\s+\d+(?:-\d+)?\s*(?:hour|hr|day)s?(?:\s*\([^)]{0,30}\))?)',
            r'(?i)(typically|usually|generally)\s+(?:respond(?:s)?|reply|replies?|get\s+back|answer)?\s*(?:to\s+emails?\s*)?(in\s+\d+(?:-\d+)?\s*(?:hour|hr|day)s?)',
            r'(?i)(typically|usually|generally)\s+(within\s+\d+(?:-\d+)?\s*(?:hour|hr|day)s?)',
            
            # Group 6: "You'll/You will" patterns
            r'(?i)you(?:\'ll|\s+will)\s+(?:get\s+a\s+)?(?:response|reply|hear\s+from\s+me)\s+(within\s+\d+(?:-\d+)?\s*(?:hour|hr|day)s?)',
            r'(?i)you(?:\'ll|\s+will)\s+(?:get\s+a\s+)?(?:response|reply|hear\s+from\s+me)\s+(in\s+\d+(?:-\d+)?\s*(?:hour|hr|day)s?)',
            r'(?i)you\s+(?:can\s+)?expect\s+(?:a\s+)?(?:response|reply)\s+(within\s+\d+(?:-\d+)?\s*(?:hour|hr|day)s?)',
            r'(?i)you\s+(?:can\s+)?expect\s+(?:a\s+)?(?:response|reply)\s+(in\s+\d+(?:-\d+)?\s*(?:hour|hr|day)s?)',
            r'(?i)you\s+(?:can\s+)?expect\s+to\s+hear\s+(?:from\s+me\s+)?(within\s+\d+(?:-\d+)?\s*(?:hour|hr|day)s?)',
            
            # Group 7: "Expect" patterns (without "you")
            r'(?i)expect\s+(?:a\s+)?(?:response|reply)\s+(within\s+\d+(?:-\d+)?\s*(?:hour|hr|day)s?)',
            r'(?i)expect\s+(?:a\s+)?(?:response|reply)\s+(in\s+\d+(?:-\d+)?\s*(?:hour|hr|day)s?)',
            
            # Group 8: "No later than" patterns
            r'(?i)(?:respond|reply|get\s+back|answer)\s+no\s+later\s+than\s+(next\s+(?:business\s+)?(?:day|weekday))',
            r'(?i)(?:respond|reply|get\s+back|answer)\s+no\s+later\s+than\s+(\d+(?:-\d+)?\s*(?:hour|hr|day)s?)',
            r'(?i)I\'ll\s+(?:respond|reply|get\s+back|answer)\s+no\s+later\s+than\s+(next\s+(?:business\s+)?(?:day|weekday))',
            r'(?i)I\'ll\s+(?:respond|reply|get\s+back|answer)\s+no\s+later\s+than\s+(\d+(?:-\d+)?\s*(?:hour|hr|day)s?)',
            
            # Group 9: "By" patterns
            r'(?i)(?:respond|reply|get\s+back|answer)\s+(by\s+(?:the\s+)?next\s+(?:business\s+)?(?:day|weekday))',
            r'(?i)I\'ll\s+(?:respond|reply|get\s+back|answer)\s+(by\s+(?:the\s+)?next\s+(?:business\s+)?(?:day|weekday))',
            r'(?i)(by\s+(?:the\s+)?next\s+(?:business\s+)?(?:day|weekday))',
            
            # Group 10: Specific common formats
            r'(?i)(24-48\s*hours?)',
            r'(?i)(24\s*hours?)(?:\s+on\s+\w+)?',
            r'(?i)(48\s*hours?)(?:\s+on\s+\w+)?',
            r'(?i)(one\s+(?:business\s+)?day)',
            r'(?i)(a\s+(?:business\s+)?day)',
            r'(?i)(\d+\s+business\s+days?)',
            r'(?i)(same\s+(?:business\s+)?day)',
            r'(?i)(next\s+(?:business\s+)?(?:day|weekday))',
            
            # Group 11: "Responses/Replies" (plural)
            r'(?i)(?:responses|replies)\s+(?:are\s+)?(?:typically|usually|generally)?\s*(?:sent\s+)?(within\s+\d+(?:-\d+)?\s*(?:hour|hr|day)s?)',
            r'(?i)(?:responses|replies)\s+(?:are\s+)?(?:typically|usually|generally)?\s*(?:sent\s+)?(in\s+\d+(?:-\d+)?\s*(?:hour|hr|day)s?)',
            
            # Group 12: "Receive" patterns
            r'(?i)(?:you\s+(?:will\s+|\'ll\s+)?)?receive\s+(?:a\s+)?(?:response|reply)\s+(within\s+\d+(?:-\d+)?\s*(?:hour|hr|day)s?)',
            r'(?i)(?:you\s+(?:will\s+|\'ll\s+)?)?receive\s+(?:a\s+)?(?:response|reply)\s+(in\s+\d+(?:-\d+)?\s*(?:hour|hr|day)s?)',
        ]
        
        # Keywords that indicate contact/communication sections
        self.contact_keywords = [
            'contact', 'email', 'office hour', 'communication',
            'preferred contact', 'reach me', 'get in touch',
            'response time', 'availability', 'questions'
        ]

    def _find_contact_windows(self, text: str) -> List[Tuple[int, int]]:
        """Find sections of text about contact/communication"""
        if not text:
            return []
        
        windows = []
        
        # Find sections near contact keywords
        for keyword in self.contact_keywords:
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            for match in pattern.finditer(text):
                start = max(0, match.start() - 200)
                end = min(len(text), match.end() + 800)
                windows.append((start, end))
        
        # Also look for response time patterns directly
        response_indicators = [
            r'(?i)(?:respond|reply|get\s+back|answer).*(?:within|in)\s+\d+',
            r'(?i)(?:within|in)\s+\d+.*(?:respond|reply|get\s+back)',
            r'(?i)response\s+time',
            r'(?i)I\s+(?:will\s+)?(?:respond|reply|get\s+back)',
        ]
        
        for pattern in response_indicators:
            for match in re.finditer(pattern, text):
                start = max(0, match.start() - 300)
                end = min(len(text), match.end() + 300)
                windows.append((start, end))
        
        if not windows:
            return []
        
        # Merge overlapping windows
        windows.sort()
        merged = [windows[0]]
        for start, end in windows[1:]:
            if start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        
        return merged

    def _extract_contact_text(self, text: str) -> str:
        """Extract contact-related sections from syllabus"""
        windows = self._find_contact_windows(text)
        
        if not windows:
            # Fallback to first chunk if no contact keywords
            first_chunk = text[:2000]
            if re.search(r'(?i)(email|contact)', first_chunk):
                return first_chunk
            return ""
        
        contact_text = ""
        for start, end in windows:
            contact_text += text[start:end] + "\n"
        
        return contact_text

    def _has_explicit_time(self, text: str) -> bool:
        """Check if text has explicit time mention (not vague)"""
        if not text:
            return False
        
        text_lower = text.lower()
        
        # Check for time units
        has_time_unit = bool(re.search(r'\d+\s*(?:hour|hr|day|business\s+day)s?', text_lower))
        if not has_time_unit:
            has_time_unit = bool(re.search(r'next\s+(?:business\s+)?(?:day|weekday)', text_lower))
        if not has_time_unit:
            has_time_unit = bool(re.search(r'(?:one|a)\s+(?:business\s+)?day', text_lower))
        
        # Exclude vague terms
        vague_terms = ['may vary', 'varies', 'depends', 'as soon as possible', 'asap', 'promptly', 'quickly']
        has_vague = any(term in text_lower for term in vague_terms)
        
        return has_time_unit and not has_vague

    def _is_false_positive(self, text: str, context: str = "") -> bool:
        """
        Filter out false positives like assignment deadlines, tech support, etc.
        Returns True if this is NOT about instructor email response time.
        """
        if not text:
            return False
        
        text_lower = text.lower()
        context_lower = context.lower() if context else ""
        combined = (text_lower + " " + context_lower).strip()
        
        # If no response context, likely false positive (unless says "response time")
        if 'response time' not in text_lower:
            has_response_context = any(word in combined for word in [
                'email', 'respond', 'reply', 'contact', 'reach', 'get in touch', 
                'reach out', 'message', 'communication'
            ])
            if not has_response_context:
                return True
        
        # Assignment grading turnaround (NOT instructor email response)
        grading_turnaround_patterns = [
            r'assignments?\s+(?:will\s+)?(?:be\s+)?(?:returned|graded)',
            r'(?:returned|graded).*assignments?',
            r'once\s+(?:they\s+are\s+)?graded',
            r'graded.*(?:within|in)\s+\d+',
            r'(?:within|in)\s+\d+.*graded',
            r'returned\s+via.*(?:within|in)\s+\d+',
            r'turnaround.*(?:within|in)\s+\d+',
            r'(?:within|in)\s+\d+.*turnaround',
            r'feedback.*(?:within|in)\s+\d+.*(?:graded|returned)',
        ]
        for pattern in grading_turnaround_patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                return True
        
        # Student must contact instructor (NOT instructor response)
        student_must_contact_patterns = [
            r'student\s+(?:must|should|need\s+to)\s+(?:contact|notify|email|reach)',
            r'you\s+(?:must|should|need\s+to)\s+(?:contact|notify|email|reach)',
            r'(?:contact|notify|email).*(?:instructor|professor).*(?:within|in)\s+\d+',
            r'(?:within|in)\s+\d+.*(?:of|after).*(?:missed|absence|exam)',
            r'must\s+(?:contact|notify|email|reach).*(?:within|in)\s+\d+',
            r'(?:within|in)\s+\d+.*of\s+the\s+missed',
        ]
        for pattern in student_must_contact_patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                return True
        
        # Class absence notification deadlines
        absence_notification_patterns = [
            r'miss(?:ing|ed)?\s+(?:a\s+)?class',
            r'absence.*(?:before|after|within)',
            r'(?:before|after).*absence',
            r'email.*(?:instructor|professor).*(?:about|regarding).*(?:absence|missing)',
            r'notify.*(?:instructor|professor).*(?:absence|missing)',
            r'inform.*(?:instructor|professor).*(?:absence|missing)',
            r'contact.*(?:instructor|professor).*(?:about|regarding).*(?:absence|missing)',
            r'(?:absence|missing).*(?:before|after|within).*(?:email|contact|notify)',
            r'if\s+you\s+miss\s+(?:a\s+)?class',
            r'take\s+(?:the\s+)?responsibility',
            r'make\s+up.*absence',
            r'circumstances\s+for\s+missing',
        ]
        for pattern in absence_notification_patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                return True
        
        # Grade disputes and grading-related
        grade_related_patterns = [
            r'discrepanc(?:y|ies)',
            r'grade.*(?:published|posted|dispute|error|mistake|concern)',
            r'(?:published|posted).*grade',
            r'contact.*me.*regarding.*(?:grade|discrepanc)',
            r'if.*you.*(?:disagree|question).*grade',
            r'grading.*(?:error|mistake|concern)',
            r'final.*grade.*(?:posted|published)',
            r'regrade.*request',
            r'appeal.*grade',
        ]
        for pattern in grade_related_patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                return True
        
        # "More than X" is usually NOT response time
        if re.search(r'more\s+than\s+\d+|more\s+than\s+a\s+(?:day|hour)', combined, re.IGNORECASE):
            return True
        
        # Student absence/health/performance contexts
        student_absence_patterns = [
            r'student\s+(?:health|support|success|absence|performance)',
            r'extenuating\s+circumstance',
            r'unavailable.*(?:day|hour)',
            r'affect.*performance',
            r'extended\s+absence',
            r'personal.*(?:health|matter)',
            r'dealing\s+with',
            r'keep\s+you\s+unavailable',
        ]
        for pattern in student_absence_patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                return True
        
        # Assignment/deadline patterns
        deadline_indicators = [
            r'\bassignments?\b.*(?:due|submit|turn\s+in)',
            r'(?:due|submit|turn\s+in).*\bassignments?\b',
            r'\bhomeworks?\b.*(?:due|submit)',
            r'(?:due|submit).*\bhomeworks?\b',
            r'\bexams?\b.*(?:due|submit)',
            r'\bquizz?(?:es)?\b.*(?:due|submit)',
            r'\btests?\b.*(?:due|submit)',
            r'\bprojects?\b.*(?:due|submit)',
            r'\bdeadline\b.*\bfor\b',
            r'\blate\b.*(?:penalty|points|grade)',
            r'(?:late|missing).*(?:work|assignment|homework)',
        ]
        
        for pattern in deadline_indicators:
            if re.search(pattern, combined, re.IGNORECASE):
                # Make sure it's not about email response
                if not re.search(r'email|respond|reply|contact', combined, re.IGNORECASE):
                    return True
        
        # Tech support patterns
        tech_support_patterns = [
            r'tech(?:nical)?\s+(?:help|support).*(?:\d+\s*hours?|24/7)',
            r'help\s+desk.*available',
            r'support\s+(?:is\s+)?available',
            r'canvas\s+support',
            r'\bit\s+support',
            r'24/7.*support',
            r'support.*24/7',
            r'hotline.*\d+\s*hours?',
            r'\d+\s*hours?.*hotline',
            r'\d+\s*hours?\s+a\s+day.*(?:seven|7)\s+days',
            r'(?:seven|7)\s+days.*\d+\s*hours?\s+a\s+day',
            r'for\s+tech\s+help',
            r'sharpp|ywca|crisis|domestic\s+violence|sexual\s+assault',
            r'emergency.*\d{3}-\d{3}-\d{4}',
            r'counseling.*available',
            r'help.*button.*canvas',
            r'walkthroughs.*tutorials',
        ]
        for pattern in tech_support_patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                return True
        
        # Course duration/hours
        duration_patterns = [
            r'course\s+runs',
            r'total\s+(?:credit\s+)?hours',
            r'credit\s+hours',
            r'hours?\s+per\s+week',
            r'hours?\s+of\s+instruction',
            r'contact\s+hours',
            r'lecture\s+hours',
            r'class\s+meets.*hours',
        ]
        for pattern in duration_patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                return True
        
        return False

    def _clean_response_time(self, text: str) -> str:
        """Clean and normalize response time text"""
        if not text:
            return ""
        
        text = ' '.join(text.split())
        text = re.sub(r'(?i)^response\s+time\s*:?\s*', '', text)
        text = text.lstrip('-–—').strip()
        text = text.rstrip('.,;:')
        
        # Normalize formats
        text = re.sub(r'(\d+)\s*-\s*(\d+)', r'\1-\2', text)
        text = re.sub(r'(\d+)(hours?|hrs?|days?)', r'\1 \2', text)
        text = re.sub(r'(\d+)\s+(hour|hr|day)\b', r'\1 \2s', text)
        text = ' '.join(text.split())
        
        return text.strip()

    def detect(self, text: str) -> Dict[str, Any]:
        """
        Detect instructor email response time commitment.
        
        Returns dict with 'found' (bool) and 'content' (str)
        Example: {'found': True, 'content': 'within 24 hours'}
        """
        if not text:
            return {"found": False, "content": "Missing"}
        
        contact_text = self._extract_contact_text(text)
        if not contact_text:
            return {"found": False, "content": "Missing"}
        
        best_match = None
        best_score = 0
        
        # Try all patterns
        for pattern in self.time_patterns:
            for match in re.finditer(pattern, contact_text, re.MULTILINE | re.IGNORECASE):
                candidate = match.group(1) if match.lastindex else match.group(0)
                candidate = candidate.strip()
                
                # Get context
                start_pos = max(0, match.start() - 100)
                end_pos = min(len(contact_text), match.end() + 100)
                context = contact_text[start_pos:end_pos]
                
                # Validate
                if not self._has_explicit_time(candidate):
                    continue
                
                if self._is_false_positive(candidate, context):
                    continue
                
                # Score the match
                score = 1
                
                # Boost for strong indicators
                if 'response time' in candidate.lower():
                    score += 5
                if 'within' in candidate.lower():
                    score += 3
                if re.search(r'\d+\s*(?:hour|day)', candidate, re.IGNORECASE):
                    score += 2
                if '(' in candidate or 'business' in candidate.lower():
                    score += 1
                if 'no later than' in candidate.lower():
                    score += 2
                if 'weekday' in candidate.lower():
                    score += 1
                if any(word in candidate.lower() for word in ['typically', 'usually', 'generally']):
                    score += 2
                
                # Update best match
                if score > best_score:
                    best_score = score
                    best_match = candidate
        
        # Return best match
        if best_match:
            cleaned = self._clean_response_time(best_match)
            if cleaned and self._has_explicit_time(cleaned):
                return {"found": True, "content": cleaned}
        
        return {"found": False, "content": "Missing"}


def detect_response_time(text: str) -> str:
    """Simple wrapper - returns response time or 'Missing'"""
    detector = ResponseTimeDetector()
    result = detector.detect(text)
    return result.get("content", "Missing")


# Test examples
if __name__ == "__main__":
    test_cases = [
        "Email me anytime. I respond within 24 hours.",
        "Response time: 48 hours (business days)",
        "I'll get back to you within one business day.",
        "You can expect a reply within 24-48 hours.",
        "I typically respond within 24 hours on weekdays.",
        "Responses are usually sent within 48 hours.",
        "You'll receive a reply in 24 hours.",
        "I usually get back to students within a day.",
        "Expect to hear from me within 24 hours.",
        "I'll reply no later than next business day.",
        "Assignments must be submitted within 24 hours.",  # Should filter
        "Canvas support available 24 hours a day.",  # Should filter
        "Please contact me regarding any discrepancies within 7 days after the grade is published.",  # Should filter
        """If you miss a class meeting, email me within 3 days after your absence.""",  # Should filter
    ]
    
    detector = ResponseTimeDetector()
    
    print("\n" + "=" * 80)
    print("RESPONSE TIME DETECTOR - TEST RESULTS")
    print("=" * 80)
    
    for i, text in enumerate(test_cases, 1):
        result = detector.detect(text)
        status = "✓ FOUND" if result['found'] else "✗ NOT FOUND"
        print(f"\n[{i}] {status}")
        print(f"Input:  {text}")
        print(f"Output: {result['content']}")
        print("-" * 80)
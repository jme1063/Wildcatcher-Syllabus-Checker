"""
Assignment Delivery Detector

Finds where students submit assignments in a syllabus.
Examples: Canvas, MyCourses, "Collected in class"

How it works:
1. Searches for platform names (Canvas, MyCourses, etc.)
2. Prefers lines that say "submit" or "upload"
3. Ignores weak phrases like "grades posted on"
4. Scores matches - higher score = more confident
5. Returns best match with confidence percentage

Example:
    Input: "Submit all work via Canvas"
    Output: "Canvas" (confidence: 95%)
"""

import re
from typing import Dict, Any, List, Set


class AssignmentDeliveryDetector:
    """Finds where students submit assignments in syllabi"""
    
    def __init__(self):
        # Platform patterns - checked in order (most specific first)
        # Format: (regex pattern, display name)
        
        self.platform_patterns = [
            # MyCourses variations (check before Canvas)
            (r'(?i)\bunh\s+mycourses\b', 'UNH MyCourses'),
            (r'(?i)\bmycourses\b', 'MyCourses'),
            
            # Canvas with MyCourses
            (r'(?i)\bcanvas\s*\(\s*mycourses\s*\)', 'Canvas (MyCourses)'),
            
            # Plain Canvas
            (r'(?i)\bcanvas\b', 'Canvas'),
            
            # Assignment platforms
            (r'(?i)\bmyopenmath\b', 'MyOpenMath'),
            (r'(?i)\bmastering\s*(?:a\s*&\s*p|anatomy\s*(?:and|&)\s*physiology)', 'Mastering A&P'),
            (r'(?i)\bmasteringphysics\b', 'MasteringPhysics'),
            (r'(?i)\bmastering\s+physics\b', 'MasteringPhysics'),
            
            # Other LMS platforms
            (r'(?i)\bblackboard\b', 'Blackboard'),
            (r'(?i)\bgoogle\s+classroom\b', 'Google Classroom'),
            (r'(?i)\bmoodle\b', 'Moodle'),
            (r'(?i)\bturnitin\b', 'Turnitin'),
            
            # Physical delivery
            (r'(?i)\bwritten\s+assignments?\s+collected\s+in\s+class\b', 'Written assignments collected in class'),
            (r'(?i)\bcollected\s+in\s+class\b', 'Collected in class'),
            (r'(?i)\bin\s*-?\s*person\s+submission\b', 'In-person submission'),
            (r'(?i)\bhanded?\s+in\b', 'Handed in'),
        ]
        
        # Noise phrases to remove
        self.noise_patterns = [
            r'\(embedded\s+in\s+[^)]+\)',
            r'\([^)]*grades?[^)]*\)',
            r'\bembedded\s+in\b',
            r'\bfor\s+grades?\b',
        ]
        
        # Section headers (strong signals)
        self.section_indicators = [
            r'(?i)^\s*assignment\s+(?:delivery|submission|platform)\s*:?',
            r'(?i)^\s*submission\s+(?:method|platform|process)\s*:?',
            r'(?i)^\s*how\s+to\s+submit\s*:?',
            r'(?i)^\s*where\s+to\s+submit\s*:?',
            r'(?i)^\s*(?:course|class)\s+(?:platform|management\s+system)\s*:?',
        ]
        
        # Delivery context (words about submitting)
        self.context_patterns = [
            r'(?i)assignments?\s+(?:are\s+)?(?:submitted|uploaded|turned\s+in|posted|delivered)\s+(?:via|on|to|through|using|in)',
            r'(?i)submit\s+(?:all\s+)?(?:your\s+)?(?:assignments?|work|papers?|homework)\s+(?:via|on|to|through|using|in)',
            r'(?i)(?:upload|post|turn\s+in)\s+(?:your\s+)?(?:assignments?|work|homework)\s+(?:via|on|to|through|in)',
            r'(?i)all\s+(?:assignments?|work|homework)\s+(?:will\s+be\s+)?(?:submitted|posted|uploaded)\s+(?:via|on|to|in)',
            r'(?i)(?:assignments?|homework)\s+(?:should|must)\s+be\s+(?:submitted|uploaded|posted|turned\s+in)\s+(?:via|on|to|in)',
        ]
        
        # Weak signals to ignore (grades, materials)
        self.weak_signal_patterns = [
            r'(?i)\bgrades?\s+(?:are\s+)?(?:posted|available|viewable)\s+(?:on|in)',
            r'(?i)\bcourse\s+materials?\s+(?:are\s+)?(?:on|in|available\s+(?:on|in))',
            r'(?i)\bsyllabus\s+(?:is\s+)?(?:posted\s+)?(?:on|in)',
            r'(?i)\bresources?\s+(?:are\s+)?(?:on|in)',
        ]
    
    def _clean_line_for_extraction(self, line: str) -> str:
        """Remove noise phrases like '(embedded in Canvas)' from line"""
        cleaned = line
        
        for pattern in self.noise_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        return cleaned.strip()
    
    def _extract_platforms_from_text(self, text: str) -> Set[str]:
        """Find all platform names in text (e.g., {'Canvas', 'MyOpenMath'})"""
        platforms = set()
        cleaned = self._clean_line_for_extraction(text)
        
        for pattern, platform_name in self.platform_patterns:
            if re.search(pattern, cleaned):
                platforms.add(platform_name)
        
        return platforms
    
    def _has_section_indicator(self, line: str) -> bool:
        """Check if line is a section header like 'Assignment Submission:'"""
        return any(re.search(p, line) for p in self.section_indicators)
    
    def _has_delivery_context(self, line: str) -> bool:
        """Check if line talks about submitting (e.g., 'Submit work via Canvas')"""
        return any(re.search(p, line) for p in self.context_patterns)
    
    def _is_weak_signal(self, line: str) -> bool:
        """Check if line is about grades/materials, not submission"""
        return any(re.search(p, line) for p in self.weak_signal_patterns)
    
    def detect(self, text: str) -> Dict[str, Any]:
        """
        Find assignment delivery platform in syllabus.
        
        Returns dict with 'found' (bool), 'content' (str), 'confidence' (float)
        Example: {'found': True, 'content': 'Canvas', 'confidence': 95.5}
        """
        if not text or not text.strip():
            return {"found": False, "content": "", "confidence": 0.0}
        
        lines = text.split('\n')
        candidates = []
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            if not line_stripped or len(line_stripped) < 5 or len(line_stripped) > 500:
                continue
            
            if self._is_weak_signal(line_stripped) and not self._has_delivery_context(line_stripped):
                continue
            
            is_section = self._has_section_indicator(line_stripped)
            has_context = self._has_delivery_context(line_stripped)
            platforms = self._extract_platforms_from_text(line_stripped)
            
            if not platforms:
                continue
            
            # Calculate score
            score = 50
            if is_section:
                score += 40
            if has_context:
                score += 35
            
            position_ratio = i / max(len(lines), 1)
            if position_ratio < 0.15:
                score += 25
            elif position_ratio < 0.35:
                score += 18
            elif position_ratio < 0.55:
                score += 10
            elif position_ratio < 0.75:
                score += 5
            
            if len(platforms) > 1:
                score += 12
            
            platform_list = sorted(list(platforms), key=lambda x: x.lower())
            content = '; '.join(platform_list)
            
            candidates.append({
                'content': content,
                'score': score,
                'line': i,
                'has_context': has_context,
                'is_section': is_section,
                'platform_count': len(platforms)
            })
        
        # Select best match
        if candidates:
            best = max(candidates, key=lambda x: (
                x['score'], x['is_section'], x['has_context'], 
                x['platform_count'], -x['line']
            ))
            
            confidence = min(100.0, (best['score'] / 162.0) * 100)
            if confidence < 45:
                confidence = 45
            
            return {'found': True, 'content': best['content'], 'confidence': round(confidence, 2)}
        
        return {'found': False, 'content': '', 'confidence': 0.0}


def detect_assignment_delivery(text: str) -> str:
    """Simple wrapper - returns platform name or empty string"""
    detector = AssignmentDeliveryDetector()
    result = detector.detect(text)
    return result.get('content', '') if result.get('found') else ''


if __name__ == "__main__":
    # Test cases
    test_cases = [
        ("Assignments are submitted via myCourses.", "MyCourses"),
        ("Submit all work through Canvas.", "Canvas"),
        ("MyOpenMath (embedded in Canvas); Written Assignments collected in class", 
         "Canvas; MyOpenMath; Written assignments collected in class"),
        ("Use MasteringPhysics for homework.", "MasteringPhysics"),
        ("Assignments delivered through UNH MyCourses", "UNH MyCourses"),
        ("Upload assignments to Canvas (myCourses)", "Canvas (MyCourses)"),
        ("Grades are posted on Canvas. Submit work via MyCourses and Mastering A&P", 
         "Mastering A&P; MyCourses"),
        ("All assignments submitted via Canvas (MyCourses)", "Canvas (MyCourses)"),
        ("Submit homework on MyCourses; Mastering A&P", "Mastering A&P; MyCourses"),
    ]
    
    detector = AssignmentDeliveryDetector()
    
    print("Testing Assignment Delivery Detector:")
    print("=" * 70)
    
    for text, expected in test_cases:
        result = detector.detect(text)
        found = result.get('content', '')
        confidence = result.get('confidence', 0)
        
        found_norm = {p.strip().lower() for p in found.split(';') if p.strip()}
        expected_norm = {p.strip().lower() for p in expected.split(';') if p.strip()}
        
        match = found_norm == expected_norm
        status = "✓" if match else "✗"
        
        print(f"\n{status} Test case:")
        print(f"  Input: {text}")
        print(f"  Expected: {expected}")
        print(f"  Got: {found} (confidence: {confidence}%)")
        if not match:
            print(f"  Expected set: {expected_norm}")
            print(f"  Got set: {found_norm}")
"""
Authors: Jackie E, Team Alpha fall 2025
Date 12/1/2025
Grading Process Detector
Detects grading processes in syllabi: percentage breakdowns (Exam 1 - 22%),

This detector handles everything that is NOT canonical A..F letter-range mappings, so how a professor might assign points to assignments.

"""

import re
import logging
from typing import Dict, Any

# Detection Configuration Constants
MAX_HEADING_SCAN_LINES = 8
MAX_HEADING_WORDS_CAPS = 12
MAX_HEADING_WORDS_ANCHOR = 15
MAX_HEADING_WORDS_TITLE = 10
MIN_TITLE_CASE_CAPS = 2
MIN_WINDOW_SCORE = 2
MAX_SHORT_LINE_WORDS = 15
MAX_SHORT_LINE_LENGTH = 120
MAX_NEXT_LINE_WORDS = 20
MAX_UPWARD_SCAN = 7
MAX_DOWNWARD_SCAN = 9
MAX_FORWARD_SCAN = 7
PERCENT_CLUSTER_WINDOW = 3


class GradingProcessDetector:
    """Detector for grading processes in syllabi (not canonical A..F letter-range mappings)."""

    def __init__(self):
        self.field_name = 'grading_process'
        self.logger = logging.getLogger('detector.grading_process')

        # Keywords that suggest a grading scale block
        self.percent_pattern = re.compile(r"\d+\s*%")
        self.points_pattern = re.compile(r"\b\d+\s*(points|pts)\b", re.I)
        # Letter-grade block pattern (A:, B:, C:, D:, F: in same area)
        self.letter_block_pattern = re.compile(
            r"A\s*[:\-].{0,80}B\s*[:\-].{0,80}C\s*[:\-].{0,80}D\s*[:\-].{0,80}F\s*[:\-]",
            re.I | re.S,
        )

        # small list of common labels to help anchor sections
        self.anchor_keywords = [
            'grade', 'grading', 'grades', 'grade breakdown', 'grade scale', 'grading scale', 'course grades',
            'how grades are determined', 'final grade', 'grade distribution', 'assignment', 'exam', 'quiz', 'project',
            'total = 100', 'total=100', 'total 100', 'total: 100', 'total - 100'
        ]

        # Pattern to detect grading scale lines (letter grades with ranges)
        # Examples: "A 100 % to 94 %", "A- < 94 % to 90 %", "A: 93 - 100"
        self.grading_scale_pattern = re.compile(
            r'\b[A-F][+-]?\s*[:<\|]?\s*(<\s*)?\d+\s*%?\s*(to|[-–—])\s*\d+\s*%?',
            re.I
        )

    def _is_grading_scale_line(self, line: str) -> bool:
        """Return True if line appears to be a grading scale (letter grades with ranges)."""
        if not line:
            return False
        line_lower = line.lower()

        # Check for grading scale patterns like "A 100% to 94%", "A: 93-100"
        if self.grading_scale_pattern.search(line):
            return True

        # Check for table headers typical of grading scales
        if 'letter' in line_lower and ('range' in line_lower or 'grade' in line_lower):
            return True

        # Check for multiple letter grades in one line (e.g., "A | 100%to94% |")
        letter_grades = re.findall(r'\b[A-F][+-]?\b', line)
        if len(letter_grades) >= 2 and '%' in line:
            return True

        # Check for table-formatted grading scales with pipes
        # Example: "A | 100 % to 94 % |" or "A- | < 94 % to 90 % |"
        if '|' in line and re.search(r'\b[A-F][+-]?\s*\|', line):
            # Has letter grade followed by pipe - likely a grading scale table
            if '%' in line or 'to' in line_lower:
                return True

        # Check for "Grade of" patterns (e.g., "Grade of F", "Grade of B")
        if 'grade of' in line_lower:
            if any(f' {letter} ' in line_lower or f' {letter},' in line_lower or f' {letter}.' in line_lower
                   for letter in ['a', 'b', 'c', 'd', 'f']):
                return True

        return False

    def _is_late_policy_line(self, line: str) -> bool:
        """Return True if line appears to be a late submission policy."""
        if not line:
            return False
        line_lower = line.lower()

        # Check for late submission indicators
        late_indicators = ['days late', 'late submission', 'points subtracted', 'late penalty',
                          'will not be graded', 'late work', 'late assignment', 'late deduction']
        if any(indicator in line_lower for indicator in late_indicators):
            return True

        # Check for late policy table patterns
        # Example: "1 | 15%" or "7 or more | Will not be graded"
        if '|' in line and any(word in line_lower for word in ['late', 'day', 'penalty', 'deduction']):
            return True

        return False

    def _get_heading_before(self, lines, line_index: int, max_scan: int = MAX_HEADING_SCAN_LINES) -> str:
        """Return a nearby short heading above line_index or empty string.

        Scans up to ``max_scan`` non-empty lines looking for short ALL-CAPS
        headings, anchor keywords, or short Title-Case phrases.
        """
        if not lines:
            return ''
        for i in range(line_index - 1, max(-1, line_index - max_scan - 1), -1):
            if i < 0 or i >= len(lines):
                break
            ln = lines[i].strip()
            if not ln:
                continue
            words = ln.split()
            if ln.isupper() and len(words) <= MAX_HEADING_WORDS_CAPS:
                return ln
            low = ln.lower()
            if any(k in low for k in self.anchor_keywords) and len(words) <= MAX_HEADING_WORDS_ANCHOR:
                return ln
            cap_count = sum(1 for w in words if w and w[0].isupper())
            if MIN_TITLE_CASE_CAPS <= cap_count and len(words) <= MAX_HEADING_WORDS_TITLE and '.' not in ln and ',' not in ln:
                return ln
        return ''

    def _is_heading_line(self, s: str) -> bool:
        """Return True if ``s`` looks like a short section heading.

        This is a lightweight heuristic used when extending blocks to
        include nearby headings.
        """
        if not s or not s.strip():
            return False
        s_stripped = s.strip()
        words = [w for w in s_stripped.split() if w]

        # All-caps short headings are strong indicator
        if s_stripped.isupper() and len(words) <= MAX_HEADING_WORDS_CAPS:
            return True

        low = s_stripped.lower()
        # Anchor keywords are useful, but require the line to be reasonably short
        if any(k in low for k in self.anchor_keywords) and len(words) <= MAX_HEADING_WORDS_ANCHOR:
            return True

        # Title-Case heuristic: short lines with multiple capitalized words and no sentence punctuation
        cap_count = sum(1 for w in words if w and w[0].isupper())
        if MIN_TITLE_CASE_CAPS <= cap_count and len(words) <= MAX_HEADING_WORDS_TITLE and '.' not in s_stripped and ',' not in s_stripped:
            return True

        return False

    def detect(self, text: str) -> Dict[str, Any]:
        """Detect grading process and return a result dict with keys:
        - 'found': bool
        - 'content': str

        The detector tries (in order):
        1) explicit letter-grade block (A:, B:, C:, D:, F:),
        2) contiguous percent/points windows, and
        3) local percentage clusters near labels.
        """
        self.logger.info(f"Starting detection for field: {self.field_name}")

        if not text:
            self.logger.info(f"NOT_FOUND: {self.field_name} (empty text)")
            return {'found': False, 'content': ''}

        # Normalize line endings
        lines = [ln.rstrip() for ln in text.split('\n')]
        joined = '\n'.join(lines)

        # DISABLED: Letter-grade block detection (A: ... B: ... C: ... F:)
        # This was detecting grading SCALES (A=90-100%), not grading PROCESS (Homework 30%)
        # The grading scale should be handled by final_grade_scale detector instead

        # 1) Look for contiguous percentage/points lines (window detection)
        windows = []
        current_block = []
        for i, ln in enumerate(lines):
            s = ln.strip()
            if not s:
                # break block
                if current_block:
                    windows.append((i - len(current_block), current_block))
                    current_block = []
                continue

            has_percent = bool(self.percent_pattern.search(s))
            has_points = bool(self.points_pattern.search(s))
            looks_like_item = bool(re.match(r"^[A-Za-z].{0,60}(\d+\s*%|\(\d+%\)|\d+\s*points|\d+\s*pts)", s, re.I))

            # Skip lines that look like grading scale (letter grades with ranges)
            if self._is_grading_scale_line(s):
                # If we have a block, end it here
                if current_block:
                    windows.append((i - len(current_block), current_block))
                    current_block = []
                continue

            # Skip lines that look like late submission policy
            if self._is_late_policy_line(s):
                # If we have a block, end it here
                if current_block:
                    windows.append((i - len(current_block), current_block))
                    current_block = []
                continue

            if has_percent or has_points or looks_like_item:
                current_block.append(s)
            else:
                # if block already has multiple percent lines, we end it
                if current_block:
                    windows.append((i - len(current_block), current_block))
                    current_block = []
        if current_block:
            windows.append((len(lines) - len(current_block), current_block))

        # Choose the best window: one with most percent/points lines
        best = None
        best_score = 0
        for idx, block in windows:
            # FILTER: Skip windows that are predominantly grading scales or late policies
            grading_scale_lines = sum(1 for ln in block if self._is_grading_scale_line(ln))
            late_policy_lines = sum(1 for ln in block if self._is_late_policy_line(ln))
            total_lines = len(block)

            # If more than 50% of lines are grading scale/late policy, skip this window
            if total_lines > 0 and (grading_scale_lines + late_policy_lines) / total_lines > 0.5:
                continue

            score = sum(1 for ln in block if self.percent_pattern.search(ln) or self.points_pattern.search(ln))
            # bonus if there is an anchor keyword near the block
            context = ' '.join(lines[max(0, idx-PERCENT_CLUSTER_WINDOW): min(len(lines), idx+len(block)+PERCENT_CLUSTER_WINDOW)])
            if any(k in context.lower() for k in self.anchor_keywords):
                score += 1
            if score > best_score and score >= MIN_WINDOW_SCORE:
                best_score = score
                best = (idx, block)

        if best:
            start_idx, block = best
            end_idx = start_idx + len(block) - 1

            # Try to extend upwards to include a nearby heading (scan up to MAX_UPWARD_SCAN lines)
            start = start_idx
            for i in range(start_idx - 1, max(-1, start_idx - MAX_UPWARD_SCAN - 1), -1):
                if i < 0:
                    break
                if not lines[i].strip():
                    break
                if self._is_heading_line(lines[i]):
                    start = i
                    # once we include a heading, stop scanning further up
                    break
                # otherwise do not include long paragraph lines as heading

            # Extend down to capture multi-line items (up to MAX_DOWNWARD_SCAN lines), but stop at long sentence paragraphs
            end = end_idx
            for j in range(end_idx + 1, min(len(lines), end_idx + MAX_DOWNWARD_SCAN)):
                if not lines[j].strip():
                    break
                next_line = lines[j].strip()
                # If the line looks like a long sentence (many words and contains a period), stop
                if '.' in next_line and len(next_line.split()) > MAX_NEXT_LINE_WORDS:
                    break
                end = j

            # Prefer to return only the percent/points lines and very short context
            percent_idxs = [i for i in range(start, end + 1) if self.percent_pattern.search(lines[i]) or self.points_pattern.search(lines[i])]
            if percent_idxs:
                selected = []
                for idx in percent_idxs:
                    # include one short preceding line if it looks like a heading/context
                    if idx - 1 >= start and lines[idx-1].strip():
                        prev = lines[idx-1].strip()
                        if len(prev.split()) <= MAX_SHORT_LINE_WORDS and len(prev) <= MAX_SHORT_LINE_LENGTH:
                            selected.append(idx-1)
                    selected.append(idx)
                    # include one short following line if it's short and not a long sentence
                    if idx + 1 <= end and lines[idx+1].strip():
                        next_line = lines[idx+1].strip()
                        if len(next_line.split()) <= MAX_NEXT_LINE_WORDS and not ('.' in next_line and len(next_line.split()) > MAX_NEXT_LINE_WORDS):
                            selected.append(idx+1)
                # dedupe while preserving order
                seen = set()
                final_idxs = []
                for i in selected:
                    if i not in seen:
                        seen.add(i)
                        final_idxs.append(i)

                # If percent lines are separated by short label lines that appear later,
                # scan forward up to a few lines to capture them (e.g., 'Quizzes:' then later 'Quiz1: 40%')
                if final_idxs:
                    start_block = min(final_idxs)
                    end_block = max(final_idxs)
                    for j in range(end_block + 1, min(len(lines), end_block + MAX_FORWARD_SCAN)):
                        if self.percent_pattern.search(lines[j]):
                            # include intervening short lines
                            for k in range(end_block + 1, j + 1):
                                if k not in seen and lines[k].strip():
                                    # only include short label/context lines
                                    if k == j or len(lines[k].split()) <= MAX_SHORT_LINE_WORDS:
                                        seen.add(k)
                                        final_idxs.append(k)
                            end_block = j
                            break

                content_lines = [lines[i].rstrip() for i in final_idxs if lines[i].strip()]
                # prepend heading if found above original block
                heading = self._get_heading_before(lines, start_idx)
                if heading and (not content_lines or not content_lines[0].startswith(heading)):
                    content_lines.insert(0, heading)
                content = '\n'.join(content_lines).strip()
                self.logger.info(f"FOUND: {self.field_name} (percent/points window)")
                return {'found': True, 'content': content}
            else:
                # fallback to returning the short block (should be rare)
                content_lines = [lines[i].rstrip() for i in range(start, end + 1) if lines[i].strip()]
                content = '\n'.join(content_lines).strip()
                self.logger.info(f"FOUND: {self.field_name} (short block fallback)")
                return {'found': True, 'content': content}

        # 3) fallback: look for lines containing a cluster of assignment labels followed shortly by percentages
        # find lines where a percentage exists and gather +/-PERCENT_CLUSTER_WINDOW lines around it
        percent_lines_idx = [i for i, ln in enumerate(lines) if self.percent_pattern.search(ln)]
        for idx in percent_lines_idx:
            # gather a slightly larger window and then try to expand to heading/context
            start = max(0, idx - PERCENT_CLUSTER_WINDOW)
            end = min(len(lines), idx + PERCENT_CLUSTER_WINDOW + 1)
            block_lines = [lines[j] for j in range(start, end) if lines[j].strip()]
            if sum(1 for ln in block_lines if self.percent_pattern.search(ln)) >= MIN_WINDOW_SCORE:
                # expand similarly to the window case
                # find nearest non-empty start before 'start' that looks like a heading
                heading_start = start
                for i in range(start - 1, max(-1, start - MAX_DOWNWARD_SCAN), -1):
                    if i < 0 or not lines[i].strip():
                        break
                    if any(k in lines[i].lower() for k in self.anchor_keywords) or lines[i].strip().isupper():
                        heading_start = i
                        break
                final_start = heading_start
                final_end = min(len(lines) - 1, end + PERCENT_CLUSTER_WINDOW)
                for j in range(end, min(len(lines), end + MAX_DOWNWARD_SCAN)):
                    if not lines[j].strip():
                        break
                    final_end = j
                # prefer to return only percent/points lines near the cluster
                percent_idxs2 = [k for k in range(final_start, final_end + 1) if self.percent_pattern.search(lines[k]) or self.points_pattern.search(lines[k])]
                if percent_idxs2:
                    selected = []
                    for idx in percent_idxs2:
                        if idx - 1 >= final_start and lines[idx-1].strip():
                            prev = lines[idx-1].strip()
                            if len(prev.split()) <= MAX_SHORT_LINE_WORDS and len(prev) <= MAX_SHORT_LINE_LENGTH:
                                selected.append(idx-1)
                        selected.append(idx)
                        if idx + 1 <= final_end and lines[idx+1].strip():
                            next_line = lines[idx+1].strip()
                            if len(next_line.split()) <= MAX_NEXT_LINE_WORDS and not ('.' in next_line and len(next_line.split()) > MAX_NEXT_LINE_WORDS):
                                selected.append(idx+1)
                    seen = set()
                    final_idxs2 = []
                    for i in selected:
                        if i not in seen:
                            seen.add(i)
                            final_idxs2.append(i)

                    # expand forward to include percent lines that appear after short labels
                    if final_idxs2:
                        start_block2 = min(final_idxs2)
                        end_block2 = max(final_idxs2)
                        for j in range(end_block2 + 1, min(len(lines), end_block2 + MAX_FORWARD_SCAN)):
                            if self.percent_pattern.search(lines[j]):
                                for k in range(end_block2 + 1, j + 1):
                                    if k not in seen and lines[k].strip():
                                        if k == j or len(lines[k].split()) <= MAX_SHORT_LINE_WORDS:
                                            seen.add(k)
                                            final_idxs2.append(k)
                                end_block2 = j
                                break

                    content_lines = [lines[k].rstrip() for k in final_idxs2 if lines[k].strip()]
                    heading = self._get_heading_before(lines, final_start)
                    if heading and (not content_lines or not content_lines[0].startswith(heading)):
                        content_lines.insert(0, heading)
                    self.logger.info(f"FOUND: {self.field_name} (percent cluster)")
                    return {'found': True, 'content': '\n'.join(content_lines).strip()}
                content_lines = [lines[k].rstrip() for k in range(final_start, final_end + 1) if lines[k].strip()]
                self.logger.info(f"FOUND: {self.field_name} (cluster fallback)")
                return {'found': True, 'content': '\n'.join(content_lines).strip()}

        self.logger.info(f"NOT_FOUND: {self.field_name}")
        return {'found': False, 'content': ''}


# Backwards compatibility
def detect_grading_process(text: str) -> str:
    d = GradingProcessDetector()
    res = d.detect(text)
    return res.get('content', '') if res.get('found') else ''


if __name__ == '__main__':
    tests = [
        ("Exam 1 - 22%\nExam 2 - 22%\nExam 3 - 22%\nOnline Quizzes - 10%\nExperiments - 20%\nAttendance - 4%\nTotal = 100%", True),
        ("PROJECTS (70%) 70 Points\nProject #1 - 10 points\nProject #2 - 10 points\nQuiz & Mid-Term (20%) 20 Points\nOTHER (10%) 10 Points\nTOTAL 100%", True),
        ("A: Excellent work B: Good work C: Satisfactory D: Needs improvement F: Failing", True),
        ("This syllabus has no grading info", False),
    ]

    d = GradingProcessDetector()
    for text, expect in tests:
        r = d.detect(text)
        print('FOUND' if r['found'] else 'NO_MATCH', '\n', r['content'])
        print('-' * 40)

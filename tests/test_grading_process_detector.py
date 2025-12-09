import unittest
from detectors.grading_process_detection import GradingProcessDetector

class TestGradingProcessDetector(unittest.TestCase):
    def setUp(self):
        self.detector = GradingProcessDetector()

    def test_letter_block_detected(self):
        text = (
            "GRADING:\n"
            "A: 93 - 100\n"
            "A-: 90 - 92\n"
            "B+: 87 - 89\n"
            "B: 83 - 86\n"
            "B-: 80 - 82\n"
            "C+: 77 - 79\n"
            "C: 73 - 76\n"
            "C-: 70 - 72\n"
            "D+: 67 - 69\n"
            "D: 63 - 66\n"
            "D-: 60 - 62\n"
            "F: below 60\n"
        )
        res = self.detector.detect(text)
        self.assertTrue(res['found'])
        self.assertIn('A:', res['content'])
        self.assertIn('F:', res['content'])

    def test_percent_block_detected(self):
        text = (
            "Exam 1 - 22%\n"
            "Exam 2 - 22%\n"
            "Exam 3 - 22%\n"
            "Online Quizzes - 10%\n"
            "Experiments - 20%\n"
            "Attendance - 4%\n"
            "Total = 100%\n"
        )
        res = self.detector.detect(text)
        self.assertTrue(res['found'])
        self.assertIn('Exam 1', res['content'])
        self.assertIn('22%', res['content'])

    def test_inline_percent_detected(self):
        text = "Exams 40%, Homework 30%, Final 30%"
        res = self.detector.detect(text)
        self.assertTrue(res['found'])
        self.assertIn('Exams 40%', res['content'])

    def test_empty_text_returns_not_found(self):
        res = self.detector.detect('')
        self.assertFalse(res['found'])
        self.assertEqual(res['content'], '')

if __name__ == '__main__':
    unittest.main()

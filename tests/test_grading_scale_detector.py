"""
Standalone runner for GradingScaleDetector.

This script is intentionally self-contained so you can run it directly from the repo root
without additional test frameworks. It ensures the repo root is on sys.path so local
imports (e.g., document_processing) work when run as:

  python tests/test_grading_scale_detector.py

Exit codes:
  0 = success (detector ran and printed result)
  1 = import error
  2 = missing PDF
  3 = extraction or detector runtime error
"""

import sys
import traceback
from pathlib import Path

# Make repo root importable when running this file directly
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from document_processing import extract_text_from_pdf
    from detectors.grading_scale_detection import GradingScaleDetector
except Exception as e:
    print("Import error:", e)
    traceback.print_exc()
    sys.exit(1)


def main():
    pdf_path = REPO_ROOT / "ground_truth_syllabus" / "557_syllabus.pdf"
    if not pdf_path.exists():
        print(f"Missing test PDF: {pdf_path}")
        return 2

    try:
        text = extract_text_from_pdf(str(pdf_path)) or ""
    except Exception as e:
        print("Error extracting text from PDF:", e)
        traceback.print_exc()
        return 3

    try:
        detector = GradingScaleDetector()
        result = detector.detect(text)
    except Exception as e:
        print("Error running GradingScaleDetector:", e)
        traceback.print_exc()
        return 3

    # Print a clear CLI-friendly output
    print("\n=== GradingScaleDetector result ===")
    print(result)
    print("===================================\n")
    # Basic validation
    if not isinstance(result, dict) or 'found' not in result or 'content' not in result:
        print("Unexpected detector result shape.")
        return 3

    return 0


if __name__ == '__main__':
    rc = main()
    sys.exit(rc)

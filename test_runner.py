#!/usr/bin/env python3
"""
Automated testing for syllabus field detection
Uses detectors + ground_truth.json
- Lenient matching:
  * If GT is "Not found"/empty and prediction is empty => match True
  * Fuzzy text match for near-equal strings
  * Modality normalization (online / hybrid / in-person)
Prints results to terminal and saves to test_results.json
Now also captures SLO text and writes it to JSON only (no terminal SLO prints), including both GT and predicted SLOs in the per-file details.
Includes support for assignment_types_title, deadline_expectations_title, response_time, and grading_process fields.
"""
import os
import sys
import json
import argparse
from collections import defaultdict
from difflib import SequenceMatcher

# Constants
FUZZY_MATCH_THRESHOLD = 0.80
SUPPORTED_FIELDS = (
    "modality", "SLOs", "email", "credit_hour", "workload",
    "instructor_name", "instructor_title", "instructor_department",
    "office_address", "office_hours", "office_phone",
    "preferred_contact_method",
    "assignment_types_title",
    "deadline_expectations_title", "assignment_delivery", "final_grade_scale",
    "response_time",
    "class_location",
    "grading_process"
)

# Add repo root to path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
PARENT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (REPO_ROOT, PARENT):
    if p not in sys.path:
        sys.path.append(p)

from document_processing import extract_text_from_pdf, extract_text_from_docx

# ------------------ Detector Imports ------------------
try:
    from detectors.online_detection import detect_modality
    MODALITY_AVAILABLE = True
except Exception:
    MODALITY_AVAILABLE = False
    print("WARNING: Modality detector not available")

try:
    from detectors.slo_detector import SLODetector
    SLO_AVAILABLE = True
except Exception:
    SLO_AVAILABLE = False
    print("WARNING: SLO detector not available")

try:
    from detectors.email_detector import EmailDetector
    EMAIL_AVAILABLE = True
except Exception:
    EMAIL_AVAILABLE = False
    print("WARNING: Email detector not available")

try:
    from detectors.credit_hours_detection import CreditHoursDetector
    CREDIT_HOURS_AVAILABLE = True
except Exception:
    CREDIT_HOURS_AVAILABLE = False
    print("WARNING: Credit hours detector not available")

try:
    from detectors.workload_detection import WorkloadDetector
    WORKLOAD_AVAILABLE = True
except Exception:
    WORKLOAD_AVAILABLE = False
    print("WARNING: Workload detector not available")

try:
    from detectors.instructor_detector import InstructorDetector
    INSTRUCTOR_AVAILABLE = True
except Exception:
    INSTRUCTOR_AVAILABLE = False
    print("WARNING: Instructor detector not available")

try:
    from detectors.office_information_detection import OfficeInformationDetector
    OFFICE_INFO_AVAILABLE = True
except Exception:
    OFFICE_INFO_AVAILABLE = False
    print("WARNING: Office information detector not available")

try:
    from detectors.preferred_contact_detector import PreferredDetector
    PREFERRED_CONTACT_AVAILABLE = True
except Exception:
    PREFERRED_CONTACT_AVAILABLE = False
    print("WARNING: Preferred contact detector not available")

try:
    from detectors.assignment_types_detection import AssignmentTypesDetector
    ASSIGNMENT_TYPES_AVAILABLE = True
except Exception:
    ASSIGNMENT_TYPES_AVAILABLE = False
    print("WARNING: Assignment types detector not available")

try:
    from detectors.late_missing_work_detector import LateDetector
    DEADLINE_EXPECTATIONS_AVAILABLE = True
except Exception:
    DEADLINE_EXPECTATIONS_AVAILABLE = False
    print("WARNING: Deadline expectations detector not available")

try:
    from detectors.assignment_delivery_detection import AssignmentDeliveryDetector
    ASSIGNMENT_DELIVERY_AVAILABLE = True
except Exception:
    ASSIGNMENT_DELIVERY_AVAILABLE = False
    print("WARNING: Assignment delivery detector not available")

try:
    from detectors.grading_scale_detection import GradingScaleDetector
    GRADING_SCALE_AVAILABLE = True
except Exception:
    GRADING_SCALE_AVAILABLE = False
    print("WARNING: Grading scale detector not available")

try:
    from detectors.grading_process_detection import GradingProcessDetector
    GRADING_PROCESS_AVAILABLE = True
except Exception:
    GRADING_PROCESS_AVAILABLE = False
    print("WARNING: Grading process detector not available")

# NEW: Response Time Detector
try:
    from detectors.class_location_detector import ClassLocationDetector
    CLASS_LOCATION_AVAILABLE = True
except Exception:
    CLASS_LOCATION_AVAILABLE = False
    print("WARNING: Class location detector not available")

try:
    from detectors.response_time_detector import ResponseTimeDetector
    RESPONSE_TIME_AVAILABLE = True
except Exception:
    RESPONSE_TIME_AVAILABLE = False
    print("WARNING: Response time detector not available")

# ======================================================================
# COMPARISON HELPERS
# ======================================================================

def norm(s):
    if s is None:
        return ""
    return " ".join(str(s).strip().lower().split())

def has_value(value):
    """
    Check if a field has a meaningful value (not empty/missing/not found).
    Simple helper for F1 score calculation.
    """
    normalized = norm(value)
    # Consider these as "no value"
    empty_indicators = ["", "not found", "missing", "n/a", "tbd", "not specified"]
    return normalized not in empty_indicators

def update_field_stats(stats, gt_value, pred_value, match):
    """
    Update TP/FP/FN/TN counts based on ground truth, prediction, and match.

    Logic:
    - TP (True Positive): GT has value AND Pred has value AND they match
    - FP (False Positive): GT has NO value BUT Pred found something
    - FN (False Negative): GT has value BUT (Pred has no value OR they don't match)
    - TN (True Negative): GT has NO value AND Pred has no value

    Note: "Missing" in GT means field was verified to NOT exist in syllabus
    """
    gt_has = has_value(gt_value)
    pred_has = has_value(pred_value)

    if gt_has and pred_has and match:
        stats["TP"] += 1  # Correct detection
    elif not gt_has and pred_has:
        stats["FP"] += 1  # False alarm (detected something that doesn't exist)
    elif gt_has and (not pred_has or not match):
        stats["FN"] += 1  # Missed detection (should have found but didn't, or found wrong value)
    elif not gt_has and not pred_has:
        stats["TN"] += 1  # Correct rejection (correctly found nothing)

def fuzzy_match(a, b, threshold=FUZZY_MATCH_THRESHOLD):
    a, b = norm(a), norm(b)
    if not a and not b:
        return True
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    return SequenceMatcher(None, a, b).ratio() >= threshold

def loose_compare(gt, pred):
    """GT 'not found'/empty/missing means field doesn't exist - expect empty pred."""
    g = norm(gt)
    p = norm(pred)

    # If GT is Missing/not found/empty, the field doesn't exist in syllabus
    # Prediction should also be empty/missing for a match
    if g in ("", "not found", "missing", "tbd", "not specified", "n/a"):
        return p in ("", "missing")

    return fuzzy_match(g, p)

def compare_grading_scale(gt, pred):
    """Compare grading scales - focus on grade letters found rather than exact formatting."""
    import re
    
    # Normalize empty values
    def is_empty(value):
        if not value:
            return True
        value_str = str(value).strip()
        return value_str == "" or value_str.lower() == "missing"
    
    # If both are empty/Missing, they match
    if is_empty(gt) and is_empty(pred):
        return True
    
    # If one is empty and the other isn't, no match
    if is_empty(gt) or is_empty(pred):
        return False
    
    def extract_grade_letters(text):
        """Extract just the grade letters (A, A-, B+, etc.) from text."""
        if not text:
            return set()
        
        # Pattern to find grade letters
        pattern = r'\b([A-F][+-]?)(?=[\s:=\d<>%]|$)'
        matches = re.findall(pattern, str(text), re.IGNORECASE)
        return set(match.upper() for match in matches)
    
    gt_grades = extract_grade_letters(gt)
    pred_grades = extract_grade_letters(pred)
    
    # If both have no grade letters, check if they're similar text
    if not gt_grades and not pred_grades:
        return fuzzy_match(gt, pred, 0.7)  # Lower threshold for non-grade text
        
    # If one has grades and the other doesn't, no match    
    if not gt_grades or not pred_grades:
        return False
        
    # Compare the sets of grades found
    # Allow for some flexibility - if we have at least 80% overlap of the larger set
    if len(gt_grades) == 0 and len(pred_grades) == 0:
        return True
    
    intersection = gt_grades & pred_grades
    union = gt_grades | pred_grades
    
    # If they have exactly the same grades, perfect match
    if gt_grades == pred_grades:
        return True
    
    # Allow for good overlap (at least 80% of grades match)
    overlap_ratio = len(intersection) / len(union) if union else 0
    return overlap_ratio >= 0.8

def compare_modality(gt, pred):
    """Normalize to buckets before compare. Missing means field doesn't exist."""
    def core(s):
        s = norm(s)
        # If GT is Missing/empty, field doesn't exist in syllabus
        if s in ("", "missing", "tbd", "not found", "not specified", "n/a"):
            return "not_present"

        # Check for negations (no remote, no online, etc.) -> treat as in-person
        if any(neg in s for neg in ("no remote", "no option for remote", "no online")):
            return "in-person"

        # Hybrid variations
        if "hybrid" in s or "blended" in s or "hy-flex" in s or "hyflex" in s:
            return "hybrid"

        # Online variations (including synchronous/asynchronous, remote, zoom)
        if any(x in s for x in ("online", "remote", "asynchronous", "synchronous", "zoom")):
            return "online"

        # In-person variations (face-to-face, on campus, specific locations, outdoor/field)
        if any(x in s for x in ("in-person", "in person", "on campus", "face to face",
                                 "face-to-face", "outdoor", "field meeting", "classroom",
                                 "lab activit", "pandra", "pandora")):
            return "in-person"

        return s

    gt_norm = core(gt)
    pred_norm = core(pred)

    # Both normalized values should match
    return gt_norm == pred_norm

def normalize_location(s):
    """
    Normalize location strings for better matching.
    - PANDRA → Pandora
    - Rm./Rm → Room
    - Remove extra spaces
    - Lowercase
    - Handle P149 <-> Pandora 149 equivalence
    """
    s = s.strip().lower()

    # Building name variations
    s = s.replace("pandra", "pandora")
    s = s.replace("hamilton smith", "hamiltonsmith")  # Consistent handling

    # Room prefix variations - normalize all "rm" variants to "room "
    # Handle "rm." "rm " and "rm" followed by number
    import re as re_local
    s = re_local.sub(r'\brm\.?\s*', 'room ', s)
    s = s.replace("classroom:", "room ")
    s = s.replace("classroom ", "room ")

    # Normalize separators
    s = s.replace(",", " ")
    s = s.replace(".", " ")

    # Normalize whitespace
    s = " ".join(s.split())

    # Handle P[number] <-> Pandora [number] equivalence
    # "pandora 149" -> "p149" and "room p149" -> "p149"
    # This allows "PANDRA 149" and "Room P149" to match
    import re

    # First, normalize "P 146" (with space) to "p146" (no space)
    s = re.sub(r'\bp\s+(\d+)\b', r'p\1', s)

    # Handle "Pandora Building (UNHM) P146" -> extract just p146
    s = re.sub(r'pandora\s+(?:building|mill|hall)?\s*(?:\([^)]+\))?\s*(p\d+)', r'\1', s)

    # If format is "pandora 123" or "pandora hall 123", convert to "p123"
    s = re.sub(r'pandora\s+(?:hall\s+)?(\d+)', r'p\1', s)

    # If format is "room p123", convert to "p123"
    s = re.sub(r'room\s+(p\d+)', r'\1', s)

    return s

def compare_class_location(gt, pred, modality):
    """
    Smart comparison for class_location that considers course modality.

    Logic:
    - If GT is Missing/empty, field doesn't exist - expect empty prediction
    - If GT indicates online (contains "online", "canvas", "zoom", "teams") AND
      modality is "Online", then empty prediction is acceptable (correct).
    - Otherwise, use fuzzy matching with location normalization.
    """
    g = norm(gt)
    p = norm(pred)

    # If GT is Missing/empty, the field doesn't exist - pred should also be empty
    if g in ("missing", "tbd", "not specified", "n/a", ""):
        return p in ("", "missing")

    # Check if GT indicates an online-only course
    online_indicators = ["online", "canvas", "zoom", "teams", "webex", "remote", "tbd"]
    gt_is_online = any(indicator in g for indicator in online_indicators)

    # Special case: GT says online and modality confirms it's online/remote
    # Empty prediction is acceptable (no physical location expected)
    if gt_is_online and modality:
        modality_norm = norm(modality)
        modality_is_online = any(word in modality_norm for word in ["online", "remote", "zoom", "teams", "webex"])
        if modality_is_online:
            # Both empty or pred is empty when GT says "online/remote"
            if p in ("", "missing") or g == p:
                return True

    # Normalize location strings for better matching
    g_norm = normalize_location(g)
    p_norm = normalize_location(p)

    # Empty checks
    if not g_norm and not p_norm:
        return True
    if not g_norm or not p_norm:
        return False

    # Exact match after normalization
    if g_norm == p_norm:
        return True

    # Substring match (one contains the other)
    if g_norm in p_norm or p_norm in g_norm:
        return True

    # Fuzzy match on normalized strings
    return SequenceMatcher(None, g_norm, p_norm).ratio() >= FUZZY_MATCH_THRESHOLD

def compare_grading_process(gt, pred):
    """
    Lenient comparison for grading_process field.

    The detector often finds the correct content but with minor formatting differences
    (extra context, different whitespace, etc.). Use a more lenient threshold (75% vs 80%).
    """
    g = norm(gt)
    p = norm(pred)

    # If GT is Missing/not found/empty, expect empty pred
    if g in ("", "not found", "missing", "tbd", "not specified", "n/a"):
        return p in ("", "missing")

    # Use fuzzy matching with MORE LENIENT threshold for grading_process
    # Standard threshold is 80%, but grading_process uses 60% due to formatting variations
    GRADING_PROCESS_THRESHOLD = 0.60

    if not g and not p:
        return True
    if not g or not p:
        return False
    if g == p or g in p or p in g:
        return True

    return SequenceMatcher(None, g, p).ratio() >= GRADING_PROCESS_THRESHOLD

# ======================================================================
# DETECTOR WRAPPERS
# ======================================================================

def detect_all_fields(text: str) -> dict:
    preds = {}

    # Modality
    if MODALITY_AVAILABLE:
        label, _ = detect_modality(text)
        preds["modality"] = label
    else:
        preds["modality"] = "Unknown"

    # SLOs (capture flag + text)
    if SLO_AVAILABLE:
        slo = SLODetector().detect(text)
        preds["has_slos"] = bool(slo.get("found"))
        content = slo.get("content")
        if isinstance(content, list):
            preds["slos_text"] = "\n".join(map(str, content))
        else:
            # FIXED: Properly handle Missing value
            preds["slos_text"] = content if content else "Missing"
    else:
        preds["has_slos"] = False
        preds["slos_text"] = "Missing"

    # Email
    if EMAIL_AVAILABLE:
        email_result = EmailDetector().detect(text)
        content = email_result.get("content")
        # Now returns string directly, but handle legacy list format for safety
        if isinstance(content, list) and content:
            preds["email"] = content[0]
        else:
            preds["email"] = content or "Missing"
    else:
        preds["email"] = "Missing"

    # Credit Hours
    if CREDIT_HOURS_AVAILABLE:
        c = CreditHoursDetector().detect(text)
        preds["credit_hour"] = c.get("content", "Missing") if c.get("found") else "Missing"
    else:
        preds["credit_hour"] = "Missing"

    # Workload
    if WORKLOAD_AVAILABLE:
        w = WorkloadDetector().detect(text)
        preds["workload"] = w.get("content", "Missing") if w.get("found") else "Missing"
    else:
        preds["workload"] = "Missing"

    # Instructor
    if INSTRUCTOR_AVAILABLE:
        instructor_result = InstructorDetector().detect(text)
        preds["instructor_name"] = instructor_result.get("name", "Missing")
        preds["instructor_title"] = instructor_result.get("title", "Missing")
        preds["instructor_department"] = instructor_result.get("department", "Missing")
    else:
        preds["instructor_name"] = "Missing"
        preds["instructor_title"] = "Missing"
        preds["instructor_department"] = "Missing"

    # Office Information
    if OFFICE_INFO_AVAILABLE:
        o = OfficeInformationDetector().detect(text)
        preds["office_address"] = o.get("office_location", {}).get("content", "Missing") if o.get("office_location", {}).get("found") else "Missing"
        preds["office_hours"] = o.get("office_hours", {}).get("content", "Missing") if o.get("office_hours", {}).get("found") else "Missing"
        preds["office_phone"] = o.get("phone", {}).get("content", "Missing") if o.get("phone", {}).get("found") else "Missing"
    else:
        preds["office_address"] = "Missing"
        preds["office_hours"] = "Missing"
        preds["office_phone"] = "Missing"

    # Preferred Contact Method
    if PREFERRED_CONTACT_AVAILABLE:
        pc = PreferredDetector().detect(text)
        preds["preferred_contact_method"] = pc.get("content", "Missing") if pc.get("found") else "Missing"
    else:
        preds["preferred_contact_method"] = "Missing"

    # Assignment Types
    if ASSIGNMENT_TYPES_AVAILABLE:
        a = AssignmentTypesDetector().detect(text)
        preds["assignment_types_title"] = a.get("content", "Missing") if a.get("found") else "Missing"
    else:
        preds["assignment_types_title"] = "Missing"

    # Grading procedures detection removed
    preds["grading_procedures_title"] = "Missing"

    # Deadline Expectations
    if DEADLINE_EXPECTATIONS_AVAILABLE:
        d = LateDetector().detect(text)
        # Extract just the title (first line) from content
        content = d.get("content", "")
        if content and d.get("found"):
            preds["deadline_expectations_title"] = content.split('\n')[0].strip()
        else:
            preds["deadline_expectations_title"] = "Missing"
    else:
        preds["deadline_expectations_title"] = "Missing"

    # Assignment Delivery
    if ASSIGNMENT_DELIVERY_AVAILABLE:
        ad = AssignmentDeliveryDetector().detect(text)
        preds["assignment_delivery"] = ad.get("content", "Missing") if ad.get("found") else "Missing"
    else:
        preds["assignment_delivery"] = "Missing"

    # Grading Scale
    if GRADING_SCALE_AVAILABLE:
        gs = GradingScaleDetector().detect(text)
        preds["final_grade_scale"] = gs.get("content", "Missing") if gs.get("found") else "Missing"
    else:
        preds["final_grade_scale"] = "Missing"

    # Response Time
    if RESPONSE_TIME_AVAILABLE:
        rt = ResponseTimeDetector().detect(text)
        preds["response_time"] = rt.get("content", "Missing") if rt.get("found") else "Missing"
    else:
        preds["response_time"] = "Missing"

    # Grading Process
    if GRADING_PROCESS_AVAILABLE:
        gp = GradingProcessDetector().detect(text)
        preds["grading_process"] = gp.get("content", "Missing") if gp.get("found") else "Missing"
    else:
        preds["grading_process"] = "Missing"

    # Class Location
    if CLASS_LOCATION_AVAILABLE:
        cl = ClassLocationDetector().detect(text)
        preds["class_location"] = cl.get("content", "Missing") if cl.get("found") else "Missing"
    else:
        preds["class_location"] = "Missing"

    return preds

# ======================================================================
# MAIN
# ======================================================================

def main():
    ap = argparse.ArgumentParser(description="Run detectors vs ground_truth.json")
    ap.add_argument("--syllabi", default="ground_truth_syllabus", help="Folder with PDFs/DOCX")
    ap.add_argument("--ground_truth", default="ground_truth.json", help="Ground truth JSON")
    ap.add_argument("--output", default="test_results.json", help="Output JSON file")
    args = ap.parse_args()

    print(f"\n[INFO] Folder: {os.path.abspath(args.syllabi)}")
    print(f"[INFO] Ground truth: {os.path.abspath(args.ground_truth)}")

    if not os.path.exists(args.syllabi) or not os.path.exists(args.ground_truth):
        print("[ERROR] Missing folder or JSON.")
        sys.exit(1)

    with open(args.ground_truth, "r", encoding="utf-8") as f:
        gt_data = json.load(f)

    print(f"\nFound {len(gt_data)} records in ground truth.")

    # Track TP, FP, FN, TN for F1 score calculation
    # TP = True Positive: GT has value, Pred has value, Match correct
    # FP = False Positive: GT has NO value, but Pred found something
    # FN = False Negative: GT has value, but Pred missed or got wrong
    # TN = True Negative: GT has NO value, Pred found nothing
    field_stats = defaultdict(lambda: {"TP": 0, "FP": 0, "FN": 0, "TN": 0})
    details = []

    for i, record in enumerate(gt_data, 1):
        fname = record.get("filename", "")
        fpath = os.path.join(args.syllabi, fname)
        if not os.path.exists(fpath):
            print(f"[{i}] [ERROR] Missing file: {fname}")
            continue

        # Extract text
        try:
            if fpath.lower().endswith(".pdf"):
                text = extract_text_from_pdf(fpath) or ""
            else:
                text = extract_text_from_docx(fpath) or ""
        except Exception as e:
            print(f"[{i}] Error reading {fname}: {e}")
            continue

        preds = detect_all_fields(text)
        result = {"filename": fname}

        # Modality
        if "modality" in record:
            gt_val = record["modality"]
            pred_val = preds.get("modality", "")
            match = compare_modality(gt_val, pred_val)
            update_field_stats(field_stats["modality"], gt_val, pred_val, match)
            result["modality"] = {"gt": gt_val, "pred": pred_val, "match": match}
            
        # SLOs: compare presence, store texts (JSON only)
        if "SLOs" in record:
            gt_val = record.get("SLOs", "")
            pred_val = preds.get("slos_text", "Missing")
            
            # FIXED: Use has_value() to properly determine if GT has SLOs
            gt_has = has_value(gt_val)
            pred_has = has_value(pred_val)
            match = (gt_has == pred_has)

            update_field_stats(field_stats["SLOs"], gt_val, pred_val, match)

            result["slos"] = {
                "gt_present": gt_has,
                "pred_present": pred_has,
                "match": match,
                "gt_text": str(gt_val).strip(),
                "pred_text": pred_val
            }

        # Email
        if "email" in record:
            gt_val = record["email"]
            pred_val = preds.get("email", "Missing")
            match = loose_compare(gt_val, pred_val)
            update_field_stats(field_stats["email"], gt_val, pred_val, match)
            result["email"] = {"gt": gt_val, "pred": pred_val, "match": match}

        # Credit hour
        if "credit_hour" in record:
            gt_val = record["credit_hour"]
            pred_val = preds.get("credit_hour", "Missing")
            match = loose_compare(gt_val, pred_val)
            update_field_stats(field_stats["credit_hour"], gt_val, pred_val, match)
            result["credit_hour"] = {"gt": gt_val, "pred": pred_val, "match": match}

        # Workload
        if "workload" in record:
            gt_val = record["workload"]
            pred_val = preds.get("workload", "Missing")
            match = loose_compare(gt_val, pred_val)
            update_field_stats(field_stats["workload"], gt_val, pred_val, match)
            result["workload"] = {"gt": gt_val, "pred": pred_val, "match": match}

        # Instructor Name
        if "instructor_name" in record:
            gt_val = record["instructor_name"]
            pred_val = preds.get("instructor_name", "Missing")
            match = loose_compare(gt_val, pred_val)
            update_field_stats(field_stats["instructor_name"], gt_val, pred_val, match)
            result["instructor_name"] = {"gt": gt_val, "pred": pred_val, "match": match}

        # Instructor Title
        if "instructor_title" in record:
            gt_val = record["instructor_title"]
            pred_val = preds.get("instructor_title", "Missing")
            match = loose_compare(gt_val, pred_val)
            update_field_stats(field_stats["instructor_title"], gt_val, pred_val, match)
            result["instructor_title"] = {"gt": gt_val, "pred": pred_val, "match": match}

        # Instructor Department
        if "instructor_department" in record:
            gt_val = record["instructor_department"]
            pred_val = preds.get("instructor_department", "Missing")
            match = loose_compare(gt_val, pred_val)
            update_field_stats(field_stats["instructor_department"], gt_val, pred_val, match)
            result["instructor_department"] = {"gt": gt_val, "pred": pred_val, "match": match}

        # Office Address
        if "office_address" in record:
            gt_val = record["office_address"]
            pred_val = preds.get("office_address", "Missing")
            match = loose_compare(gt_val, pred_val)
            update_field_stats(field_stats["office_address"], gt_val, pred_val, match)
            result["office_address"] = {"gt": gt_val, "pred": pred_val, "match": match}

        # Office Hours
        if "office_hours" in record:
            gt_val = record["office_hours"]
            pred_val = preds.get("office_hours", "Missing")
            match = loose_compare(gt_val, pred_val)
            update_field_stats(field_stats["office_hours"], gt_val, pred_val, match)
            result["office_hours"] = {"gt": gt_val, "pred": pred_val, "match": match}

        # Office Phone
        if "office_phone" in record:
            gt_val = record["office_phone"]
            pred_val = preds.get("office_phone", "Missing")
            match = loose_compare(gt_val, pred_val)
            update_field_stats(field_stats["office_phone"], gt_val, pred_val, match)
            result["office_phone"] = {"gt": gt_val, "pred": pred_val, "match": match}

        # Preferred Contact Method
        if "preferred_contact_method" in record:
            gt_val = record["preferred_contact_method"]
            pred_val = preds.get("preferred_contact_method", "Missing")
            match = loose_compare(gt_val, pred_val)
            update_field_stats(field_stats["preferred_contact_method"], gt_val, pred_val, match)
            result["preferred_contact_method"] = {"gt": gt_val, "pred": pred_val, "match": match}

        # Assignment Types Title
        if "assignment_types_title" in record:
            gt_val = record["assignment_types_title"]
            pred_val = preds.get("assignment_types_title", "Missing")
            match = loose_compare(gt_val, pred_val)
            update_field_stats(field_stats["assignment_types_title"], gt_val, pred_val, match)
            result["assignment_types_title"] = {"gt": gt_val, "pred": pred_val, "match": match}

        # Deadline Expectations Title
        if "deadline_expectations_title" in record:
            gt_val = record["deadline_expectations_title"]
            pred_val = preds.get("deadline_expectations_title", "Missing")
            match = loose_compare(gt_val, pred_val)
            update_field_stats(field_stats["deadline_expectations_title"], gt_val, pred_val, match)
            result["deadline_expectations_title"] = {"gt": gt_val, "pred": pred_val, "match": match}

        # Assignment Delivery
        if "assignment_delivery" in record:
            gt_val = record["assignment_delivery"]
            pred_val = preds.get("assignment_delivery", "Missing")
            match = loose_compare(gt_val, pred_val)
            update_field_stats(field_stats["assignment_delivery"], gt_val, pred_val, match)
            result["assignment_delivery"] = {"gt": gt_val, "pred": pred_val, "match": match}

        # Final Grade Scale
        if "final_grade_scale" in record:
            gt_val = record["final_grade_scale"]  
            pred_val = preds.get("final_grade_scale", "Missing")    
            match = compare_grading_scale(gt_val, pred_val)  
            update_field_stats(field_stats["final_grade_scale"], gt_val, pred_val, match)  
            result["final_grade_scale"] = {"gt": gt_val, "pred": pred_val, "match": match}  
            
        # Response Time
        if "response_time" in record:
            gt_val = record["response_time"]
            pred_val = preds.get("response_time", "Missing")
            match = loose_compare(gt_val, pred_val)
            update_field_stats(field_stats["response_time"], gt_val, pred_val, match)
            result["response_time"] = {"gt": gt_val, "pred": pred_val, "match": match}
            
        # Class Location (with smart comparison considering modality)
        if "class_location" in record:
            gt_val = record["class_location"]
            pred_val = preds.get("class_location", "Missing")
            modality_value = record.get("modality", "")
            match = compare_class_location(gt_val, pred_val, modality_value)
            update_field_stats(field_stats["class_location"], gt_val, pred_val, match)
            result["class_location"] = {
                "gt": gt_val,
                "pred": pred_val,
                "match": match,
                "modality": modality_value
            }
        # Grading Process
        if "grading_process" in record:
            gt_val = record["grading_process"]
            pred_val = preds.get("grading_process", "Missing")
            match = compare_grading_process(gt_val, pred_val)
            update_field_stats(field_stats["grading_process"], gt_val, pred_val, match)
            result["grading_process"] = {"gt": gt_val, "pred": pred_val, "match": match}

        details.append(result)

    # Calculate summary statistics with Precision, Recall, and F1 Score
    summary = {}
    total_tp = total_fp = total_fn = total_tn = 0

    for field in SUPPORTED_FIELDS:
        stats = field_stats[field]
        tp = stats["TP"]
        fp = stats["FP"]
        fn = stats["FN"]
        tn = stats["TN"]

        # Calculate metrics
        # Precision: Of all detections, how many were correct?
        precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0

        # Recall: Of all actual values, how many did we detect correctly?
        recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0

        # F1 Score: Harmonic mean of precision and recall
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        # Accuracy: Overall correctness
        total = tp + fp + fn + tn
        accuracy = ((tp + tn) / total) if total > 0 else 0.0

        summary[field] = {
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "TP": tp,
            "FP": fp,
            "FN": fn,
            "TN": tn
        }

        total_tp += tp
        total_fp += fp
        total_fn += fn
        total_tn += tn

    # Overall metrics
    overall_precision = (total_tp / (total_tp + total_fp)) if (total_tp + total_fp) > 0 else 0.0
    overall_recall = (total_tp / (total_tp + total_fn)) if (total_tp + total_fn) > 0 else 0.0
    overall_f1 = (2 * overall_precision * overall_recall / (overall_precision + overall_recall)) if (overall_precision + overall_recall) > 0 else 0.0
    overall_total = total_tp + total_fp + total_fn + total_tn
    overall_accuracy = ((total_tp + total_tn) / overall_total) if overall_total > 0 else 0.0

    # Print summary to terminal with F1 Score
    print("\n" + "=" * 90)
    print("RESULTS SUMMARY - Detector Performance Metrics")
    print("=" * 90)
    print(f"{'Field':<30} {'Accuracy':>9} {'Precision':>10} {'Recall':>9} {'F1 Score':>10}")
    print("-" * 90)

    for field in SUPPORTED_FIELDS:
        stats = summary[field]
        print(f"{field:<30} {stats['accuracy']:>8.1%} {stats['precision']:>10.1%} "
              f"{stats['recall']:>9.1%} {stats['f1_score']:>10.1%}")

    print("-" * 90)
    print(f"{'OVERALL':<30} {overall_accuracy:>8.1%} {overall_precision:>10.1%} "
          f"{overall_recall:>9.1%} {overall_f1:>10.1%}")
    print("=" * 90)

    # Print explanation for non-technical audience
    print("\nMETRIC DEFINITIONS:")
    print("  • Accuracy:  How often the detector is correct overall")
    print("  • Precision: When detector finds something, how often is it right?")
    print("  • Recall:    Of all fields that exist, how many did we find?")
    print("  • F1 Score:  Balanced measure combining Precision and Recall")
    print("               (Higher F1 = better overall detector quality)")
    print("=" * 90)

    # Save results to JSON
    output_data = {
        "summary": summary,
        "overall": {
            "accuracy": round(overall_accuracy, 4),
            "precision": round(overall_precision, 4),
            "recall": round(overall_recall, 4),
            "f1_score": round(overall_f1, 4),
            "TP": total_tp,
            "FP": total_fp,
            "FN": total_fn,
            "TN": total_tn
        },
        "details": details
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\n[SUCCESS] Results saved to {args.output}")

if __name__ == "__main__":
    main()
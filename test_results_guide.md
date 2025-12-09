# Test Results Guide

## How to Read the Detector Performance Metrics

This guide explains what the four metrics mean and how to use them to improve detectors.

---

## The Four Metrics Explained

### 1. **Accuracy** - Overall Correctness
**Question:** How often is the detector correct (either finding the right thing OR correctly finding nothing)?

**Examples:**
- **workload detector: 88.3%** → Out of 120 syllabi tested, got it right 106 times (GOOD)
- **final_grade_scale detector: 25.0%** → Out of 120 syllabi, only got 30 right (BAD)

**Why it matters:** Shows overall performance, but doesn't tell you HOW the detector is failing.

---

### 2. **Precision** - Trust What You Find
**Question:** When the detector says "I found something," how often is it actually correct?

**Formula:** `Correct Detections / All Detections`

**Examples:**

**Example 1: class_location detector (100% precision)**
- Detector found locations in 105 syllabi
- ALL 105 were correct locations! (0 false alarms)
- **Meaning:** When this detector finds a location, you can trust it 100%

**Example 2: email detector (28.2% precision)**
- Detector found emails in 110 syllabi
- Only 31 were actually correct emails
- 79 were FALSE ALARMS (found text that wasn't really an email)
- **Meaning:** When this detector says "found email," it's wrong 72% of the time!

**Real false alarm examples from test results:**
- File: `COMP_405 - Capuz_Fall - Fall 2022.docx`
  - Ground truth: (no instructor email listed in this syllabus)
  - Detector found: `carlo.capuz@unh.edu` (FALSE - probably from a footer or contact section)

- File: `Archived CPRM 850 syllabus (2025 Term 5).pdf`
  - Ground truth: `randall.magiera@unh.edu` (instructor email)
  - Detector found: `sas.office@unh.edu` (WRONG - picked up support office email instead!)

**What low precision means:** Too many false alarms - detector is finding things that don't exist, or finding the wrong emails (like support office emails instead of instructor emails).

---

### 3. **Recall** - Find Everything That Exists
**Question:** Of all the fields that actually exist, how many did we detect?

**Formula:** `Correct Detections / All Things That Should Be Found`

**Real examples from our project:**

**Example 1: SLO detector (100% recall)**
- Ground truth shows 17 syllabi have SLOs
- Detector found ALL 17 of them! (missed 0)
- **Meaning:** Never misses an SLO when it exists

**Example 2: office_address detector (41.7% recall)**
- Ground truth shows 48 syllabi have office addresses
- Detector only found 20 of them
- MISSED 28 office addresses that actually existed
- **Meaning:** Detector is too conservative - it misses more than half!

**Real missed detection examples from test results:**
- File: `2025-summer-comp690-comp891-jin.pdf`
  - Ground truth: `Rm 139, Pandora Mill building` (full office location)
  - Detector found: `Room 139` (PARTIAL - missing building name, counted as mismatch)

- File: `Beverly Hodsdon - CA520 Special Topics.pdf`
  - Ground truth: `Pandora Room 443` (office location exists)
  - Detector found: (nothing) (COMPLETELY MISSED)

**What low recall means:** Detector is missing things that exist - too picky, not handling different formats, or not looking in the right places.

---

### 4. **F1 Score** - Balanced Quality
**Question:** What's the overall quality when balancing precision and recall?

**Formula:** `2 × (Precision × Recall) / (Precision + Recall)`

**Real examples from our project:**

**Example 1: office_phone detector (86.3% F1) - EXCELLENT**
- Precision: 93.2% (rarely wrong when it finds a phone number)
- Recall: 80.4% (finds most phone numbers)
- Both metrics are strong → High F1 score
- **Meaning:** This detector works well overall

**Example 2: instructor_department detector (32.6% F1) - POOR**
- Precision: 20.8% (80% of detections are wrong!)
- Recall: 75.0% (finds most departments, but with many errors)
- High recall can't make up for terrible precision → Low F1 score
- **Meaning:** Detector needs complete redesign

**Why F1 matters:** Shows balanced quality. A detector with 100% recall but 10% precision is useless (too many false alarms). F1 penalizes this.

---

## Reading the Results Table

```
Field                           Accuracy  Precision    Recall   F1 Score
------------------------------------------------------------------------------------------
email                             30.8%      28.2%     88.6%      42.8%
```

### What this tells you:

| Metric | Value | What It Means |
|--------|-------|---------------|
| **Accuracy: 30.8%** | Low | Out of 120 syllabi, only correct on 37 |
| **Precision: 28.2%** | Very Low | 79 out of 110 detected emails were FALSE (72% false alarm rate!) |
| **Recall: 88.6%** | High | Found 31 out of 35 real emails (missed only 4) |
| **F1: 42.8%** | Low | Poor overall quality due to massive false alarm problem |

**Diagnosis:** Email detector finds almost all real emails (good recall) but also detects 79 fake emails (terrible precision).

**Real-world examples of what went wrong:**
- Detected `sas.office@unh.edu` (support office email) instead of instructor email
- Found emails in syllabi where instructor didn't list one
- Picked up ANY @unh.edu address anywhere in the document

**Fix needed:** Add context checking - only detect emails near "Instructor:", "Contact:", or "Professor:" sections. Ignore footer and support office emails.

---

## Common Patterns & What They Mean

### Pattern 1: High Precision, Low Recall
**Real Example:** `class_location` (100% precision, 64.8% recall, 78.6% F1)

**What's happening:**
- Detector found 105 locations
- ALL 105 were correct (perfect precision!)
- BUT it missed 57 locations that actually existed
- Out of 162 total physical locations, it only found 105

**Examples of missed locations:**
- Missed: `Pandora Building (UNHM) P 146` (complex format with building name and room)
- Missed: `Zoom or on-campus (scheduled)` (hybrid format - not purely physical)
- Only detected simple formats like "Room 105" or "P380"

**Why:** Detector is too conservative - only catches simple "Room XXX" patterns, misses complex formats.

**Fix:** Add more regex patterns for:
  - Building names followed by room numbers
  - Hybrid formats (physical + online options)
  - Different punctuation styles

---

### Pattern 2: Low Precision, High Recall
**Real Example:** `email` (28.2% precision, 88.6% recall, 42.8% F1)

**What's happening:**
- Detector found 31 out of 35 real emails (great recall!)
- BUT it also falsely detected 79 non-emails as emails
- Examples of false alarms:
  - Picked up `sas.office@unh.edu` (support office) instead of instructor email
  - Detected emails in syllabi where instructor intentionally didn't list email
  - Probably grabbing any @unh.edu address in the document

**Why:** Detector is too loose - finds ANY email in the document, not specifically the instructor's email.

**Fix:** Add context checking. Only detect emails near "Instructor:", "Professor:", or "Contact:" sections. Ignore footer/support emails.

---

### Pattern 3: Balanced & Good
**Real Example:** `office_phone` (93.2% precision, 80.4% recall, 86.3% F1)

**What's happening:**
- Found 41 phone numbers, 39 were correct (only 2 false alarms)
- Out of 51 real phone numbers, found 41 (missed 10)
- Both metrics are strong

**Why:** Detector has good rules - identifies most phones without many errors.

**Fix:** Minor tuning to catch the 10 missed phone numbers. Overall, this detector works well.

---

### Pattern 4: Everything Low
**Real Example:** `instructor_department` (20.8% precision, 75.0% recall, 32.6% F1)

**What's happening:**
- Precision is terrible (20.8%) - 80% of detections are wrong!
- Recall is decent (75.0%) - finds most departments, but incorrectly
- F1 score is worst in the entire system (32.6%)

**Examples of errors:**
- File: `COMP_405 - Capuz_Fall - Fall 2022.docx`
  - Expected: (no department listed)
  - Found: `UNH Manchester` (WRONG - this is campus name, not department!)

- File: `COMP_405 - Jin_Fall - Fall 2021.pdf`
  - Expected: (no department specified in ground truth)
  - Found: `Applied Engineering and Sciences Department,` (FALSE ALARM)

**Why:** Detector is finding ANY organization name in the document - campuses, schools, departments - without understanding context.

**Fix:** Complete redesign needed. Add rules to:
  - Distinguish between campus names (UNH Manchester) vs departments
  - Only detect near "Department:" labels or instructor contact sections
  - Validate against known department names

---




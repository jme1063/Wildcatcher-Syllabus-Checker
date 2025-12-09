# Developer Guide: Adding New Field Detectors

## Overview

This application uses a simple architecture for detecting different fields in syllabus documents. Currently, only Student Learning Outcomes (SLOs) are implemented, but you can easily add more fields.

## Simple Structure

```
Project Structure:
├── detectors/                   # All field detection modules
│   └── slo_detector.py         # SLO detection (example)
├── api_routes.py               # Import your detectors here
└── DEVELOPER_GUIDE.md          # This file
```

That's it. No complex configuration files or engines.

## Adding a New Field Detector

### Step 1: Create Your Detector File

First, create a new file in the detectors folder. See other detectors as examples to base your code on. Each field is unique and has their own patterns, so you'll need to customize the detection logic for your specific field.

Example: `detectors/course_info_detector.py`

```python
import re
import logging
from typing import Dict, Any

class CourseIdDetector:
    def __init__(self):
        self.field_name = 'course_id'
        self.logger = logging.getLogger('detector.course_id')

    def detect(self, text: str) -> Dict[str, Any]:
        self.logger.info(f"Starting detection for field: {self.field_name}")

        # Your detection logic here
        pattern = r'([A-Z]{2,4}\s*\d{3,4})'
        matches = re.findall(pattern, text)

        if matches:
            course_id = matches[0]
            result = {
                'field_name': self.field_name,
                'found': True,
                'content': course_id
            }
            self.logger.info(f"FOUND: {self.field_name}")
        else:
            result = {
                'field_name': self.field_name,
                'found': False,
                'content': None
            }
            self.logger.info(f"NOT_FOUND: {self.field_name}")

        return result
```

### Step 2: Edit api_routes.py

Second, edit api_routes.py. The routes are responsible for handling file uploads and calling the detectors to analyze the text. That's why you need to add your new detector there.

```python
# Import your new detector
from detectors.course_detector import CourseDetector

def detect_slos_with_regex(text):
    # Use SLO detector
    slo_detector = SLODetector()
    slo_result = slo_detector.detect(text)

    # Add your new detector
    course_detector = CourseDetector()
    course_result = course_detector.detect(text)

    # Return results (modify as needed)
    has_slos = slo_result.get('found', False)
    slo_content = slo_result.get('content', None)

    return has_slos, slo_content
```

## Required Result Format

Detectors must return this format:

```python
{
    'field_name': 'course_id',      # Name of your field
    'found': True,                  # Whether field was detected
    'content': 'CS 101'             # Extracted content (if found)
}
```

## Quick Start

Ready to add your first field?

1. Copy `detectors/slo_detector.py` to `detectors/course_id_detector.py`
2. Change class name to `CourseIdDetector`
3. Change `field_name = 'course_id'`
4. Update the detection logic for course IDs
5. Import and use it in `api_routes.py`
6. Test it

Start with simple fields like course_id, instructor_email, or instructor_name.

## Displaying New Fields on the Frontend

### Step 3: Update the Frontend Display

After creating your detector and integrating it in `api_routes.py`, you need to update the frontend to display the new field results.

#### A. Update the API Response Format

First, modify `api_routes.py` to return the new field data in the response:

```python
def _process_single_file(file, temp_dir):
    # ... existing code ...

    # Check for SLOs
    has_slos, slo_content = detect_slos_with_regex(extracted_text)

    # Add your new field detection
    course_detector = CourseDetector()
    course_result = course_detector.detect(extracted_text)

    # Create messages for each field
    if has_slos:
        slo_message = "SLOs detected"
    else:
        slo_message = "Student Learning Outcome: Not find the acceptable title for SLO<br>• Student Learning Outcomes<br>• Student Learning Objectives<br>• Learning Outcomes<br>• Learning Objectives"

    if course_result['found']:
        course_message = "Course ID detected"
    else:
        course_message = "Course ID: Not found<br>• Must include course identifier (e.g., CS 101, MATH 205)"

    # Build combined message
    if has_slos and course_result['found']:
        message = "All fields detected"
    else:
        missing_fields = []
        if not has_slos:
            missing_fields.append(slo_message)
        if not course_result['found']:
            missing_fields.append(course_message)
        message = "Missing Fields:<br>" + "<br><br>".join(missing_fields)

    result = {
        "filename": filename,
        "slo_status": "PASS" if (has_slos and course_result['found']) else "FAIL",
        "has_slos": has_slos,
        "message": message,
        "course_id": course_result.get('content', None)  # Add new field data
    }

    # Include SLO content if found
    if has_slos and slo_content:
        result["slo_content"] = slo_content[:300] + "..." if len(slo_content) > 300 else slo_content

    return result
```

#### B. Update the Frontend JavaScript

Modify the `displaySLOResult` function in `templates/index.html` to handle the new field:

```javascript
// Find the displaySLOResult function (around line 1030) and update it:
function displaySLOResult(data) {
    const status = data.slo_status === "PASS"
        ? '<span class="status-pass"><i class="fas fa-check-circle"></i> PASS</span>'
        : '<span class="status-fail"><i class="fas fa-times-circle"></i> FAIL</span>';

    const sloPreview = data.slo_content
        ? `<div style="margin-top: 10px; padding: 10px; background: #f5f5f5; border-radius: 5px;">
             <strong>SLO Content Found:</strong><br>
             <pre style="white-space: pre-wrap; font-size: 12px;">${data.slo_content}</pre>
           </div>`
        : '';

    // Add display for your new field
    const courseIdPreview = data.course_id
        ? `<div style="margin-top: 10px; padding: 10px; background: #e8f4ff; border-radius: 5px;">
             <strong>Course ID Found:</strong><br>
             <span style="font-size: 14px; font-weight: bold;">${data.course_id}</span>
           </div>`
        : '';

    // Choose label based on pass/fail status
    const messageLabel = data.slo_status === "PASS" ? "Result:" : "Missing Fields:";

    const resultHTML = `
        <div class="upload-result">
            <h3><i class="fas fa-file-pdf"></i> ${data.filename}</h3>
            <div class="analysis-summary">
                <div class="status-item">
                    <strong>Result:</strong> ${status}
                </div>
                <div class="message">
                    <strong>${messageLabel}</strong> ${data.message}
                </div>
                ${sloPreview}
                ${courseIdPreview}
            </div>
        </div>
    `;

    addHTMLMessage(resultHTML, false);
}
```



### Frontend Integration Checklist

When adding a new field to the frontend:

- [ ] Update `api_routes.py` to include new field data in the response
- [ ] Modify the message format to include your field's missing/found status
- [ ] Update `displaySLOResult()` function in `index.html`
- [ ] Add preview section for when your field is found
- [ ] Update the overall PASS/FAIL logic to include your field
- [ ] Test with both passing and failing cases
- [ ] Add custom CSS styling if needed


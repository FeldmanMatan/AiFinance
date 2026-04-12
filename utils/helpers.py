import os
import json
import re
import logging
from datetime import datetime
import PyPDF2

logger = logging.getLogger(__name__)

def backup_json_locally(data, user_id, original_filename):
    try:
        backup_dir = "json_backups"
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = "".join(c if c.isalnum() else "_" for c in original_filename)
        filepath = os.path.join(backup_dir, f"{user_id}_{safe_filename}_{timestamp}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logger.info(f"Backed up JSON locally to {filepath}")
    except Exception as e:
        logger.error(f"Local backup failed: {e}")

def extract_text_from_pdf(uploaded_file):
    pdf_reader = PyPDF2.PdfReader(uploaded_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"
    return text

def clean_number(val):
    """Aggressively cleans string to return a valid float."""
    if isinstance(val, (int, float)):
        return float(val)
    if not val:
        return 0.0
    # Remove everything except digits, decimal point, and minus sign
    clean_str = re.sub(r'[^\d.-]', '', str(val))
    try:
        return float(clean_str) if clean_str else 0.0
    except Exception:
        return 0.0
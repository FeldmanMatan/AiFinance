import os
import json
import logging
from datetime import datetime
from google import genai
from google.genai import types
from dotenv import load_dotenv
from utils.helpers import extract_text_from_pdf

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
logger = logging.getLogger("AppLogger")

def run_extraction_agent(uploaded_file, user_id):
    if not GOOGLE_API_KEY: return {"error": "Missing API Key"}
    try:
        file_text = extract_text_from_pdf(uploaded_file)
        client = genai.Client(api_key=GOOGLE_API_KEY)
        
        prompt = f"""
        You are an Israeli financial data expert. 
        Extract data from the text and return a VALID JSON ARRAY.
        
        CRITICAL RULES:
        1. DO NOT translate terms. If the document says "הראל" or "פנסיה", output exactly "הראל" or "פנסיה" in Hebrew.
        2. If a value (like policy_number) is entirely missing or hidden, output an empty string "". DO NOT GUESS.
        3. AVOID unescaped double quotes inside your strings.
        
        FIELDS FOR EACH OBJECT:
        - "owner_id": The main personal ID (ת.ז) found at the top. Apply this EXACT ID to ALL objects.
        - "policy_number": Account/policy number (מספר קופה/פוליסה/חשבון).
        - "provider_name": Insurance company name (e.g. הראל, מנורה, אלטשולר).
        - "fund_type": (e.g. קרן פנסיה, קרן השתלמות, קופת גמל).
        - "current_balance": Number only.
        - "management_fee_accumulation": % from balance.
        - "management_fee_deposit": % from deposit.
        - "investment_track": Full track name exactly as written.
        
        TEXT:
        {file_text}
        """
        
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        
        raw_text = response.text.strip()
        if raw_text.startswith("```json"): raw_text = raw_text[7:]
        elif raw_text.startswith("```"): raw_text = raw_text[3:]
        if raw_text.endswith("```"): raw_text = raw_text[:-3]
        raw_text = raw_text.strip()
        
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as json_err:
            logger.error(f"JSON Parsing Error: {json_err}")
            return {"error": "המודל ייצר פורמט לא תקין. אנא העלה מחדש."}
            
        if not isinstance(data, list): data = [data]
            
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for item in data:
            item["user_id"] = user_id 
            item["extraction_date"] = now
            if not item.get("owner_id"): item["owner_id"] = "לא_זוהה"
                
        return data
    except Exception as e:
        logger.error(f"AI Extraction failed: {e}")
        return {"error": str(e)}

def run_analyst_agent(data, analysis_type="portfolio"):
    if not GOOGLE_API_KEY: return "Error: No API Key"
    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)
        if analysis_type == "portfolio":
            p = f"Analyze this portfolio and give a report in HEBREW. Data: {json.dumps(data, ensure_ascii=False)}"
        else:
            p = f"Deep dive into this fund using Google Search. Report in HEBREW. Data: {json.dumps(data, ensure_ascii=False)}"
            
        response = client.models.generate_content(
            model=GEMINI_MODEL, contents=p,
            config=types.GenerateContentConfig(tools=[{"google_search": {}}], temperature=0.3)
        )
        return response.text
    except Exception as e:
        logger.error(f"AI Analyst failed: {e}")
        return "שגיאה בניתוח הנתונים."
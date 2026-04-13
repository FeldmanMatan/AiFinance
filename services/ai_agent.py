import os
import json
import logging
import re
from datetime import datetime
from google import genai
from google.genai import types
from dotenv import load_dotenv
from utils.helpers import extract_text_from_pdf

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
logger = logging.getLogger("AppLogger")

def _serialize_chat_history(chat_history, max_messages=8):
    if not chat_history:
        return "No previous conversation."

    serialized_messages = []
    for message in chat_history[-max_messages:]:
        role = message.get("role", "user")
        content = str(message.get("content", "")).strip()
        if not content:
            continue
        serialized_messages.append(f"{role.upper()}: {content}")

    return "\n".join(serialized_messages) if serialized_messages else "No previous conversation."

def run_chat_agent(user_message, active_user, portfolio_data=None, chat_history=None):
    if not GOOGLE_API_KEY:
        return "חסר מפתח API של Gemini ולכן הצ'אט לא זמין כרגע."

    portfolio_data = portfolio_data or []
    chat_history = chat_history or []

    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)
        portfolio_json = json.dumps(portfolio_data, ensure_ascii=False, indent=2)
        conversation_text = _serialize_chat_history(chat_history)

        system_instruction = f"""
        You are Ai Finance Chat, an in-app assistant for Israeli pension and investment tracking.

        RULES:
        - Reply in HEBREW unless the user writes in another language.
        - Be concise, practical, and friendly.
        - Base portfolio-specific answers only on the provided data.
        - If the user asks about a specific fund or policy number, use the provided portfolio data to answer.
        - If the data is missing, say so clearly. Do not make up numbers.
        - Do not present your answer as regulated financial advice.
        - If the user asks for calculations, explain them clearly.

        ACTIVE USER: {active_user}
        PORTFOLIO DATA: {portfolio_json}
        """

        user_prompt = f"PREVIOUS CHAT:\n{conversation_text}\n\nUSER MESSAGE:\n{user_message}"

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                temperature=0.4,
                system_instruction=system_instruction
            )
        )

        return response.text.strip() if response.text else "לא הצלחתי לייצר תשובה. נסה לנסח את השאלה מחדש."
    except Exception as e:
        logger.error(f"AI Chat failed: {e}")
        return f"אירעה שגיאה בקריאה למודל: {str(e)}"

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
        
        # --- FIX: Bulletproof JSON extraction using Regex ---
        json_match = re.search(r'\[.*\]', raw_text, re.DOTALL)
        if json_match:
            raw_text = json_match.group(0)
        else:
            # Fallback cleanup
            if raw_text.startswith("```json"):
                raw_text = raw_text.replace("```json", "").replace("```", "").strip()

        extracted_data = json.loads(raw_text)
        
        if isinstance(extracted_data, dict):
            extracted_data = [extracted_data]
            
        for d in extracted_data:
            d["extraction_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            d["user_id"] = user_id
            
        return extracted_data
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return {"error": str(e)}

def run_analyst_agent(portfolio_data, analysis_type="portfolio"):
    if not GOOGLE_API_KEY:
        return "חסר מפתח API של Gemini."

    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)
        data_str = json.dumps(portfolio_data, ensure_ascii=False, indent=2)
        search_tool = {"google_search": {}}

        if analysis_type == "portfolio":
            prompt = f"You are a senior Israeli financial analyst. Review this entire portfolio data and provide macro-level insights in Hebrew. Identify overall asset allocation, potential duplicate fees, or risks. Do NOT provide direct regulated advice, just objective insights.\n\nPortfolio Data:\n{data_str}"
        else:
            prompt = f"You are a senior Israeli financial analyst. Review this specific fund data and provide micro-level insights in Hebrew. Compare the current track against recent market trends using your search tool.\n\nFund Data:\n{data_str}"

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(tools=[search_tool], temperature=0.3)
        )
        return response.text
    except Exception as e:
        logger.error(f"Analyst agent failed: {e}")
        return f"אירעה שגיאה בניתוח הנתונים: {str(e)}"
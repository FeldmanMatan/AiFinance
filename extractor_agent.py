import streamlit as st
import os
import json
import certifi
from google import genai
from google.genai import types
import PyPDF2
import gspread
from dotenv import load_dotenv

# --- SSL FIX FOR WINDOWS ---
# Force Python and requests to use certifi's valid certificate bundle
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

# Load environment variables (API Key and Sheet ID)
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

# --- AGENT LOGIC (Extraction) ---

def extract_text_from_pdf(uploaded_file):
    # Read the PDF file directly from Streamlit's memory buffer
    pdf_reader = PyPDF2.PdfReader(uploaded_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"
    return text

def run_extraction_agent(uploaded_file, user_id):
    # Check if API key is present before calling Gemini
    if not GOOGLE_API_KEY:
        return {"error": "Google API Key is missing. Check your .env file."}
        
    # Step 1: Extract raw text from the file using PyPDF2
    file_text = extract_text_from_pdf(uploaded_file)
    
    # Step 2: Initialize the NEW Gemini Client
    client = genai.Client(api_key=GOOGLE_API_KEY)
    
    # Step 3: Build the extraction prompt with explicit JSON instructions
    prompt = f"""
    You are an expert financial data extraction agent.
    Review the following pension/investment report for the user '{user_id}'.
    Extract the following information and return it.
    If a value is not found in the text, use null.
    
    Required fields:
    - "provider_name": The company managing the fund (e.g., Harel, Menora, Altshuler)
    - "fund_type": The type of fund (e.g., Keren Hishtalmut, Pension, Kupat Gemel)
    - "current_balance": The total current balance (number only, remove commas and currency symbols)
    - "management_fee_accumulation": Management fee from the total balance (percentage as float)
    - "management_fee_deposit": Management fee from new deposits (percentage as float)
    - "investment_track": The precise name of the investment track (e.g., S&P 500, General, Shares)

    Document Text:
    {file_text}
    """
    
    # Step 4: Call Gemini using the new SDK syntax and force JSON format
    try:
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        
        # Step 5: Parse the result into a Python dictionary
        extracted_data = json.loads(response.text)
        extracted_data["user_id"] = user_id 
        return extracted_data
    except Exception as e:
        return {"error": f"Failed to process document: {str(e)}"}

# --- DATABASE LOGIC (Google Sheets) ---

def save_data_to_sheet(data):
    try:
        # Authenticate using the service account
        gc = gspread.service_account(filename='service_account.json')
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        worksheet = sh.sheet1
        
        # Define the row structure based on extracted JSON fields
        row_to_insert = [
            data.get("user_id", ""),
            data.get("provider_name", ""),
            data.get("fund_type", ""),
            data.get("current_balance", ""),
            data.get("management_fee_accumulation", ""),
            data.get("management_fee_deposit", ""),
            data.get("investment_track", "")
        ]
        
        # Append the row to the bottom of the sheet
        worksheet.append_row(row_to_insert)
        return True, "Data successfully saved to Google Sheets!"
    except Exception as e:
        return False, f"Database Error: {str(e)}"

def fetch_data_for_user(user_id):
    """Fetches all rows for a specific user from Google Sheets."""
    try:
        gc = gspread.service_account(filename='service_account.json')
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        worksheet = sh.sheet1
        
        # Get all rows from the sheet
        all_values = worksheet.get_all_values()
        
        # Filter rows by the requested user_id (assuming user_id is in column 0)
        user_rows = []
        for row in all_values:
            if len(row) > 0 and row[0] == user_id:
                user_rows.append(row)
        return user_rows
    except Exception as e:
        st.error(f"Failed to fetch data: {str(e)}")
        return []

# --- STREAMLIT UI ---

st.set_page_config(page_title="Pension & Investment Tracker", layout="wide")

# Sidebar setup for navigation and user profile selection
st.sidebar.title("Navigation")
active_user = st.sidebar.selectbox("Select User Profile", ["Matan", "Client A", "Client B", "Add New..."])
menu = st.sidebar.radio("Go to:", ["Dashboard", "Upload Report"])

if menu == "Dashboard":
    st.title(f"Financial Overview: {active_user}")
    
    with st.spinner("Fetching data from database..."):
        raw_data = fetch_data_for_user(active_user)
        
    if not raw_data:
        st.info(f"No data found for {active_user}. Please upload a report to get started.")
    else:
        # Variables to calculate total sums
        total_balance = 0.0
        pension_balance = 0.0
        hishtalmut_balance = 0.0
        
        display_data = []
        
        for row in raw_data:
            # Map columns based on our insert structure
            provider = row[1] if len(row) > 1 else "Unknown"
            f_type = row[2] if len(row) > 2 else "Unknown"
            balance_str = row[3] if len(row) > 3 else "0"
            track = row[6] if len(row) > 6 else "Unknown"
            
            # Safely convert the balance string to a float for calculation
            try:
                clean_balance = str(balance_str).replace(',', '').replace('₪', '').strip()
                balance = float(clean_balance) if clean_balance else 0.0
            except ValueError:
                balance = 0.0
                
            total_balance += balance
            
            # Categorize the funds for the metric display
            if "פנסיה" in f_type or "Pension" in f_type or "pension" in f_type.lower():
                pension_balance += balance
            elif "השתלמות" in f_type or "Hishtalmut" in f_type:
                hishtalmut_balance += balance
                
            # Add to the table display list
            display_data.append({
                "Provider": provider,
                "Fund Type": f_type,
                "Investment Track": track,
                "Balance": f"₪ {balance:,.2f}"
            })
            
        # Display dynamic metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="Total Portfolio Balance", value=f"₪ {total_balance:,.2f}")
        with col2:
            st.metric(label="Keren Hishtalmut", value=f"₪ {hishtalmut_balance:,.2f}")
        with col3:
            st.metric(label="Pension", value=f"₪ {pension_balance:,.2f}")
            
        st.markdown("---")
        st.subheader("Your Active Funds")
        st.table(display_data)

        
elif menu == "Upload Report":
    st.title(f"Upload Reports for {active_user}")
    
    # Allow multiple PDF uploads for the same user session
    uploaded_files = st.file_uploader(
        "Drag and drop multiple PDF files here", 
        type=["pdf"], 
        accept_multiple_files=True
    )
    
    if uploaded_files:
        if not GOOGLE_API_KEY:
            st.error("System Error: Google API Key is missing. Please check your .env file.")
        else:
            for file in uploaded_files:
                st.write(f"Processing: **{file.name}**...")
                
                # 1. Trigger the Extraction Agent (Gemini)
                result_json = run_extraction_agent(file, active_user)
                
                if "error" in result_json:
                    st.error(result_json["error"])
                else:
                    st.success(f"Successfully extracted data from {file.name}")
                    # Show a brief preview of extracted data instead of full JSON
                    st.write(f"Identified Fund: {result_json.get('provider_name')} - {result_json.get('fund_type')}")
                    
                    # 2. Trigger data persistence to Google Sheets
                    with st.spinner("Saving to database..."):
                        success, db_message = save_data_to_sheet(result_json)
                        if success:
                            st.success(db_message)
                        else:
                            st.error(db_message)
            
            st.info("All files processed and stored.")
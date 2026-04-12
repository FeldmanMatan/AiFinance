import os
import logging
import gspread
import re
from dotenv import load_dotenv

load_dotenv()
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
logger = logging.getLogger("AppLogger")

def get_worksheet(sh, user_id):
    if user_id not in [ws.title for ws in sh.worksheets()]:
        ws = sh.add_worksheet(title=user_id, rows="100", cols="11")
        ws.append_row(["Date", "Owner ID", "Policy #", "Provider", "Type", "Track", "Balance", "Fee Acc", "Fee Dep", "Tag", "Search Link"])
        return ws
    return sh.worksheet(user_id)

def strict_normalize(val):
    """Keeps ONLY Hebrew, English, and Digits. Strips spaces and symbols to match keys perfectly."""
    if not val: return ""
    return re.sub(r'[^\w\u0590-\u05FF]', '', str(val)).lower()

def generate_key(oid, pol, prov, ftype):
    """Generates an unbreakable unique key. Uses a fallback if Policy Number is missing."""
    n_oid = strict_normalize(oid)
    n_pol = strict_normalize(pol)
    n_prov = strict_normalize(prov)
    n_ftype = strict_normalize(ftype)
    
    # If policy number is successfully extracted
    if n_pol and n_pol not in ["null", "none", "unknown"]:
        return f"pol_{n_pol}_{n_oid}"
    else:
        # FALLBACK: If policy is missing, identify by Provider + Fund Type + Owner ID
        return f"fallback_{n_prov}_{n_ftype}_{n_oid}"

def save_data_to_sheet(data_list, user_id):
    try:
        gc = gspread.service_account(filename='service_account.json')
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        ws = get_worksheet(sh, user_id)
            
        all_rows = ws.get_all_values()
        
        # 1. Map existing keys from the database
        existing_keys = {}
        if len(all_rows) > 1:
            for i, r in enumerate(all_rows):
                if i == 0: continue
                sheet_oid = r[1] if len(r) > 1 else ""
                sheet_pol = r[2] if len(r) > 2 else ""
                sheet_prov = r[3] if len(r) > 3 else ""
                sheet_ftype = r[4] if len(r) > 4 else ""
                
                key = generate_key(sheet_oid, sheet_pol, sheet_prov, sheet_ftype)
                existing_keys[key] = i + 1
        
        # 2. Process new data
        for d in data_list:
            raw_oid = str(d.get("owner_id", ""))
            raw_pol = str(d.get("policy_number", ""))
            raw_prov = str(d.get("provider_name", ""))
            raw_ftype = str(d.get("fund_type", ""))
            
            current_key = generate_key(raw_oid, raw_pol, raw_prov, raw_ftype)
            
            search_query = f"תשואות {raw_prov} {raw_ftype} {d.get('investment_track', '')}".replace(" ", "+")
            search_link = f"[https://www.google.com/search?q=](https://www.google.com/search?q=){search_query}"
            
            row_data = [
                d.get("extraction_date", ""), raw_oid, raw_pol, raw_prov,
                raw_ftype, d.get("investment_track", ""),
                d.get("current_balance", ""), d.get("management_fee_accumulation", ""),
                d.get("management_fee_deposit", ""), "", search_link
            ]
            
            if current_key in existing_keys:
                idx = existing_keys[current_key]
                logger.info(f"MATCH FOUND ({current_key}): Updating row {idx}")
                ws.update(values=[row_data[:9]], range_name=f"A{idx}:I{idx}")
                ws.update_cell(idx, 11, search_link)
            else:
                logger.info(f"NO MATCH ({current_key}): Appending new row")
                ws.append_row(row_data)
                # Register to prevent inner-duplicates in the same extraction array
                new_row_idx = len(ws.get_all_values())
                existing_keys[current_key] = new_row_idx
                
        return True, "Sync Completed"
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        return False, str(e)

def update_tag_in_sheet(user_id, policy_number, owner_id, new_tag):
    try:
        gc = gspread.service_account(filename='service_account.json')
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        ws = sh.worksheet(user_id)
        rows = ws.get_all_values()
        
        target_oid = strict_normalize(owner_id)
        target_pol = strict_normalize(policy_number)
        
        for i, r in enumerate(rows):
            if i == 0: continue
            if strict_normalize(r[1]) == target_oid and strict_normalize(r[2]) == target_pol:
                ws.update_cell(i+1, 10, new_tag)
                return True, "Tag Updated"
        return False, "Record not found"
    except Exception as e:
        logger.error(f"Tag error: {e}")
        return False, str(e)

def fetch_data_for_user(user_id):
    try:
        gc = gspread.service_account(filename='service_account.json')
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        if user_id not in [ws.title for ws in sh.worksheets()]: return []
        return sh.worksheet(user_id).get_all_values()[1:]
    except Exception as e:
        logger.error(f"Fetch error: {e}")
        return []
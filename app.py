# --- SYSTEM CERTS PATCH ---
try:
    import pip_system_certs.wrapt_requests
except ImportError:
    pass

import streamlit as st
import pandas as pd
import plotly.express as px
import logging
from logging.handlers import RotatingFileHandler

# Import our custom modules
from utils.helpers import backup_json_locally, clean_number
from services.db_manager import save_data_to_sheet, fetch_data_for_user, update_tag_in_sheet
from services.ai_agent import run_extraction_agent, run_analyst_agent, run_chat_agent

# --- LOGGING SETUP (ROTATING LOGS) ---
logger = logging.getLogger("AppLogger")
logger.setLevel(logging.INFO)

# Clear existing handlers to prevent duplicate logs on Streamlit reruns
if logger.hasHandlers():
    logger.handlers.clear()

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# 1. File Handler with Rotation (Max 1MB per file, keeps 1 backup)
file_handler = RotatingFileHandler('app.log', maxBytes=1024 * 1024, backupCount=1, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# 2. Console Handler (Prints logs live to your terminal)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

logger.info("--- Streamlit UI Initialized / Refreshed ---")


def load_local_css(path: str):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            st.markdown(f"<style>{fh.read()}</style>", unsafe_allow_html=True)
    except Exception as e:
        logger.warning(f"Could not load CSS {path}: {e}")

# Load local styles (non-fatal)
load_local_css("static/styles.css")

# --- STREAMLIT UI ---
st.set_page_config(page_title="Pension Tracker", layout="wide")
st.sidebar.title("Navigation")
active_user = st.sidebar.selectbox("Profile", ["Matan", "Client A", "Client B"])
menu = st.sidebar.radio("Go to:", ["Dashboard", "Upload"])

if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = {}

if "chat_open" not in st.session_state:
    st.session_state.chat_open = True

if menu == "Dashboard":
    st.title(f"Financial Overview: {active_user}")
    
    logger.info(f"Loading dashboard for user: {active_user}")
    data = fetch_data_for_user(active_user)
    raw_ai_portfolio = []
    
    if not data:
        st.info("No data yet. Please upload a report.")
    else:
        total = pension = hishtalmut = gemel = 0.0
        display = []
        fund_ai_mapping = {}
        selector_list = []
        
        for r in data:
            oid = r[1] if len(r) > 1 else ""
            pol = r[2] if len(r) > 2 else ""
            prov = r[3] if len(r) > 3 else ""
            ftype = r[4] if len(r) > 4 else ""
            track = r[5] if len(r) > 5 else ""
            bal_str = r[6] if len(r) > 6 else "0"
            fee1 = r[7] if len(r) > 7 else ""
            fee2 = r[8] if len(r) > 8 else ""
            tag = r[9] if len(r) > 9 else ""
            link = r[10] if len(r) > 10 else ""

            # Use the aggressive cleaner from utils
            bal = clean_number(bal_str)
            
            total += bal
            if "פנסיה" in ftype: pension += bal
            elif "השתלמות" in ftype: hishtalmut += bal
            elif "גמל" in ftype: gemel += bal
            
            display.append({
                "Owner ID": oid, "Policy #": pol, "Provider": prov, "Type": ftype,
                "Track": track, "Balance": f"₪ {bal:,.2f}", "Tag": tag, "Link": link
            })
            
            raw_ai_portfolio.append({"Provider": prov, "Type": ftype, "Track": track, "Balance": bal})
            
            if pol:
                selector_string = f"{pol} | {prov} - {ftype} (Owner: {oid})"
                selector_list.append(selector_string)
                fund_ai_mapping[selector_string] = {
                    "Policy": pol, "Provider": prov, "Type": ftype, 
                    "Track": track, "Balance": bal, "Fee (Accumulation)": fee1, "Fee (Deposit)": fee2
                }

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", f"₪ {total:,.2f}")
        c2.metric("Pension", f"₪ {pension:,.2f}")
        c3.metric("Hishtalmut", f"₪ {hishtalmut:,.2f}")
        c4.metric("Gemel", f"₪ {gemel:,.2f}")

        st.markdown("---")
        chart_col, table_col = st.columns([1, 2])
        with chart_col:
            df_pie = pd.DataFrame({"Product": ["Pension", "Hishtalmut", "Gemel"], "Amount": [pension, hishtalmut, gemel]})
            filtered_pie = df_pie[df_pie["Amount"] > 0]
            if not filtered_pie.empty:
                fig = px.pie(filtered_pie, values='Amount', names='Product', hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("אין מספיק נתונים להצגת הגרף.")
            
        with table_col:
            st.subheader("Active Funds")
            df_display = pd.DataFrame(display)
            if not df_display.empty:
                st.dataframe(df_display, width='stretch', column_config={"Link": st.column_config.LinkColumn("נתוני אמת")})
                csv = df_display.to_csv(index=False)
                st.download_button("Download CSV", data=csv, file_name=f"{active_user}_funds.csv", mime="text/csv")
            else:
                st.info("No active funds to display.")

        st.markdown("---")
        st.subheader("🏷️ Tag Management")
        t1, t2, t3 = st.columns([2, 3, 1])
        with t1: sel = st.selectbox("Select Policy:", selector_list)
        with t2: val = st.text_input("New Tag:")
        with t3: 
            st.write(""); st.write("")
            if st.button("Save Tag") and sel:
                p = fund_ai_mapping[sel]["Policy"]
                o = sel.split("(Owner: ")[1].replace(")", "")
                logger.info(f"Attempting to update tag for Policy: {p}, Owner: {o}")
                success, msg = update_tag_in_sheet(active_user, p, o, val)
                if success: 
                    st.rerun()
                else:
                    st.error(msg)

        st.markdown("---")
        st.subheader("🤖 AI Analyst")
        tab_macro, tab_micro = st.tabs(["📊 Portfolio Analysis", "🔎 Single Fund Deep Dive"])
        
        with tab_macro:
            if st.button("Analyze Full Portfolio"):
                with st.spinner("Analyzing..."):
                    logger.info("Triggered AI Analyst for Full Portfolio")
                    res = run_analyst_agent(raw_ai_portfolio, analysis_type="portfolio")
                    with st.expander("📄 Report", expanded=True): st.markdown(res)
                        
        with tab_micro:
            if selector_list:
                fund_to_analyze = st.selectbox("Select Fund to analyze:", selector_list)
                if st.button("Analyze Selected Fund"):
                    with st.spinner("Searching web & analyzing..."):
                        logger.info(f"Triggered AI Analyst for Single Fund: {fund_to_analyze}")
                        specific_data = fund_ai_mapping[fund_to_analyze]
                        res = run_analyst_agent(specific_data, analysis_type="fund")
                        with st.expander(f"📄 Report - {fund_to_analyze}", expanded=True): st.markdown(res)

    default_message = {
        "role": "assistant",
        "content": f"שלום, אני העוזר של {active_user}. אפשר לשאול אותי על התיק, על סוגי הקופות ועל הנתונים שהועלו למערכת."
    }
    active_chat = st.session_state.chat_sessions.setdefault(active_user, [default_message])

    st.sidebar.markdown("---")
    st.sidebar.subheader("AI Chat")
    if st.sidebar.button(
        "Close Chat" if st.session_state.chat_open else "Open Chat",
        key=f"toggle_chat_{active_user}"
    ):
        st.session_state.chat_open = not st.session_state.chat_open
        st.rerun()

    if st.session_state.chat_open:
        st.sidebar.caption(f"Chat about {active_user}'s portfolio.")

        if st.sidebar.button("Clear Chat", key=f"clear_chat_{active_user}"):
            st.session_state.chat_sessions[active_user] = [default_message]
            st.rerun()

        if not raw_ai_portfolio:
            st.sidebar.info("General chat works now. Portfolio-specific answers improve after uploading data.")

        chat_container = st.sidebar.container()
        with chat_container:
            for message in active_chat:
                speaker = "You" if message["role"] == "user" else "Bot"
                st.markdown(f"**{speaker}:** {message['content']}")

        with st.sidebar.form(key=f"chat_form_{active_user}", clear_on_submit=True):
            prompt = st.text_area(
                "Message",
                placeholder="Ask about balances, funds, fees, or next actions...",
                height=80,
                key=f"chat_prompt_{active_user}"
            )
            send_chat = st.form_submit_button("Send")

        if send_chat and prompt.strip():
            prompt = prompt.strip()
            active_chat.append({"role": "user", "content": prompt})
            with st.sidebar.spinner("Thinking..."):
                reply = run_chat_agent(
                    user_message=prompt,
                    active_user=active_user,
                    portfolio_data=raw_ai_portfolio,
                    chat_history=active_chat[:-1]
                )

            active_chat.append({"role": "assistant", "content": reply})
            st.rerun()

elif menu == "Upload":
    st.title(f"Upload for {active_user}")
    files = st.file_uploader("PDFs", type=["pdf"], accept_multiple_files=True)
    if files:
        for f in files:
            logger.info(f"Uploading and extracting file: {f.name}")
            res = run_extraction_agent(f, active_user)
            if "error" not in res:
                backup_json_locally(res, active_user, f.name)
                save_data_to_sheet(res, active_user)
                st.success(f"Processed {f.name}")
            else:
                logger.error(f"Failed processing {f.name}: {res['error']}")
                st.error(res["error"])
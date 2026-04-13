# Ai Finance: Israeli Pension & Investment Tracker

## Vision
Managing financial portfolios in Israel can be overwhelming due to complex, non-standardized PDF reports from various providers. **Ai Finance** aims to empower users by automating the extraction of financial data and providing AI-driven insights. By bridging the gap between static PDF documents and dynamic market data, this tool offers a clear, real-time view of a user's financial future.

## Overview
Ai Finance is a specialized FinTech application built with Python. It utilizes Large Language Models (LLM) to parse Hebrew financial reports, store them in a structured Google Sheets database, and provide a comprehensive dashboard for asset management and analysis.

## Key Features
- **Automated Data Extraction:** Uses Gemini 1.5 Flash to accurately extract Owner IDs, policy numbers, balances, and management fees from complex Hebrew PDFs.
- **Smart Data Synchronization:** Features a "Compound Key" upsert logic to prevent duplicate records and ensure data integrity even when reports are uploaded multiple times.
- **Interactive Dashboard:** A Streamlit-based interface providing real-time metrics and asset allocation visualization (Pie Charts) using Plotly.
- **AI Financial Analyst:** An integrated agent with **Google Search Grounding** that analyzes the portfolio against current market trends and provides actionable recommendations in Hebrew.
- **In-App Chat Assistant:** A Gemini-powered chat panel inside the dashboard that answers user questions about the selected portfolio and uploaded fund data.
- **Modular Architecture:** Cleanly separated services for AI processing, database management, and UI rendering for high maintainability.

## Tech Stack
- **Frontend:** [Streamlit](https://streamlit.io/)
- **AI/LLM:** [Google Gemini API](https://ai.google.dev/) (with Search Grounding)
- **Database:** Google Sheets API (via `gspread`)
- **Data Visualization:** [Plotly](https://plotly.com/)
- **Language:** Python 3.x

## Security Note
This project is configured to ignore sensitive files such as `.env` and `service_account.json`. Always ensure your credentials are kept local and never pushed to public repositories.

---
*Developed by Matan*
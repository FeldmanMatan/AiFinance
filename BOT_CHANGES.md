# Bot Changes

This file documents all bot-related changes added to the application.

## Summary

An in-app AI chat assistant was added to the existing Streamlit application. The bot uses the Gemini API, keeps separate conversations per selected user, and can answer questions based on the current user's uploaded portfolio data.

## Files Changed

- `services/ai_agent.py`
- `app.py`
- `README.md`

## Detailed Changes

### 1. New chat backend in `services/ai_agent.py`

Added a helper function:

- `_serialize_chat_history(chat_history, max_messages=8)`

What it does:

- Converts recent chat messages into plain text
- Limits the amount of prior conversation sent to the model
- Preserves role labels such as `USER` and `ASSISTANT`

Added a new main function:

- `run_chat_agent(user_message, active_user, portfolio_data=None, chat_history=None)`

What it does:

- Sends the current message to Gemini
- Includes the active profile name in the prompt
- Includes the current user's portfolio data in the prompt
- Includes recent conversation history in the prompt
- Returns answers in Hebrew by default
- Avoids making up portfolio facts when data is missing
- Returns a fallback message if the API key is missing or a request fails

Prompt behavior added for the bot:

- Reply in Hebrew unless the user writes in another language
- Keep answers concise and practical
- Base portfolio-specific answers only on provided data
- Avoid presenting answers as regulated financial advice
- Explain calculations when the user asks for them

### 2. Chat integration in `app.py`

Updated imports:

- Added `run_chat_agent` to the imported AI functions

Added Streamlit session state storage:

- `st.session_state.chat_sessions`
- `st.session_state.chat_open`

What they do:

- `chat_sessions` stores separate conversations for each selected profile
- `chat_open` controls whether the sidebar chat is visible or hidden

Added chat initialization logic:

- Each selected user gets a default assistant welcome message
- The chat session is created the first time that user opens the dashboard

Added sidebar chat UI:

- New `AI Chat` section in the sidebar
- `Open Chat` / `Close Chat` toggle button
- `Clear Chat` button to reset a user's conversation
- Sidebar text area for entering a message
- `Send` button using a Streamlit form

Chat behavior in the sidebar:

- Messages are rendered in the sidebar instead of the main dashboard body
- User and bot messages are shown in order
- After sending a message, the app calls `run_chat_agent(...)`
- The assistant response is appended to the stored session history
- The app reruns after send or clear to refresh the sidebar state

Portfolio-awareness added to chat:

- The bot receives `raw_ai_portfolio` from the dashboard
- That data is built from the currently selected user's records
- If no uploaded data exists, the sidebar shows an informational message
- General chat still works even when no portfolio data has been uploaded

### 3. UI placement change

Initial bot implementation:

- The first version of the chat was placed in the main dashboard area

Later update:

- The chat was moved into the sidebar
- A visible open/close control was added

Reason for the update:

- Keeps the main dashboard cleaner
- Makes the chat easier to hide when not needed
- Matches the requirement for a close/open experience outside the main content area

### 4. Documentation update in `README.md`

Added a new feature line:

- `In-App Chat Assistant`

What it documents:

- The app now includes a Gemini-powered chat panel
- The chat can answer questions about the selected portfolio and uploaded fund data

## Validation Performed

The following validations were run after the bot changes:

```powershell
& .\venv\Scripts\python.exe -m py_compile app.py services\ai_agent.py services\db_manager.py utils\helpers.py
& .\venv\Scripts\python.exe -m py_compile app.py
```

Result:

- No syntax errors were reported by `py_compile`
- Editor diagnostics also reported no errors in the updated files during validation

## Current Bot Capabilities

The bot currently supports:

- In-app chat from the Streamlit sidebar
- Open and close behavior
- Clear chat behavior
- Separate chat history for each selected user profile
- Portfolio-aware answers using uploaded dashboard data
- Hebrew-first responses

## Not Added Yet

The following features were not added yet:

- A dedicated `Summarize Portfolio` button in the sidebar
- Auto-generated summary on chat open
- Streaming partial responses while the model is generating
- Custom chat bubble styling in CSS
- Bottom bar chat layout

## Current File Location

This change log is stored at the project root as:

- `BOT_CHANGES.md`
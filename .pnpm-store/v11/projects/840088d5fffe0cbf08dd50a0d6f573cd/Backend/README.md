# Refyne AI Backend

This is the backend for the Refyne AI Requirement Engineering project.

## Setup

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Unix/MacOS:
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and fill in the values.

3. Run the application:
   ```bash
   uvicorn app.main:app --reload
   ```

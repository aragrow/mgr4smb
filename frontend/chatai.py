"""
FastAPI Chat AI Test Interface

A comprehensive test interface for the conversation agent.
No HTML file needed - everything is in Python + Jinja2 templates.

Features:
- Authentication token management
- Test message submission
- CSV test data loader
- Execution logs viewer
- Real-time token validation

Run with: python frontend/chatai.py
"""

import os
import csv
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from frontend/.env.local
env_path = Path(__file__).parent / '.env.local'
load_dotenv(env_path)

# Get API credentials from environment
API_CLIENTS = os.getenv('API_CLIENTS', '')
if '=' in API_CLIENTS:
    client_id, client_secret = API_CLIENTS.split('=', 1)
else:
    client_id = '036c5b6c-8578-4d69-8100-9ad970029d06'
    client_secret = '_U0IGh9wy9F1Iweqe26TM6cfpQi6Zs-rlKkfbZkWiMA'

# Initialize FastAPI app
app = FastAPI(
    title="Agent Test Interface",
    description="Development tool for testing the conversation agent",
    version="1.0.0"
)

# Mount docs directory for CSV access
docs_path = Path(__file__).parent.parent / "docs"
if docs_path.exists():
    app.mount("/static/docs", StaticFiles(directory=str(docs_path)), name="docs")

# Setup Jinja2 templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


# Pydantic Models
class TestEntry(BaseModel):
    """Test data entry from CSV"""
    sender_type: str
    from_email: Optional[str] = None
    from_phone: Optional[str] = None
    source: str
    contact_name: Optional[str] = None
    body: str


# API Routes
@app.get("/")
async def get_interface(request: Request):
    """
    Serve the main test interface

    Template variables injected:
    - client_id: OAuth client ID from .env.local
    - client_secret: OAuth client secret from .env.local
    - api_url: Default API endpoint
    - current_time: Server timestamp
    """
    return templates.TemplateResponse(
        "interface.html",
        {
            "request": request,
            "client_id": client_id,
            "client_secret": client_secret,
            "api_url": "http://localhost:8000/orchestrator/message",
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    )


@app.get("/api/csv-entries", response_model=List[TestEntry])
async def get_csv_entries():
    """
    Load test entries from CSV file

    Returns:
        List of test entries from src/data/test_questions.csv

    Raises:
        HTTPException: If CSV file not found
    """
    csv_path = Path(__file__).parent.parent / "src" / "data" / "test_questions.csv"

    if not csv_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"CSV file not found at {csv_path}"
        )

    entries = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                entries.append(TestEntry(
                    sender_type=row.get('sender_type', ''),
                    from_email=row.get('from_email') or None,
                    from_phone=row.get('from_phone') or None,
                    source=row.get('source', ''),
                    contact_name=row.get('contact_name') or None,
                    body=row.get('body', '')
                ))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error reading CSV: {str(e)}"
        )

    return entries


@app.get("/health")
async def health_check():
    """
    Health check endpoint

    Returns:
        Status information including service name and timestamp
    """
    return {
        "status": "healthy",
        "service": "chatai",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "client_id": client_id[:20] + "..." if len(client_id) > 20 else client_id
    }


# Main entry point
if __name__ == "__main__":
    # Get port from environment or use default
    port = int(os.getenv('CHATAI_PORT', 8015))

    # Display startup information
    print("\n" + "="*60)
    print("🚀 Agent Test Interface")
    print("="*60)
    print(f"📖 URL:        http://localhost:{port}")
    print(f"🔑 Client ID:  {client_id}")
    print(f"🔒 Config:     frontend/.env.local")
    print(f"📊 Test Data:  src/data/test_questions.csv")
    print("="*60 + "\n")

    # Start server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )

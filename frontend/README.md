# Agent Test Interface

A comprehensive Python-based test interface for the conversation agent.

## Architecture

**Pure Python + Jinja2 Templates** - No standalone HTML files!

```
frontend/
├── chatai.py              # FastAPI application (main entry point)
├── templates/
│   └── interface.html     # Jinja2 template with credentials injection
├── .env.local             # Configuration (not in git)
└── README.md              # This file
```

## Features

- ✅ **Token Management** - OAuth 2.0 authentication
- ✅ **Test Submissions** - Send messages via form or JSON
- ✅ **CSV Test Loader** - Load 160+ test questions
- ✅ **Execution Logs** - View API request/response logs
- ✅ **JSON API** - RESTful endpoints for test data

## Setup

```bash
cd frontend
cp .env.local.example .env.local
# Edit .env.local with your credentials
```

## Running

### Option 1: Main Menu (Recommended)
```bash
./main_menu.sh
# Select option 4
```

### Option 2: Direct
```bash
python3 frontend/chatai.py
```

Interface: **http://localhost:8015**

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/` | Main interface (HTML) |
| `/api/csv-entries` | Test entries (JSON) |
| `/health` | Health check |

## Migration from HTML

**Before:** Standalone HTML + Python server  
**After:** Python + Jinja2 templates + JSON API

No more standalone HTML files - everything is in Python!

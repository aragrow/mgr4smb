#!/bin/bash

# start_frontend.sh - Start the Frontend AI Agent Testing Interface
# This script can be run standalone or imported by main_menu.sh

set -e  # Exit on error

# Color codes for better UX
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Determine script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
FRONTEND_ENV="$FRONTEND_DIR/.env.local"
FRONTEND_SCRIPT="$FRONTEND_DIR/chatai.py"

# Function to check frontend configuration
check_frontend_config() {
    if [ ! -f "$FRONTEND_ENV" ]; then
        echo -e "${YELLOW}[WARNING]${NC} Frontend .env.local not found"

        if [ -f "$FRONTEND_DIR/.env.local.example" ]; then
            echo -e "${BLUE}[INFO]${NC} Creating .env.local from example..."
            cp "$FRONTEND_DIR/.env.local.example" "$FRONTEND_ENV"
            echo -e "${GREEN}[OK]${NC} Configuration file created"
            echo -e "${YELLOW}[ACTION REQUIRED]${NC} Please edit $FRONTEND_ENV with your credentials"
        else
            echo -e "${RED}[ERROR]${NC} No configuration template found"
            exit 1
        fi
    else
        echo -e "${GREEN}[OK]${NC} Frontend configuration found"
    fi
}

# Function to start frontend
start_frontend() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}🚀 Starting Frontend AI Agent Testing Interface...${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""

    # Kill existing frontend server if running
    echo -e "${YELLOW}[INFO]${NC} Checking for existing frontend server..."
    if pkill -f "python.*http.server.*8015" 2>/dev/null || pkill -f "python.*chatai" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} Stopped existing frontend server"
        sleep 2
    else
        echo -e "${BLUE}[INFO]${NC} No existing frontend server found"
    fi

    # Check if frontend script exists
    if [ ! -f "$FRONTEND_SCRIPT" ]; then
        echo -e "${RED}[ERROR]${NC} Frontend script not found at $FRONTEND_SCRIPT"
        exit 1
    fi

    # Check configuration
    check_frontend_config

    # Display startup info
    echo -e "${BLUE}[INFO]${NC} Frontend directory: $FRONTEND_DIR"
    echo -e "${BLUE}[INFO]${NC} Configuration: $FRONTEND_ENV"

    # Check if virtual environment exists
    if [ -d "$FRONTEND_DIR/.venv" ]; then
        echo -e "${GREEN}✓${NC} Using virtual environment: frontend/.venv"
        PYTHON_CMD="$FRONTEND_DIR/.venv/bin/python3"
    else
        echo -e "${YELLOW}⚠${NC} No virtual environment found, using system Python"
        PYTHON_CMD="python3"
    fi

    echo -e "${BLUE}[INFO]${NC} Interface will be available at: ${GREEN}http://localhost:8015${NC}"
    echo ""
    echo -e "${YELLOW}[TIP]${NC} Press Ctrl+C to stop the server"
    echo ""

    # Change to templates directory and run simple HTTP server
    # Note: Using simple HTTP server since chatai.py requires jinja2
    cd "$FRONTEND_DIR/templates"
    echo -e "${BLUE}[INFO]${NC} Starting HTTP server on port 8015..."
    python3 -m http.server 8015
}

# If script is run directly (not sourced), execute the function
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    start_frontend
fi

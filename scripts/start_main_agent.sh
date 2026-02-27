#!/bin/bash

# start_main_agent.sh - Start the MGR4SMB Main Agent Server
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
MAIN_ENV="$PROJECT_ROOT/.env.local"
MAIN_SCRIPT="$PROJECT_ROOT/src/api/main.py"

# Function to check main configuration
check_main_config() {
    if [ ! -f "$MAIN_ENV" ]; then
        echo -e "${YELLOW}[WARNING]${NC} Main .env.local not found"

        if [ -f "$PROJECT_ROOT/.env.example" ]; then
            echo -e "${BLUE}[INFO]${NC} Creating .env.local from example..."
            cp "$PROJECT_ROOT/.env.example" "$MAIN_ENV"
            echo -e "${GREEN}[OK]${NC} Configuration file created"
            echo -e "${YELLOW}[ACTION REQUIRED]${NC} Please edit $MAIN_ENV with your credentials"
        else
            echo -e "${RED}[ERROR]${NC} No configuration template found"
            exit 1
        fi
    else
        echo -e "${GREEN}[OK]${NC} Main configuration found"
    fi
}

# Function to start main agent
start_main_agent() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}🤖 Starting MGR4SMB Main Agent Server...${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""

    # Kill existing main agent server if running
    echo -e "${YELLOW}[INFO]${NC} Checking for existing main agent server..."
    if pkill -f "python.*src.api.main" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} Stopped existing main agent server"
        sleep 2
    else
        echo -e "${BLUE}[INFO]${NC} No existing main agent server found"
    fi

    # Check if main script exists
    if [ ! -f "$MAIN_SCRIPT" ]; then
        echo -e "${RED}[ERROR]${NC} Main script not found at $MAIN_SCRIPT"
        exit 1
    fi

    # Check configuration
    check_main_config

    # Display startup info
    echo -e "${BLUE}[INFO]${NC} Project directory: $PROJECT_ROOT"
    echo -e "${BLUE}[INFO]${NC} Configuration: $MAIN_ENV"

    # Check if virtual environment exists
    if [ -d "$PROJECT_ROOT/.venv" ]; then
        echo -e "${GREEN}✓${NC} Using virtual environment: .venv"
        PYTHON_CMD="$PROJECT_ROOT/.venv/bin/python3"
    else
        echo -e "${YELLOW}⚠${NC} No virtual environment found, using system Python"
        PYTHON_CMD="python3"
    fi

    echo -e "${BLUE}[INFO]${NC} API will be available at: ${GREEN}http://localhost:8000${NC}"
    echo -e "${BLUE}[INFO]${NC} API docs: ${GREEN}http://localhost:8000/docs${NC}"
    echo ""
    echo -e "${YELLOW}[TIP]${NC} Press Ctrl+C to stop the server"
    echo ""

    # Change to project directory and run
    cd "$PROJECT_ROOT"
    $PYTHON_CMD -m src.api.main
}

# If script is run directly (not sourced), execute the function
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    start_main_agent
fi

#!/bin/bash

# main_menu.sh - AI Agent Testing Main Menu
# Provides easy access to start the frontend testing interface and main agent

set -e  # Exit on error

# Color codes for better UX
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Project paths
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$PROJECT_ROOT/scripts"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
FRONTEND_ENV="$FRONTEND_DIR/.env.local"
MAIN_ENV="$PROJECT_ROOT/.env.local"

# Source the individual startup scripts
source "$SCRIPTS_DIR/start_frontend.sh"
source "$SCRIPTS_DIR/start_main_agent.sh"

# Function to print colored header
print_header() {
    echo -e "${CYAN}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║        🤖 AI Agent Testing - Main Menu                    ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Function to check dependencies
check_dependencies() {
    echo -e "${BLUE}[INFO]${NC} Checking dependencies..."

    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}[ERROR]${NC} Python 3 is not installed"
        exit 1
    fi

    # Check uv installation
    export PATH="$HOME/.local/bin:$PATH"
    if ! command -v uv &> /dev/null; then
        echo -e "${YELLOW}[WARNING]${NC} uv not found"
        echo -e "${BLUE}[INFO]${NC} Installing uv..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
    else
        echo -e "${GREEN}✓${NC} Using uv ($(uv --version | cut -d' ' -f2))"
    fi

    # Check if main project virtual environment exists, if not create it
    if [ ! -d "$PROJECT_ROOT/.venv" ]; then
        echo -e "${YELLOW}[WARNING]${NC} Main project virtual environment not found"
        echo -e "${BLUE}[INFO]${NC} Creating virtual environment..."
        cd "$PROJECT_ROOT"
        uv venv
        echo -e "${GREEN}✓${NC} Main virtual environment created"
    fi

    # Check if main dependencies are installed
    if ! "$PROJECT_ROOT/.venv/bin/python3" -c "import fastapi, uvicorn, jwt, pymongo, motor, google.generativeai" 2>/dev/null; then
        echo -e "${YELLOW}[WARNING]${NC} Required packages not found in main venv"
        echo -e "${BLUE}[INFO]${NC} Installing main dependencies with uv sync..."
        cd "$PROJECT_ROOT"
        uv sync
        echo -e "${GREEN}✓${NC} Main dependencies installed"
    else
        echo -e "${GREEN}✓${NC} Main dependencies installed"
    fi

    # Check if frontend virtual environment exists, if not create it
    if [ ! -d "$FRONTEND_DIR/.venv" ]; then
        echo -e "${YELLOW}[WARNING]${NC} Frontend virtual environment not found"
        echo -e "${BLUE}[INFO]${NC} Creating frontend virtual environment..."
        cd "$FRONTEND_DIR"
        uv venv
        echo -e "${GREEN}✓${NC} Frontend virtual environment created"
    fi

    # Check if frontend dependencies are installed
    if ! "$FRONTEND_DIR/.venv/bin/python3" -c "import fastapi, uvicorn" 2>/dev/null; then
        echo -e "${YELLOW}[WARNING]${NC} Frontend packages not found in venv"
        echo -e "${BLUE}[INFO]${NC} Installing frontend dependencies..."
        cd "$FRONTEND_DIR"
        uv pip install fastapi uvicorn python-dotenv pydantic jinja2
        echo -e "${GREEN}✓${NC} Frontend dependencies installed"
    else
        echo -e "${GREEN}✓${NC} Frontend dependencies installed"
    fi

    echo -e "${GREEN}[OK]${NC} Dependencies verified"
}

# Function to show system status
show_status() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}📊 System Status${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"

    # Python version
    PYTHON_VERSION=$(python3 --version 2>&1)
    echo -e "${GREEN}✓${NC} Python: $PYTHON_VERSION"

    # Check uv installation
    export PATH="$HOME/.local/bin:$PATH"
    if command -v uv &> /dev/null; then
        UV_VERSION=$(uv --version 2>&1 | cut -d' ' -f2)
        echo -e "${GREEN}✓${NC} uv: $UV_VERSION (fast package installer)"
    else
        echo -e "${YELLOW}⚠${NC} uv: Not installed (using pip3)"
    fi

    # Check if main config exists
    if [ -f "$MAIN_ENV" ]; then
        echo -e "${GREEN}✓${NC} Main Config: Configured"
    else
        echo -e "${RED}✗${NC} Main Config: Missing"
    fi

    # Check if frontend config exists
    if [ -f "$FRONTEND_ENV" ]; then
        echo -e "${GREEN}✓${NC} Frontend Config: Configured"
    else
        echo -e "${RED}✗${NC} Frontend Config: Missing"
    fi

    # Check if main script exists
    if [ -f "$PROJECT_ROOT/src/api/main.py" ]; then
        echo -e "${GREEN}✓${NC} Main Agent Script: Found"
    else
        echo -e "${RED}✗${NC} Main Agent Script: Missing"
    fi

    # Check if frontend script exists
    if [ -f "$FRONTEND_DIR/chatai.py" ]; then
        echo -e "${GREEN}✓${NC} Frontend Script: Found"
    else
        echo -e "${RED}✗${NC} Frontend Script: Missing"
    fi

    echo ""
}

# Function to install uv
install_uv() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}📦 Installing uv (Fast Python Package Installer)${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""

    # Check if already installed
    export PATH="$HOME/.local/bin:$PATH"
    if command -v uv &> /dev/null; then
        UV_VERSION=$(uv --version 2>&1)
        echo -e "${GREEN}✓${NC} uv is already installed: $UV_VERSION"
        echo ""
        return
    fi

    echo -e "${BLUE}[INFO]${NC} Downloading and installing uv..."
    echo -e "${BLUE}[INFO]${NC} This will install to ~/.local/bin"
    echo ""

    # Install uv
    if curl -LsSf https://astral.sh/uv/install.sh | sh; then
        echo ""
        echo -e "${GREEN}✓${NC} uv installed successfully!"
        export PATH="$HOME/.local/bin:$PATH"
        UV_VERSION=$(uv --version 2>&1)
        echo -e "${GREEN}✓${NC} Version: $UV_VERSION"
        echo ""
        echo -e "${YELLOW}[NOTE]${NC} You may need to restart your shell or run:"
        echo -e "        ${CYAN}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
    else
        echo ""
        echo -e "${RED}✗${NC} Failed to install uv"
        echo -e "${YELLOW}[INFO]${NC} Falling back to pip3 for package installation"
    fi
    echo ""
}

# Function to display help
show_help() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}📖 Help & Information${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${YELLOW}Frontend Interface:${NC}"
    echo "  - URL: http://localhost:8015"
    echo "  - Features: Token management, test submissions, CSV loader"
    echo "  - Config: frontend/.env.local"
    echo ""
    echo -e "${YELLOW}Main Agent Server:${NC}"
    echo "  - URL: http://localhost:8000"
    echo "  - API Docs: http://localhost:8000/docs"
    echo "  - Features: Orchestrator, multi-agent conversation system"
    echo "  - Config: .env.local"
    echo ""
    echo -e "${YELLOW}Configuration:${NC}"
    echo "  - Edit .env.local for main agent API credentials"
    echo "  - Edit frontend/.env.local for frontend API credentials"
    echo ""
    echo -e "${YELLOW}Quick Start:${NC}"
    echo "  1. Run: ./main_menu.sh (interactive menu)"
    echo "     OR: ./main_menu.sh --start (direct start frontend)"
    echo "     OR: ./main_menu.sh --main (direct start main agent)"
    echo "  2. Select option 1 for Frontend or option 2 for Main Agent"
    echo "  3. Frontend: http://localhost:8015 | Main Agent: http://localhost:8000"
    echo ""
    echo -e "${YELLOW}Direct Launch:${NC}"
    echo "  ./main_menu.sh --start    # Start frontend immediately"
    echo "  ./main_menu.sh -s         # Short form (frontend)"
    echo "  ./main_menu.sh 1          # Numeric option (frontend)"
    echo "  ./main_menu.sh --main     # Start main agent immediately"
    echo "  ./main_menu.sh -m         # Short form (main agent)"
    echo "  ./main_menu.sh 2          # Numeric option (main agent)"
    echo ""
    echo -e "${YELLOW}Standalone Scripts:${NC}"
    echo "  ./scripts/start_frontend.sh    # Start frontend directly"
    echo "  ./scripts/start_main_agent.sh  # Start main agent directly"
    echo ""
}

# Main menu display and selection
show_menu() {
    print_header

    echo -e "${BLUE}Available Options:${NC}"
    echo ""
    echo -e "  ${GREEN}1${NC} - Start FastAPI Chat AI Test Interface ${YELLOW}(Frontend)${NC}"
    echo -e "  ${GREEN}2${NC} - Start MGR4SMB Main Agent Server ${YELLOW}(Backend API)${NC}"
    echo -e "  ${GREEN}0${NC} - Exit"
    echo ""
    echo -ne "${CYAN}Select option [0-2]:${NC} "
}

# Main execution
main() {
    # Handle direct command-line arguments
    case "${1:-}" in
        --start|-s|1|"")
            # If run without arguments, show menu
            # If run with --start/-s/1, start frontend directly
            if [ -n "${1:-}" ]; then
                check_dependencies
                start_frontend
                exit 0
            fi
            ;;
        --main|-m|2)
            # Start main agent directly
            check_dependencies
            start_main_agent
            exit 0
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
    esac

    # Interactive menu loop
    while true; do
        show_menu
        read -r choice

        case $choice in
            1)
                check_dependencies
                start_frontend
                # When server stops, return to menu
                echo ""
                echo -e "${YELLOW}[INFO]${NC} Server stopped"
                read -p "Press Enter to continue..."
                ;;
            2)
                check_dependencies
                start_main_agent
                # When server stops, return to menu
                echo ""
                echo -e "${YELLOW}[INFO]${NC} Server stopped"
                read -p "Press Enter to continue..."
                ;;
            0)
                echo ""
                echo -e "${GREEN}Goodbye!${NC}"
                echo ""
                exit 0
                ;;
            *)
                echo ""
                echo -e "${RED}Invalid option. Please select 0, 1, or 2.${NC}"
                echo ""
                read -p "Press Enter to continue..."
                ;;
        esac

        # Clear screen for next iteration (optional)
        clear
    done
}

# Run main function
main "$@"

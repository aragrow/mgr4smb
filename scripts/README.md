# Scripts Directory

This directory contains modular startup scripts for the MGR4SMB project. Each script can be run standalone or sourced by the main menu.

## Available Scripts

### 1. `start_frontend.sh`
Starts the Frontend AI Agent Testing Interface.

**Standalone Usage:**
```bash
./scripts/start_frontend.sh
```

**Features:**
- Auto-checks and creates frontend configuration
- Uses frontend virtual environment if available
- Starts server on `http://localhost:8015`

---

### 2. `start_main_agent.sh`
Starts the MGR4SMB Main Agent Server (Backend API).

**Standalone Usage:**
```bash
./scripts/start_main_agent.sh
```

**Features:**
- Auto-checks and creates main configuration
- Uses project virtual environment
- Starts API server on `http://localhost:8000`
- API docs available at `http://localhost:8000/docs`
- Initializes orchestrator and all conversation agents

---

## Script Architecture

Each script follows this pattern:

1. **Self-contained**: Can run independently
2. **Sourceable**: Can be sourced by `main_menu.sh` for reuse
3. **Color-coded output**: Uses consistent color scheme
4. **Error handling**: Checks for required files and configurations
5. **Conditional execution**: Only runs main function when executed directly (not sourced)

### Example Pattern:
```bash
#!/bin/bash
set -e  # Exit on error

# Define variables and functions...

# Function to start service
start_service() {
    # Implementation
}

# Only execute if run directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    start_service
fi
```

---

## Adding New Scripts

To add a new startup option:

1. Create a new script in this directory: `start_<service>.sh`
2. Make it executable: `chmod +x scripts/start_<service>.sh`
3. Follow the existing pattern with:
   - Color-coded output
   - Configuration checks
   - Conditional execution
4. Source it in `main_menu.sh`:
   ```bash
   source "$SCRIPTS_DIR/start_<service>.sh"
   ```
5. Add menu option in `main_menu.sh` to call your function

---

## Color Scheme

All scripts use consistent colors:
- **RED**: Errors
- **GREEN**: Success/confirmation
- **YELLOW**: Warnings/tips
- **BLUE**: Information
- **CYAN**: Headers/sections
- **NC**: No color (reset)

---

## Dependencies

Scripts assume:
- Python 3.11+
- uv package manager (or pip3 fallback)
- Virtual environments in `.venv` directories
- Configuration files in `.env.local` or `.env.example`

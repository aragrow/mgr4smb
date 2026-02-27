"""
API Server Entry Point

Starts the FastAPI server with orchestrator integration
"""

import uvicorn
from src.api.server import create_app
from src.config.settings import get_settings


def main():
    """Start API server with orchestrator"""
    settings = get_settings()

    # Create FastAPI app (orchestrator will be initialized on startup event)
    app = create_app()

    print(f"\n🚀 Starting API server on {settings.api_host}:{settings.api_port}")
    print(f"📖 API docs: http://{settings.api_host}:{settings.api_port}/docs")
    print(f"🔒 JWT authentication enabled")
    print("🎭 Orchestrator will initialize on startup...\n")

    # Start server
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()

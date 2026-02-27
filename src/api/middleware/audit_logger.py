"""
Audit Logging Middleware

Logs all authenticated API requests including client_id, HTTP method, and path.
"""

import logging
from fastapi import Request
from datetime import datetime

# Create dedicated audit logger
logger = logging.getLogger("audit")


async def audit_log_middleware(request: Request, call_next):
    """
    Audit logging middleware

    Logs all authenticated API requests with:
    - client_id (from JWT token)
    - HTTP method (GET, POST, etc.)
    - Request path
    - Timestamp
    """
    # Only log authenticated endpoints
    if hasattr(request.state, "token_payload"):
        client_id = request.state.token_payload.get("client_id")

        logger.info(
            f"API Request | "
            f"Client: {client_id} | "
            f"Method: {request.method} | "
            f"Path: {request.url.path} | "
            f"Time: {datetime.utcnow().isoformat()}"
        )

    response = await call_next(request)
    return response

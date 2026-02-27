"""
Rate Limiting Middleware

Per-client rate limiting based on client_id from JWT token.
Default: 60 requests per minute per client.
"""

from fastapi import Request, HTTPException
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Per-client rate limiting based on client_id
    """

    def __init__(self):
        self.requests: Dict[str, List[datetime]] = defaultdict(list)

    async def check_rate_limit(
        self,
        client_id: str,
        limit_per_minute: int = 60
    ):
        """Check if client has exceeded rate limit"""
        now = datetime.utcnow()
        one_minute_ago = now - timedelta(minutes=1)

        # Clean old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if req_time > one_minute_ago
        ]

        # Check limit
        if len(self.requests[client_id]) >= limit_per_minute:
            logger.warning(
                f"Rate limit exceeded for client: {client_id} | "
                f"Limit: {limit_per_minute}/min"
            )
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {limit_per_minute} requests per minute"
            )

        # Record request
        self.requests[client_id].append(now)


# Global rate limiter instance
rate_limiter = RateLimiter()


async def rate_limit_middleware(request: Request, call_next):
    """
    Rate limiting middleware

    Only applies to authenticated endpoints (those with JWT token).
    Extracts client_id from token payload and enforces rate limits.
    """
    # Only apply to authenticated endpoints
    if hasattr(request.state, "token_payload"):
        client_id = request.state.token_payload.get("client_id")
        if client_id:
            await rate_limiter.check_rate_limit(client_id)

    response = await call_next(request)
    return response

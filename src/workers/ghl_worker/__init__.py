"""
GoHighLevel Worker - CRM integration for Email Conversation Agent

Provides GoHighLevel API integration for:
- Contact management
- Conversation retrieval
- Message synchronization
"""

from src.workers.ghl_worker.ghl_client import GoHighLevelClient

__all__ = ["GoHighLevelClient"]

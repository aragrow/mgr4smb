"""
FastAPI server for Orchestrator API

Provides REST API endpoints for external applications to communicate with orchestrator
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import FastAPI, Depends, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from src.api.auth import (
    JWTBearer,
    TokenPayload,
    ClientCredentials,
    TokenResponse,
    create_access_token,
    verify_client_credentials,
    should_renew_token,
)
from src.api.middleware.rate_limiter import rate_limit_middleware
from src.api.middleware.audit_logger import audit_log_middleware
from src.config.settings import get_settings


# Request/Response Models
class OrchestratorRequest(BaseModel):
    """Request to orchestrator"""
    action: str
    payload: Dict[str, Any]
    target_agent: Optional[str] = None  # Optional - orchestrator will auto-route if not specified


class OrchestratorResponse(BaseModel):
    """Response from orchestrator"""
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = datetime.utcnow()


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    version: str
    agents_active: int


# Global orchestrator instance (will be set on startup)
_orchestrator = None

# Health check caching (to avoid excessive checks)
_health_cache = None
_health_cache_timestamp = None
HEALTH_CACHE_TTL_SECONDS = 300  # 5 minutes


def set_orchestrator(orchestrator):
    """Set the global orchestrator instance"""
    global _orchestrator
    _orchestrator = orchestrator


def get_orchestrator():
    """Get the global orchestrator instance"""
    if _orchestrator is None:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    return _orchestrator


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application

    Returns:
        Configured FastAPI app
    """
    settings = get_settings()

    app = FastAPI(
        title="Conversation Orchestrator API",
        description="Secure API for external applications to communicate with the orchestrator",
        version="1.0.0",
    )

    # Startup event: Initialize orchestrator and agents
    @app.on_event("startup")
    async def startup_event():
        """Initialize orchestrator on application startup"""
        from src.agents import ConversationOrchestrator

        print("🎭 Initializing orchestrator...")

        # Create and start orchestrator
        orchestrator = ConversationOrchestrator()
        await orchestrator.start()

        # Set global orchestrator instance
        set_orchestrator(orchestrator)

        print("✅ Orchestrator initialized successfully (no agents registered yet)")

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins for development
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting middleware (60 requests/minute per client)
    app.middleware("http")(rate_limit_middleware)

    # Audit logging middleware (logs all authenticated requests)
    app.middleware("http")(audit_log_middleware)

    # Health check endpoint (no auth required)
    @app.get("/health", response_model=HealthResponse, tags=["Health"])
    async def health_check():
        """
        Health check endpoint (cached for 5 minutes)

        Returns service status and basic info.
        The actual health check only runs once every 5 minutes to reduce load.
        """
        global _health_cache, _health_cache_timestamp

        now = datetime.utcnow()

        # Check if cache is still valid
        if _health_cache is not None and _health_cache_timestamp is not None:
            cache_age = (now - _health_cache_timestamp).total_seconds()
            if cache_age < HEALTH_CACHE_TTL_SECONDS:
                # Return cached response
                return _health_cache

        # Cache expired or doesn't exist - perform health check
        try:
            orchestrator = get_orchestrator()
            active_agents = len(orchestrator.get_active_agents())
        except:
            active_agents = 0

        response = HealthResponse(
            status="healthy" if active_agents > 0 else "degraded",
            timestamp=now,
            version="1.0.0",
            agents_active=active_agents,
        )

        # Update cache
        _health_cache = response
        _health_cache_timestamp = now

        return response

    # Authentication endpoint
    @app.post("/auth/token", response_model=TokenResponse, tags=["Authentication"])
    async def get_token(credentials: ClientCredentials):
        """
        Obtain JWT access token

        Requires valid client_id and client_secret.
        Token expires in 24 hours.

        Args:
            credentials: Client credentials

        Returns:
            JWT access token with expiration info
        """
        # Verify credentials
        verify_client_credentials(credentials.client_id, credentials.client_secret)

        # Create access token
        token_data = create_access_token(credentials.client_id)

        return TokenResponse(**token_data)

    # Token renewal endpoint
    @app.post("/auth/refresh", response_model=TokenResponse, tags=["Authentication"])
    async def refresh_token(
        response: Response,
        token_payload: TokenPayload = Depends(JWTBearer())
    ):
        """
        Refresh JWT access token

        Requires valid (non-expired) JWT token.
        Returns new token with extended expiration.

        Args:
            token_payload: Current token payload

        Returns:
            New JWT access token
        """
        # Create new access token with same client_id
        token_data = create_access_token(token_payload.client_id)

        return TokenResponse(**token_data)

    # Send message to orchestrator
    @app.post("/orchestrator/message", response_model=OrchestratorResponse, tags=["Orchestrator"])
    async def send_message(
        request: Request,
        response: Response,
        orchestrator_request: OrchestratorRequest,
        token_payload: TokenPayload = Depends(JWTBearer())
    ):
        """
        Send message to orchestrator

        Requires valid JWT token.
        Allows external applications to send requests to the orchestrator.

        Args:
            orchestrator_request: Request details
            token_payload: Verified JWT token

        Returns:
            Response from orchestrator
        """
        from uuid import uuid4
        from src.utils.contact_extractor import ContactExtractor
        orchestrator = get_orchestrator()

        # Check if token should be renewed
        if hasattr(request.state, 'should_renew_token') and request.state.should_renew_token:
            response.headers["X-Token-Renewal-Suggested"] = "true"

        # Register external client in message bus if not already registered
        external_agent_id = f"external_{token_payload.client_id}"
        if external_agent_id not in orchestrator.message_bus.queues:
            orchestrator.message_bus.register_agent(external_agent_id)

        # Check if email or phone is provided
        from_email = orchestrator_request.payload.get("from_email", "")
        from_phone = orchestrator_request.payload.get("from_phone", "")
        body = orchestrator_request.payload.get("body", "")
        session_id = orchestrator_request.payload.get("session_id")

        # If session_id exists but no contact info in payload, check conversation state
        if session_id and not from_email and not from_phone and orchestrator._state_manager:
            try:
                # Try to get existing session from conversation state
                existing_session = await orchestrator._state_manager.get_session(session_id)
                if existing_session:
                    # Check if contact info was already provided in this session
                    # ConversationState stores contact in contact_identifier and phone_number
                    contact_identifier = existing_session.contact_identifier
                    stored_phone = existing_session.phone_number

                    # contact_identifier could be email or phone
                    if contact_identifier and "@" in contact_identifier:
                        from_email = contact_identifier
                        orchestrator_request.payload["from_email"] = contact_identifier
                        logger.info(f"✅ Retrieved email from session: {contact_identifier}")
                    elif contact_identifier and not "@" in contact_identifier:
                        from_phone = contact_identifier
                        orchestrator_request.payload["from_phone"] = contact_identifier
                        logger.info(f"✅ Retrieved phone from session: {contact_identifier}")

                    # Also check dedicated phone_number field
                    if stored_phone and not from_phone:
                        from_phone = stored_phone
                        orchestrator_request.payload["from_phone"] = stored_phone
                        logger.info(f"✅ Retrieved phone from session: {stored_phone}")
            except Exception as e:
                logger.debug(f"Could not retrieve session contact info: {e}")

        # Check if we're resuming from a "waiting_for_contact_info" state
        if session_id and not from_email and not from_phone:
            # Check in-memory cache first
            if hasattr(orchestrator, '_contact_info_cache') and session_id in orchestrator._contact_info_cache:
                checkpoint_context = orchestrator._contact_info_cache[session_id]
                # Restore contact info if it was stored in a previous message
                if checkpoint_context.get("contact_stored"):
                    cached_email = checkpoint_context.get("from_email", "")
                    cached_phone = checkpoint_context.get("from_phone", "")
                    if cached_email:
                        from_email = cached_email
                        orchestrator_request.payload["from_email"] = cached_email
                        logger.info(f"✅ Retrieved email from session cache: {cached_email}")
                    if cached_phone:
                        from_phone = cached_phone
                        orchestrator_request.payload["from_phone"] = cached_phone
                        logger.info(f"✅ Retrieved phone from session cache: {cached_phone}")
                elif checkpoint_context.get("waiting_for_contact_info"):
                    logger.info("📋 Resuming from contact info collection cache")

                    # STEP 1: Try regex-based extraction first (faster, no LLM cost)
                    contact_info = ContactExtractor.extract_contacts(body)
                    extracted_email = contact_info.get("email")
                    extracted_phone = contact_info.get("phone")

                    if extracted_email:
                        from_email = extracted_email
                        orchestrator_request.payload["from_email"] = extracted_email
                        logger.info(f"✅ Extracted email from response (regex): {extracted_email}")

                    if extracted_phone:
                        from_phone = extracted_phone
                        orchestrator_request.payload["from_phone"] = extracted_phone
                        logger.info(f"✅ Extracted phone from response (regex): {extracted_phone}")

                    # STEP 2: If regex didn't find anything, fallback to LLM extraction
                    if not extracted_email and not extracted_phone:
                        logger.info("🤖 Regex extraction failed - trying LLM extraction as fallback")

                        from src.services.llm_service import LLMService
                        llm_service = LLMService()

                        extraction_prompt = f"""Extract contact information from this message if present.

Message: {body}

Look for:
- Email address (in format xxx@xxx.xxx)
- Phone number (any format)

Return ONLY a JSON object with these fields. Use null if not found.
Example:
{{
  "email": "user@example.com",
  "phone": "+1-305-555-0100"
}}"""

                        try:
                            import json
                            extracted = await llm_service.generate_text(prompt=extraction_prompt, max_tokens=200)
                            logger.info(f"🔍 LLM extraction response (from cache): {extracted}")

                            if "{" in extracted and "}" in extracted:
                                json_start = extracted.index("{")
                                json_end = extracted.rindex("}") + 1
                                json_str = extracted[json_start:json_end]
                                contact_info_llm = json.loads(json_str)

                                extracted_email = contact_info_llm.get("email")
                                extracted_phone = contact_info_llm.get("phone")

                                if extracted_email and extracted_email.lower() != "null":
                                    from_email = extracted_email
                                    orchestrator_request.payload["from_email"] = extracted_email
                                    logger.info(f"✅ Extracted email from response (LLM): {extracted_email}")

                                if extracted_phone and extracted_phone.lower() != "null":
                                    from_phone = extracted_phone
                                    orchestrator_request.payload["from_phone"] = extracted_phone
                                    logger.info(f"✅ Extracted phone from response (LLM): {extracted_phone}")
                            else:
                                logger.warning(f"⚠️  No JSON found in LLM response (from cache)")
                        except Exception as e:
                            logger.warning(f"Could not extract contact info from response with LLM: {e}")

                    # Restore original message from cache if we got contact info
                    if from_email or from_phone:
                        original_message = checkpoint_context.get("original_message", "")
                        if original_message:
                            orchestrator_request.payload["body"] = original_message
                            body = original_message
                            logger.info(f"📋 Restored original message from cache")

                        # Log extracted contact info to conversation state
                        if orchestrator._state_manager and session_id:
                            try:
                                await orchestrator._state_manager.log_event(
                                    session_id=session_id,
                                    event_type="contact_info_extracted",
                                    data={
                                        "email": from_email,
                                        "phone": from_phone,
                                        "extraction_method": "regex" if extracted_email or extracted_phone else "llm"
                                    }
                                )
                                logger.info(f"📝 Logged extracted contact info to conversation state")
                            except Exception as e:
                                logger.warning(f"Failed to log contact info to conversation state: {e}")

                        # Clear the cache
                        del orchestrator._contact_info_cache[session_id]
                        logger.info(f"🗑️  Cleared contact info cache for session: {session_id}")
                    else:
                        logger.warning(f"⚠️  Could not extract contact info from user's response, asking again")

        # If neither email nor phone is provided, try to extract from message body
        if not from_email and not from_phone and body:
            logger.info("⚠️  No email or phone provided - attempting to extract from message body")

            # STEP 1: Try regex-based extraction first (faster, no LLM cost)
            contact_info = ContactExtractor.extract_contacts(body)
            extracted_email = contact_info.get("email")
            extracted_phone = contact_info.get("phone")

            if extracted_email:
                from_email = extracted_email
                orchestrator_request.payload["from_email"] = extracted_email
                logger.info(f"✅ Extracted email (regex): {extracted_email}")

            if extracted_phone:
                from_phone = extracted_phone
                orchestrator_request.payload["from_phone"] = extracted_phone
                logger.info(f"✅ Extracted phone (regex): {extracted_phone}")

            # STEP 2: If regex didn't find anything, fallback to LLM extraction
            if not extracted_email and not extracted_phone:
                logger.info("🤖 Regex extraction failed - trying LLM extraction as fallback")

                from src.services.llm_service import LLMService
                llm_service = LLMService()

                extraction_prompt = f"""Extract contact information from this message if present.

Message: {body}

Look for:
- Email address (in format xxx@xxx.xxx)
- Phone number (any format)

Return ONLY a JSON object with these fields. Use null if not found.
Example:
{{
  "email": "user@example.com",
  "phone": "+1-305-555-0100"
}}"""

                try:
                    import json
                    extracted = await llm_service.generate_text(prompt=extraction_prompt, max_tokens=200)
                    logger.info(f"🔍 LLM extraction response: {extracted}")

                    # Parse JSON from response
                    if "{" in extracted and "}" in extracted:
                        json_start = extracted.index("{")
                        json_end = extracted.rindex("}") + 1
                        json_str = extracted[json_start:json_end]
                        contact_info_llm = json.loads(json_str)

                        extracted_email_llm = contact_info_llm.get("email")
                        extracted_phone_llm = contact_info_llm.get("phone")

                        if extracted_email_llm and extracted_email_llm.lower() != "null":
                            from_email = extracted_email_llm
                            orchestrator_request.payload["from_email"] = extracted_email_llm
                            logger.info(f"✅ Extracted email (LLM): {extracted_email_llm}")

                        if extracted_phone_llm and extracted_phone_llm.lower() != "null":
                            from_phone = extracted_phone_llm
                            orchestrator_request.payload["from_phone"] = extracted_phone_llm
                            logger.info(f"✅ Extracted phone (LLM): {extracted_phone_llm}")
                    else:
                        logger.warning(f"⚠️  No JSON found in LLM response")
                except Exception as e:
                    logger.warning(f"Could not extract contact info from message with LLM: {e}")

            # Check GHL data and look for open conversations
            if (from_email or from_phone) and orchestrator._state_manager:
                try:
                    # Step 1: Look up contact in GHL data
                    from src.workers.ghl_worker.ghl_client import GoHighLevelClient
                    from src.workers.db_worker.mongo_client import MongoDBClient
                    from src.workers.db_worker.conversation_state_repo import ConversationStateRepository

                    ghl = GoHighLevelClient()
                    ghl_contact = None

                    # Search GHL by email first, then phone
                    if from_email:
                        logger.info(f"🔍 Searching GHL data for email: {from_email}")
                        ghl_contact = ghl.csv_find_contact_by_email(from_email)

                    if not ghl_contact and from_phone:
                        logger.info(f"🔍 Searching GHL data for phone: {from_phone}")
                        ghl_contact = ghl.csv_find_contact_by_phone(from_phone)

                    # If found in GHL, log it and use GHL contact data
                    contact_identifiers = []
                    if ghl_contact:
                        logger.info(f"✅ Found contact in GHL: {ghl_contact.get('name', 'Unknown')}")
                        logger.info(f"   GHL Email: {ghl_contact.get('email', 'N/A')}")
                        logger.info(f"   GHL Phone: {ghl_contact.get('phone', 'N/A')}")

                        # Use both email and phone from GHL for conversation search
                        if ghl_contact.get('email'):
                            contact_identifiers.append(ghl_contact['email'])
                        if ghl_contact.get('phone'):
                            contact_identifiers.append(ghl_contact['phone'])
                    else:
                        logger.info(f"📋 Contact not found in GHL data")
                        # Use extracted contact info
                        if from_email:
                            contact_identifiers.append(from_email)
                        if from_phone:
                            contact_identifiers.append(from_phone)

                    # Step 2: Search for open conversations using contact identifiers
                    db = MongoDBClient.get_database()
                    conv_repo = ConversationStateRepository(db)

                    open_conversations = []
                    for contact_id in contact_identifiers:
                        all_conversations = await conv_repo.find_by_contact(
                            contact_identifier=contact_id,
                            limit=10
                        )
                        # Filter for in_progress status
                        open_convs = [c for c in all_conversations if c.status == "in_progress"]
                        open_conversations.extend(open_convs)

                    # Remove duplicates (same session_id)
                    seen_sessions = set()
                    unique_open_conversations = []
                    for conv in open_conversations:
                        if conv.session_id not in seen_sessions:
                            seen_sessions.add(conv.session_id)
                            unique_open_conversations.append(conv)

                    if unique_open_conversations:
                        # Found open conversation(s) - use the most recent one
                        latest_conv = sorted(unique_open_conversations, key=lambda c: c.updated_at, reverse=True)[0]
                        old_session_id = session_id
                        session_id = latest_conv.session_id
                        orchestrator_request.payload["session_id"] = session_id

                        contact_identifier = contact_identifiers[0] if contact_identifiers else "Unknown"
                        logger.info(f"🔄 Found open conversation for {contact_identifier}")
                        logger.info(f"   Resuming session: {session_id} (previous: {old_session_id})")

                        # Log resumption event with GHL data if available
                        resume_data = {
                            "previous_session_id": old_session_id,
                            "contact_identifier": contact_identifier,
                            "reason": "open_conversation_found",
                            "found_in_ghl": ghl_contact is not None
                        }
                        if ghl_contact:
                            resume_data["ghl_contact"] = {
                                "name": ghl_contact.get("name"),
                                "email": ghl_contact.get("email"),
                                "phone": ghl_contact.get("phone"),
                                "ghl_id": ghl_contact.get("id")
                            }

                        await orchestrator._state_manager.log_event(
                            session_id=session_id,
                            event_type="conversation_resumed",
                            data=resume_data
                        )
                    else:
                        contact_identifier = contact_identifiers[0] if contact_identifiers else "Unknown"
                        logger.info(f"📝 No open conversations found for {contact_identifier} - continuing with current session")

                except Exception as e:
                    logger.warning(f"Could not check GHL data or open conversations: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())

            # Log extracted contact info to conversation state if we have a session_id
            if (from_email or from_phone) and session_id and orchestrator._state_manager:
                try:
                    await orchestrator._state_manager.log_event(
                        session_id=session_id,
                        event_type="contact_info_extracted",
                        data={
                            "email": from_email,
                            "phone": from_phone,
                            "extraction_method": "regex" if extracted_email or extracted_phone else "llm",
                            "source": "message_body"
                        }
                    )
                    logger.info(f"📝 Logged extracted contact info to conversation state")
                except Exception as e:
                    logger.warning(f"Failed to log contact info to conversation state: {e}")

            # Cache contact info for subsequent requests in the same session
            if (from_email or from_phone) and session_id:
                if not hasattr(orchestrator, '_contact_info_cache'):
                    orchestrator._contact_info_cache = {}
                cache_entry = orchestrator._contact_info_cache.get(session_id, {})
                if not cache_entry.get("waiting_for_contact_info"):
                    orchestrator._contact_info_cache[session_id] = {
                        "from_email": from_email or "",
                        "from_phone": from_phone or "",
                        "contact_stored": True
                    }
                    logger.info(f"💾 Cached contact info for session: {session_id}")

        # If still no email or phone, ask for it
        if not from_email and not from_phone:
            logger.info("⚠️  No email or phone provided and couldn't extract - asking user for contact information")

            # Generate session_id if not provided
            if not session_id:
                session_id = f"session_{uuid4().hex[:16]}"
                logger.info(f"🆔 Generated new session_id for contact collection: {session_id}")

            # Store the original message in the payload for next turn
            # Use a simple dict to cache this temporarily
            if not hasattr(orchestrator, '_contact_info_cache'):
                orchestrator._contact_info_cache = {}

            orchestrator._contact_info_cache[session_id] = {
                "waiting_for_contact_info": True,
                "original_message": body
            }
            logger.info(f"💾 Cached original message for session: {session_id}")

            return OrchestratorResponse(
                status="needs_contact_info",
                message="To assist you better, I'll need your contact information. Could you please provide your email address or phone number?\n\nThis information is only used to keep track of our conversation and provide you with personalized assistance. We respect your privacy and won't share your information with anyone.",
                data={"session_id": session_id}
            )

        # Auto-detect customer_type if not provided
        customer_type = orchestrator_request.payload.get("customer_type", "").lower()
        if not customer_type:
            # Query GHL Worker to find contact
            from src.workers.ghl_worker.ghl_client import GoHighLevelClient
            ghl = GoHighLevelClient()

            contact = None
            if from_email:
                contact = ghl.csv_find_contact_by_email(from_email)
            elif from_phone:
                contact = ghl.csv_find_contact_by_phone(from_phone)

            if contact:
                # Contact exists - determine type based on classification
                classification = contact.get("classification", "").lower()

                if classification == "vendor":
                    customer_type = "vendor"
                elif classification == "prospect":
                    customer_type = "prospect"
                elif classification == "client":
                    customer_type = "contact"
                elif classification == "lead":
                    # Check if they have quotes or properties
                    properties = ghl.csv_find_properties_by_email(from_email) if from_email else []
                    quotes = ghl.csv_find_quotes_by_email(from_email) if from_email else []

                    if properties or quotes:
                        customer_type = "contact"  # Has property/quote → client
                    else:
                        customer_type = "prospect"  # Lead without property/quote
                else:
                    customer_type = "prospect"  # Unknown classification → treat as prospect
            else:
                # Contact not found → treat as new lead
                customer_type = "lead"

            # Update payload with detected customer_type
            orchestrator_request.payload["customer_type"] = customer_type
            logger.info(f"📊 Auto-detected customer_type: {customer_type} for {from_email or from_phone}")

        # Determine target agent based on customer_type if not explicitly specified
        # NOTE: For now, we only have orchestrator - no individual agents registered
        target_agent = orchestrator_request.target_agent
        if not target_agent:
            # Always use orchestrator since no other agents are registered
            target_agent = "orchestrator"
            logger.info(f"📍 Routing to orchestrator (customer_type: {customer_type})")

        # Save payload session_id before routing resets it (used for cache-based history)
        payload_session_id = session_id

        # Enable conversation tracking for process_message actions
        session_id = None
        if orchestrator_request.action == "process_message":
            source = orchestrator_request.payload.get("source", "").lower()
            from_email = orchestrator_request.payload.get("from_email", "")
            from_phone = orchestrator_request.payload.get("from_phone", "")
            body = orchestrator_request.payload.get("body", "")
            contact_name = orchestrator_request.payload.get("contact_name")
            customer_type = orchestrator_request.payload.get("customer_type", "").lower()

            # Map customer_type to classification
            classification = None
            if customer_type == "prospect":
                classification = "prospect"  # Contact without job/quote
            elif customer_type == "contact":
                classification = "client"
            elif customer_type == "vendor":
                classification = "vendor"
            # "lead" maps to None classification

            # Determine sender_status based on customer_type
            sender_status = "NOT_FOUND" if customer_type == "lead" else "FOUND"

            # Route through proper channels to enable conversation tracking
            if source == "email" and from_email:
                # Generate email_id and thread_id if not provided
                email_id = orchestrator_request.payload.get("email_id") or f"test-email-{uuid.uuid4().hex[:16]}"
                thread_id = orchestrator_request.payload.get("thread_id") or f"test-thread-{uuid.uuid4().hex[:16]}"

                routing_decision = await orchestrator.route_email(
                    from_email=from_email,
                    to_email="info@example.com",  # Default recipient
                    subject=orchestrator_request.payload.get("subject", "Test message"),
                    body=body,
                    sender_status=sender_status,
                    classification=classification,
                    email_id=email_id,
                    thread_id=thread_id,
                    contact_name=contact_name,
                    phone_number=from_phone if from_phone else None,  # Include phone number
                    enable_tracking=True
                )

                if routing_decision:
                    session_id = routing_decision.get("session_id")

            elif source == "phone" and from_phone:
                # Generate call_id if not provided
                call_id = orchestrator_request.payload.get("call_id") or f"test-call-{uuid.uuid4().hex[:16]}"

                routing_decision = await orchestrator.route_call(
                    phone_number=from_phone,
                    caller_name=contact_name,
                    call_id=call_id,
                    call_direction="inbound",
                    initial_message=body,
                    sender_status=sender_status,
                    classification=classification,
                    enable_tracking=True
                )

                if routing_decision:
                    session_id = routing_decision.get("session_id")

        # ORCHESTRATOR-ONLY MODE: No individual agents registered
        # Use LLM to generate response based on user's message
        logger.info(f"✅ Message processed in orchestrator-only mode")

        # Check if this is just contact info (no actual question)
        # If the message is ONLY contact info, acknowledge it
        is_only_contact_info = False
        llm_prompt_sent = None
        if body:
            # Check if body contains ONLY email or phone (no other text)
            body_stripped = body.strip()
            contact_check = ContactExtractor.extract_contacts(body_stripped)
            if contact_check.get("email") or contact_check.get("phone"):
                # Check if body is essentially just the contact info
                # Remove the contact info and see if anything meaningful remains
                temp_body = body_stripped
                if contact_check.get("email"):
                    temp_body = temp_body.replace(contact_check["email"], "")
                if contact_check.get("phone"):
                    # Remove various phone formats
                    import re
                    temp_body = re.sub(r'[\d\-\(\)\.\+\s]+', '', temp_body)

                # If nothing meaningful remains, it's just contact info
                remaining = temp_body.strip().strip(".,;:-")
                if len(remaining) < 5:  # Just punctuation or very short
                    is_only_contact_info = True

        if is_only_contact_info:
            # Just acknowledge the contact info
            confirmation_parts = []
            if from_email:
                confirmation_parts.append(f"Email: {from_email}")
            if from_phone:
                confirmation_parts.append(f"Phone: {from_phone}")

            confirmation_message = "Thank you! I've recorded your contact information:\n\n" + "\n".join(confirmation_parts) + "\n\nHow can I help you today?"
        else:
            # User asked a question - use LLM to respond
            from src.services.llm_service import LLMService
            llm_service = LLMService()

            # Build conversation history and GHL data from session if available
            conversation_history = ""
            ghl_contact_info = None
            if session_id and orchestrator._state_manager:
                try:
                    existing_session = await orchestrator._state_manager.get_session(session_id)
                    if existing_session and existing_session.events:
                        # Build conversation summary from events
                        history_lines = []
                        for event in existing_session.events[-10:]:  # Last 10 events
                            event_type = event.event_type
                            event_data = event.data if hasattr(event, 'data') else {}

                            # Format different event types
                            if event_type == "contact_info_extracted":
                                email = event_data.get("email", "")
                                phone = event_data.get("phone", "")
                                if email:
                                    history_lines.append(f"- User provided email: {email}")
                                if phone:
                                    history_lines.append(f"- User provided phone: {phone}")
                            elif event_type == "conversation_resumed":
                                # Check if we have GHL contact data from resumption
                                if event_data.get("found_in_ghl") and event_data.get("ghl_contact"):
                                    ghl_contact_info = event_data["ghl_contact"]
                                    logger.info(f"📋 Retrieved GHL contact info from conversation history")
                            elif event_type in ["email_received", "call_received"]:
                                user_message = event_data.get("body", "")
                                if user_message:
                                    history_lines.append(f"- User: {user_message}")
                            elif event_type == "agent_response":
                                agent_message = event_data.get("message", "")
                                if agent_message:
                                    history_lines.append(f"- Agent: {agent_message}")

                        if history_lines:
                            conversation_history = "\n".join(history_lines)
                            logger.info(f"📜 Retrieved {len(history_lines)} events from conversation history")
                except Exception as e:
                    logger.debug(f"Could not retrieve conversation history: {e}")

            # Fetch knowledge base context for this query
            knowledge_context = ""
            try:
                from src.workers.knowledge_worker.knowledge_enrichment import KnowledgeEnrichment
                enrichment = KnowledgeEnrichment()
                enrichment_data = await enrichment.enrich_for_orchestrator("", body)
                knowledge_context = enrichment.format_enrichment(enrichment_data)
                logger.info(f"📚 Knowledge enrichment retrieved ({len(knowledge_context)} chars)")
            except Exception as e:
                logger.warning(f"Could not retrieve knowledge context: {e}")

            # Build conversation context with history and GHL data
            conversation_context = f"""You are a helpful customer service agent for a small business.

Customer Information:
- Email: {from_email if from_email else "Not provided"}
- Phone: {from_phone if from_phone else "Not provided"}
- Customer Type: {customer_type}"""

            # Add GHL contact information if available
            if ghl_contact_info:
                conversation_context += f"""
- Name: {ghl_contact_info.get('name', 'Not available')}
- GHL Contact ID: {ghl_contact_info.get('ghl_id', 'Not available')}
- Status: Found in customer database"""

            # Inject knowledge base context
            if knowledge_context:
                conversation_context += f"""

{knowledge_context}"""

            if conversation_history:
                conversation_context += f"""

Previous Conversation:
{conversation_history}"""

            conversation_context += f"""

Current Customer Message: {body}

Answer the customer's question directly and completely using the company and service information above. Be helpful, professional, and concise. Do not repeat the customer's contact information back to them."""

            llm_prompt_sent = conversation_context

            try:
                llm_response = await llm_service.generate_text(
                    prompt=conversation_context,
                    temperature=0.7,
                    max_tokens=get_settings().llm_max_response_tokens
                )
                confirmation_message = llm_response
                logger.info(f"🤖 Generated LLM response for user question")

                # Log the agent response to conversation state
                if session_id and orchestrator._state_manager:
                    try:
                        await orchestrator._state_manager.log_event(
                            session_id=session_id,
                            event_type="agent_response",
                            agent_name="orchestrator",
                            data={
                                "message": llm_response,
                                "user_message": body
                            }
                        )
                    except Exception as e:
                        logger.debug(f"Could not log agent response: {e}")

            except Exception as e:
                logger.error(f"Failed to generate LLM response: {e}", exc_info=True)
                confirmation_message = f"[LLM ERROR: {e}]"

        response_data = {
            "customer_type": customer_type,
            "acknowledged": True,
        }

        # Add extracted contact info to response
        if from_email:
            response_data["email"] = from_email
        if from_phone:
            response_data["phone"] = from_phone

        # Add session_id to response if tracking was enabled
        if session_id:
            response_data["session_id"] = session_id

        # Include the LLM prompt for frontend display
        if llm_prompt_sent:
            response_data["llm_prompt"] = llm_prompt_sent

        return OrchestratorResponse(
            status="success",
            message=confirmation_message,
            data=response_data
        )

    # Get orchestrator status
    @app.get("/orchestrator/status", response_model=Dict[str, Any], tags=["Orchestrator"])
    async def get_status(
        token_payload: TokenPayload = Depends(JWTBearer())
    ):
        """
        Get orchestrator status

        Returns information about active agents and system status.

        Args:
            token_payload: Verified JWT token

        Returns:
            Orchestrator status information
        """
        orchestrator = get_orchestrator()
        active_agents = orchestrator.get_active_agents()

        return {
            "status": "active",
            "timestamp": datetime.utcnow(),
            "agents": [
                {
                    "name": agent.name,
                    "type": agent.agent_type,
                    "status": agent.status,
                    "capabilities": agent.capabilities,
                    "last_seen": agent.last_seen,
                }
                for agent in active_agents
            ],
            "total_agents": len(active_agents),
        }

    # List available agents
    @app.get("/orchestrator/agents", response_model=Dict[str, Any], tags=["Orchestrator"])
    async def list_agents(
        token_payload: TokenPayload = Depends(JWTBearer())
    ):
        """
        List all available agents

        Returns list of registered agents with their capabilities.

        Args:
            token_payload: Verified JWT token

        Returns:
            List of agents
        """
        orchestrator = get_orchestrator()
        active_agents = orchestrator.get_active_agents()

        return {
            "agents": [
                {
                    "name": agent.name,
                    "type": agent.agent_type,
                    "capabilities": agent.capabilities,
                    "status": agent.status,
                }
                for agent in active_agents
            ]
        }

    return app


# Create app instance for uvicorn
app = create_app()

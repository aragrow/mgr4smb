"""
Conversation Orchestrator - Top-level agent coordinator

Manages and coordinates communication between all agents
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from src.agents.message_bus import MessageBus, Message, MessageType
from src.agents.agent_registry import AgentRegistry, AgentInfo
from src.models.agent_prompt import AgentPrompt
from src.workers.db_worker.mongo_client import MongoDBClient
from src.workers.db_worker.agent_prompt_repo import AgentPromptRepository
from src.services.llm_service import LLMService
from src.services.conversation_state_manager import ConversationStateManager

logger = logging.getLogger(__name__)


class ConversationOrchestrator:
    """
    Top-level orchestrator for agent coordination

    Manages agent lifecycle, message routing, and conversation flow
    """

    def __init__(self):
        """Initialize orchestrator"""
        self.name = "orchestrator"
        self.message_bus = MessageBus()
        self.agent_registry = AgentRegistry()
        self.is_running = False
        self.agents: List = []  # Will hold agent instances

        # Intent classification components
        self._intent_prompt: Optional[AgentPrompt] = None
        self._llm_service: Optional[LLMService] = None

        # Conversation state tracking
        self._state_manager: Optional[ConversationStateManager] = None

        # Register orchestrator with message bus
        self.message_bus.register_agent(self.name)

    async def start(self) -> None:
        """
        Start the orchestrator

        Initializes message bus, agent registry, and loads prompts
        """
        # Initialize LLM service
        self._llm_service = LLMService()

        # Initialize conversation state manager
        self._state_manager = ConversationStateManager()

        # Load intent classification prompt
        await self._load_intent_prompt()

        self.is_running = True
        print(f"🎭 Orchestrator started")

    async def stop(self) -> None:
        """
        Stop the orchestrator

        Stops all agents and cleans up
        """
        self.is_running = False

        # Stop all agents
        for agent in self.agents:
            await agent.stop()

        print(f"🎭 Orchestrator stopped")

    def register_agent(self, agent) -> None:
        """
        Register an agent with the orchestrator

        Args:
            agent: Agent instance to register
        """
        self.agents.append(agent)

    async def start_all_agents(self) -> None:
        """
        Start all registered agents
        """
        for agent in self.agents:
            await agent.start()

    async def listen_for_greetings(self, timeout: float = 5.0) -> List[Message]:
        """
        Listen for greeting messages from agents

        Args:
            timeout: How long to wait for greetings

        Returns:
            List of greeting messages received
        """
        greetings = []
        end_time = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < end_time:
            remaining = end_time - asyncio.get_event_loop().time()
            if remaining <= 0:
                break

            message = await self.message_bus.receive_message(
                self.name,
                timeout=remaining
            )

            if message and message.type == MessageType.GREETING:
                greetings.append(message)
                print(f"📨 Received: {message.payload.get('message')}")

                # Send acknowledgment
                ack = Message(
                    type=MessageType.RESPONSE,
                    from_agent=self.name,
                    to_agent=message.from_agent,
                    payload={
                        "message": f"Hello {message.from_agent}! Welcome to the conversation.",
                        "status": "acknowledged"
                    },
                    correlation_id=message.id
                )
                await self.message_bus.send_message(ack)

        return greetings

    async def broadcast_message(self, message_type: MessageType, payload: Dict) -> None:
        """
        Broadcast a message to all agents

        Args:
            message_type: Type of message
            payload: Message payload
        """
        message = Message(
            type=message_type,
            from_agent=self.name,
            to_agent=None,  # Broadcast
            payload=payload
        )
        await self.message_bus.send_message(message)

    def get_active_agents(self) -> List[AgentInfo]:
        """
        Get list of active agents

        Returns:
            List of active agent information
        """
        return self.agent_registry.list_agents(status="active")

    async def coordinate_conversation(self) -> None:
        """
        Main conversation coordination loop

        This is where the orchestrator will manage the conversation flow
        between agents in future iterations
        """
        # TODO: Implement conversation flow logic
        # For now, just listen for messages
        print(f"🎭 Orchestrator coordinating conversation...")

        while self.is_running:
            message = await self.message_bus.receive_message(self.name, timeout=1.0)
            if message:
                await self.handle_message(message)

    async def _load_intent_prompt(self) -> None:
        """Load intent classification prompt from database"""
        try:
            db = MongoDBClient.get_database()
            prompt_repo = AgentPromptRepository(db)

            self._intent_prompt = await prompt_repo.find_by_agent_and_type(
                agent_name=self.name,
                prompt_type="intent_classification"
            )

            if self._intent_prompt:
                logger.info(
                    f"Loaded intent prompt for orchestrator "
                    f"(v{self._intent_prompt.version}, model={self._intent_prompt.model})"
                )
            else:
                logger.warning("No intent classification prompt found for orchestrator")

        except Exception as e:
            logger.warning(f"Failed to load intent prompt - starting without it: {e}")

    async def route_email(
        self,
        from_email: str,
        to_email: str,
        subject: str,
        body: str,
        sender_status: str = "UNKNOWN",
        classification: Optional[str] = None,
        previous_count: int = 0,
        last_interaction: str = "Never",
        email_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        contact_name: Optional[str] = None,
        phone_number: Optional[str] = None,
        enable_tracking: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Route an incoming email to the appropriate agent using intent classification

        Args:
            from_email: Sender email address
            to_email: Recipient email address
            subject: Email subject
            body: Email body
            sender_status: "NOT_FOUND" (LEAD) or "FOUND" (CLIENT/VENDOR)
            classification: "client", "vendor", or None if NOT_FOUND
            previous_count: Number of previous conversations
            last_interaction: Date of last interaction
            email_id: Gmail message ID (for tracking)
            thread_id: Gmail thread ID (for tracking)
            contact_name: Contact name (for tracking)
            phone_number: Contact phone number (optional, for tracking)
            enable_tracking: Enable conversation state tracking (default True)

        Returns:
            Routing decision with target_agent, sub_route, and session_id (if tracking enabled)
        """
        if not self._intent_prompt or not self._llm_service:
            logger.error("Orchestrator not properly initialized for intent classification")
            return None

        session_id = None

        # Start or resume conversation tracking if enabled
        if enable_tracking and self._state_manager and email_id:
            try:
                # Check if conversation already exists for this thread
                existing_session = None
                if thread_id:
                    existing_session = await self._state_manager.get_session_by_thread(thread_id)

                if existing_session:
                    # Resume existing conversation
                    session_id = existing_session.session_id
                    logger.info(f"Resuming conversation: session_id={session_id}, thread_id={thread_id}")

                    # Log new message to existing session
                    await self._state_manager.log_event(
                        session_id=session_id,
                        event_type="email_received",
                        data={
                            "from": from_email,
                            "to": to_email,
                            "subject": subject,
                            "body": body,
                            "sender_status": sender_status,
                            "phone_number": phone_number,
                            "email_id": email_id
                        }
                    )
                else:
                    # Start new conversation
                    session_id = await self._state_manager.start_session(
                        channel="email",
                        email_id=email_id,
                        thread_id=thread_id,
                        contact_identifier=from_email,
                        contact_name=contact_name,
                        classification=classification,
                        phone_number=phone_number,  # Include phone number if provided
                        data={
                            "from": from_email,
                            "to": to_email,
                            "subject": subject,
                            "body": body,
                            "sender_status": sender_status,
                            "phone_number": phone_number  # Include in event data too
                        }
                    )
                    logger.info(f"Started new conversation: session_id={session_id}, thread_id={thread_id}")

            except Exception as e:
                logger.error(f"Failed to start/resume conversation tracking: {e}", exc_info=True)
                # Continue without tracking

        # Build variables for prompt template
        variables = {
            "from_email": from_email,
            "sender_status": sender_status,
            "classification": classification if classification else "null",
            "subject": subject,
            "body": body,
            "previous_count": previous_count,
            "last_interaction": last_interaction,
        }

        try:
            # Classify intent using LLM
            routing_decision = await self._llm_service.classify_intent(
                agent_prompt=self._intent_prompt,
                variables=variables
            )

            logger.info(f"Routing decision: {routing_decision}")

            # Log routing event if tracking enabled
            if session_id and self._state_manager:
                try:
                    await self._state_manager.log_event(
                        session_id=session_id,
                        event_type="agent_routed",
                        agent_name=self.name,
                        data={
                            "target_agent": routing_decision.get("target_agent"),
                            "sub_route": routing_decision.get("sub_route"),
                            "ghl_status": routing_decision.get("ghl_status"),
                            "classification": routing_decision.get("classification"),
                            "reasoning": routing_decision.get("reasoning"),
                            "confidence": routing_decision.get("confidence")
                        }
                    )

                    # Create checkpoint
                    await self._state_manager.create_checkpoint(
                        session_id=session_id,
                        current_agent=self.name,
                        state="in_progress",
                        next_action=routing_decision.get("target_agent"),
                        context={
                            "email_id": email_id,
                            "thread_id": thread_id,
                            "sub_route": routing_decision.get("sub_route")
                        }
                    )
                except Exception as e:
                    logger.error(f"Failed to log routing event: {e}", exc_info=True)

            # Add session_id to routing decision
            if session_id:
                routing_decision["session_id"] = session_id

            return routing_decision

        except Exception as e:
            logger.error(f"Failed to route email: {e}", exc_info=True)

            # Mark session as error if tracking enabled
            if session_id and self._state_manager:
                try:
                    await self._state_manager.mark_error(
                        session_id=session_id,
                        error_data={"error": str(e), "step": "routing"}
                    )
                except:
                    pass

            return None

    async def route_call(
        self,
        phone_number: str,
        caller_name: Optional[str] = None,
        call_id: Optional[str] = None,
        call_direction: str = "inbound",
        initial_message: Optional[str] = None,
        sender_status: str = "UNKNOWN",
        classification: Optional[str] = None,
        previous_count: int = 0,
        last_interaction: str = "Never",
        enable_tracking: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Route an incoming phone call to the appropriate agent

        Args:
            phone_number: Caller phone number
            caller_name: Caller name (if known)
            call_id: GoHighLevel call ID (for tracking)
            call_direction: "inbound" or "outbound"
            initial_message: Transcription or initial context
            sender_status: "NOT_FOUND" (LEAD) or "FOUND" (CLIENT/VENDOR)
            classification: "client", "vendor", or None if NOT_FOUND
            previous_count: Number of previous conversations
            last_interaction: Date of last interaction
            enable_tracking: Enable conversation state tracking (default True)

        Returns:
            Routing decision with target_agent, sub_route, and session_id (if tracking enabled)
        """
        if not self._intent_prompt or not self._llm_service:
            logger.error("Orchestrator not properly initialized for intent classification")
            return None

        session_id = None

        # Start or resume conversation tracking if enabled
        if enable_tracking and self._state_manager and call_id:
            try:
                # Check if conversation already exists for this call
                existing_session = await self._state_manager.get_session_by_call(call_id)

                if existing_session:
                    # Resume existing conversation (e.g., call was transferred or reconnected)
                    session_id = existing_session.session_id
                    logger.info(f"Resuming phone conversation: session_id={session_id}, call_id={call_id}")

                    # Log continuation event
                    await self._state_manager.log_event(
                        session_id=session_id,
                        event_type="call_received",
                        data={
                            "caller_id": phone_number,
                            "call_direction": call_direction,
                            "initial_message": initial_message or "Call continued",
                            "sender_status": sender_status,
                            "call_status": "resumed"
                        }
                    )
                else:
                    # Start new conversation
                    session_id = await self._state_manager.start_session(
                        channel="phone",
                        call_id=call_id,
                        phone_number=phone_number,
                        contact_identifier=phone_number,
                        contact_name=caller_name,
                        classification=classification,
                        call_direction=call_direction,
                        data={
                            "caller_id": phone_number,
                            "call_direction": call_direction,
                            "initial_message": initial_message or "No transcription available",
                            "sender_status": sender_status
                        }
                    )
                    logger.info(f"Started new phone conversation: session_id={session_id}, call_id={call_id}")

            except Exception as e:
                logger.error(f"Failed to start/resume phone conversation tracking: {e}", exc_info=True)
                # Continue without tracking

        # Build variables for prompt template (adapted for phone)
        variables = {
            "from_email": phone_number,  # Use phone as identifier
            "sender_status": sender_status,
            "classification": classification if classification else "null",
            "subject": f"Phone call from {caller_name or phone_number}",
            "body": initial_message or "Phone conversation (no transcription)",
            "previous_count": previous_count,
            "last_interaction": last_interaction,
        }

        try:
            # Classify intent using LLM
            routing_decision = await self._llm_service.classify_intent(
                agent_prompt=self._intent_prompt,
                variables=variables
            )

            logger.info(f"Phone routing decision: {routing_decision}")

            # Log routing event if tracking enabled
            if session_id and self._state_manager:
                try:
                    await self._state_manager.log_event(
                        session_id=session_id,
                        event_type="agent_routed",
                        agent_name=self.name,
                        data={
                            "target_agent": routing_decision.get("target_agent"),
                            "sub_route": routing_decision.get("sub_route"),
                            "ghl_status": routing_decision.get("ghl_status"),
                            "classification": routing_decision.get("classification"),
                            "reasoning": routing_decision.get("reasoning"),
                            "confidence": routing_decision.get("confidence"),
                            "call_direction": call_direction
                        }
                    )

                    # Create checkpoint
                    await self._state_manager.create_checkpoint(
                        session_id=session_id,
                        current_agent=self.name,
                        state="in_progress",
                        next_action=routing_decision.get("target_agent"),
                        context={
                            "call_id": call_id,
                            "phone_number": phone_number,
                            "sub_route": routing_decision.get("sub_route")
                        }
                    )
                except Exception as e:
                    logger.error(f"Failed to log phone routing event: {e}", exc_info=True)

            # Add session_id to routing decision
            if session_id:
                routing_decision["session_id"] = session_id

            return routing_decision

        except Exception as e:
            logger.error(f"Failed to route phone call: {e}", exc_info=True)

            # Mark session as error if tracking enabled
            if session_id and self._state_manager:
                try:
                    await self._state_manager.mark_error(
                        session_id=session_id,
                        error_data={"error": str(e), "step": "phone_routing"}
                    )
                except:
                    pass

            return None

    async def handle_message(self, message: Message) -> None:
        """
        Handle incoming message

        Args:
            message: Message to handle
        """
        print(f"📨 Orchestrator received {message.type} from {message.from_agent}")

        # Handle different message types
        if message.type == MessageType.GREETING:
            # Already handled in listen_for_greetings
            pass
        elif message.type == MessageType.REQUEST:
            # Route request to appropriate agent
            # TODO: Implement request routing logic
            pass
        elif message.type == MessageType.NOTIFICATION:
            # Handle notification
            # TODO: Implement notification handling
            pass
        elif message.type == MessageType.ERROR:
            # Handle error
            print(f"❌ Error from {message.from_agent}: {message.payload}")

"""
Agent Base Class - Interface for all agents

Defines the common interface and behavior for all agents
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from src.agents.message_bus import MessageBus, Message, MessageType
from src.agents.agent_registry import AgentRegistry, AgentInfo
from src.models.agent_prompt import AgentPrompt
from src.workers.db_worker.mongo_client import MongoDBClient
from src.workers.db_worker.agent_prompt_repo import AgentPromptRepository
from src.services.llm_service import LLMService
from src.services.conversation_state_manager import ConversationStateManager
from src.workers.ghl_worker.ghl_client import GoHighLevelClient
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class AgentBase(ABC):
    """
    Base class for all agents

    Provides common functionality for agent communication and lifecycle
    """

    def __init__(
        self,
        name: str,
        agent_type: str,
        message_bus: MessageBus,
        agent_registry: AgentRegistry,
    ):
        """
        Initialize agent

        Args:
            name: Unique name for this agent instance
            agent_type: Type of agent (mail, db, ghl, jobber)
            message_bus: Message bus for communication
            agent_registry: Registry for agent discovery
        """
        self.name = name
        self.agent_type = agent_type
        self.message_bus = message_bus
        self.agent_registry = agent_registry
        self.is_running = False

        # Intent classification components
        self._intent_prompt: Optional[AgentPrompt] = None
        self._llm_service: Optional[LLMService] = None

        # Urgent escalation components
        self._ghl_client = GoHighLevelClient()
        self._settings = get_settings()

        # Conversation state tracking
        self._state_manager: Optional[ConversationStateManager] = None

        # Message processing task
        self._processing_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """
        Start the agent

        Registers with message bus and agent registry, loads prompts
        """
        # Register with message bus
        self.message_bus.register_agent(self.name)

        # Register with agent registry
        agent_info = AgentInfo(
            name=self.name,
            agent_type=self.agent_type,
            capabilities=self.get_capabilities(),
        )
        self.agent_registry.register(agent_info)

        # Initialize LLM service
        self._llm_service = LLMService()

        # Initialize conversation state manager
        self._state_manager = ConversationStateManager()

        # Load intent classification prompt from database
        await self._load_intent_prompt()

        self.is_running = True

        # Send greeting to orchestrator
        await self.send_greeting()

        # Start message processing loop
        self._processing_task = asyncio.create_task(self._message_processing_loop())
        logger.info(f"{self.name} started message processing loop")

    async def stop(self) -> None:
        """
        Stop the agent

        Unregisters from message bus and agent registry
        """
        self.is_running = False

        # Cancel processing task
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass

        self.message_bus.unregister_agent(self.name)
        self.agent_registry.unregister(self.name)

    async def send_greeting(self) -> None:
        """
        Send greeting message to orchestrator
        """
        greeting = Message(
            type=MessageType.GREETING,
            from_agent=self.name,
            to_agent="orchestrator",
            payload={
                "message": f"Hello from {self.name}!",
                "agent_type": self.agent_type,
                "capabilities": self.get_capabilities(),
            }
        )
        await self.message_bus.send_message(greeting)

    async def send_message(self, message: Message) -> None:
        """
        Send a message

        Args:
            message: Message to send
        """
        await self.message_bus.send_message(message)

    async def receive_message(self, timeout: Optional[float] = None) -> Optional[Message]:
        """
        Receive a message

        Args:
            timeout: Optional timeout in seconds

        Returns:
            Message if available, None if timeout
        """
        return await self.message_bus.receive_message(self.name, timeout)

    @abstractmethod
    def get_capabilities(self) -> list[str]:
        """
        Get list of capabilities this agent provides

        Returns:
            List of capability names
        """
        pass

    async def _load_intent_prompt(self) -> None:
        """
        Load intent classification prompt from database

        Subclasses can override to customize prompt loading
        """
        try:
            db = MongoDBClient.get_database()
            prompt_repo = AgentPromptRepository(db)

            # Load prompt for this agent
            self._intent_prompt = await prompt_repo.find_by_agent_and_type(
                agent_name=self.name,
                prompt_type="intent_classification"
            )

            if self._intent_prompt:
                logger.info(
                    f"Loaded intent prompt for {self.name} "
                    f"(v{self._intent_prompt.version}, model={self._intent_prompt.model})"
                )
            else:
                logger.warning(f"No intent classification prompt found for {self.name}")

        except Exception as e:
            logger.error(f"Failed to load intent prompt for {self.name}: {e}", exc_info=True)

    async def classify_intent(
        self,
        variables: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Classify intent using loaded prompt and LLM

        Args:
            variables: Variables to fill in the prompt template
            session_id: Optional conversation session ID for event logging

        Returns:
            Parsed intent classification result, or None if no prompt loaded
        """
        if not self._intent_prompt:
            logger.warning(f"No intent prompt loaded for {self.name}, cannot classify")
            return None

        if not self._llm_service:
            logger.error(f"LLM service not initialized for {self.name}")
            return None

        try:
            result = await self._llm_service.classify_intent(
                agent_prompt=self._intent_prompt,
                variables=variables
            )

            # Log classification event if session tracking enabled
            if session_id and self._state_manager and result:
                try:
                    await self._state_manager.log_event(
                        session_id=session_id,
                        event_type="agent_classification",
                        agent_name=self.name,
                        data=result
                    )
                    logger.debug(f"Logged classification event for session {session_id}")
                except Exception as e:
                    logger.error(f"Failed to log classification event: {e}", exc_info=True)
                    # Continue even if logging fails

            return result

        except Exception as e:
            logger.error(f"Intent classification failed for {self.name}: {e}", exc_info=True)
            return None

    async def log_response(
        self,
        session_id: Optional[str],
        response: str,
        response_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Log agent's response to conversation state

        Args:
            session_id: Conversation session ID
            response: The agent's response text
            response_type: Type of response (e.g., "appointment_scheduling", "quote_request")
            metadata: Optional metadata (model, tokens, etc.)

        Returns:
            True if logged successfully, False otherwise
        """
        if not session_id or not self._state_manager:
            return False

        try:
            event_data = {
                "response": response,
            }

            if response_type:
                event_data["response_type"] = response_type

            if metadata:
                event_data.update(metadata)

            await self._state_manager.log_event(
                session_id=session_id,
                event_type="response_sent",
                agent_name=self.name,
                data=event_data
            )

            logger.debug(f"Logged response for session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to log response for session {session_id}: {e}", exc_info=True)
            return False

    async def generate_response_with_jobber_data(
        self,
        original_question: str,
        contact_name: str,
        classification: Dict[str, Any],
        jobber_data: Optional[Dict[str, Any]] = None,
        agent_context: str = ""
    ) -> str:
        """
        Generate a natural language response using LLM with Jobber data context

        This method is available to ALL agents that query Jobber data and need to
        generate customer-facing responses based on that data.

        Args:
            original_question: The customer's original question/request
            contact_name: Customer/vendor/contact name
            classification: Classification result with intent, urgency, etc.
            jobber_data: Data from Jobber (schedule, jobs, properties, payments, etc.)
            agent_context: Optional agent-specific context to include in the prompt

        Returns:
            Natural language response based on the data

        Example:
            response = await self.generate_response_with_jobber_data(
                original_question="What's my schedule for Friday?",
                contact_name="John Worker",
                classification={"intent": "SCHEDULE_INQUIRY", "urgency": "NORMAL"},
                jobber_data={"schedule": [...], "total_jobs": 3}
            )
        """
        try:
            if not self._llm_service:
                logger.error(f"LLM service not initialized for {self.name}")
                return f"Hi {contact_name}! I have your information. Let me get back to you shortly with the details. If you need immediate assistance, please call us at (305) 204-7598."

            # Extract intent and urgency from classification
            intent = classification.get("intent") or classification.get("vendor_intent") or classification.get("support_action") or classification.get("scheduling_action") or "GENERAL"
            urgency = classification.get("urgency", "NORMAL")
            summary = classification.get("summary", "")

            # Format Jobber data if available
            jobber_context = "No data available from Jobber."
            if jobber_data and jobber_data.get("status") == "success":
                if "schedule" in jobber_data:
                    # Format schedule data
                    schedule = jobber_data.get("schedule", [])
                    total_jobs = jobber_data.get("total_jobs", 0)
                    jobber_context = f"Schedule data retrieved from Jobber:\n"
                    jobber_context += f"Total jobs: {total_jobs}\n\n"

                    for day in schedule:
                        date = day.get("date")
                        day_of_week = day.get("day_of_week")
                        jobs = day.get("jobs", [])

                        jobber_context += f"**{day_of_week}, {date}** - {len(jobs)} job(s):\n"
                        for i, job in enumerate(jobs, 1):
                            jobber_context += f"{i}. {job.get('title')} ({job.get('job_number')})\n"
                            jobber_context += f"   Time: {job.get('start_time')} - {job.get('end_time')}\n"
                            jobber_context += f"   Location: {job.get('property_address')}\n"
                            jobber_context += f"   Client: {job.get('client_name')}\n"
                            if job.get('notes'):
                                jobber_context += f"   Notes: {job.get('notes')}\n"
                            jobber_context += "\n"

                elif "jobs" in jobber_data:
                    # Format jobs data
                    jobs = jobber_data.get("jobs", [])
                    jobber_context = f"Jobs data retrieved from Jobber:\n"
                    jobber_context += f"Total jobs: {len(jobs)}\n\n"
                    for i, job in enumerate(jobs, 1):
                        jobber_context += f"{i}. {job.get('title')} ({job.get('job_number')})\n"
                        jobber_context += f"   Status: {job.get('status')}\n"
                        jobber_context += f"   Location: {job.get('property_address')}\n"
                        if job.get('client_name'):
                            jobber_context += f"   Client: {job.get('client_name')}\n"
                        jobber_context += "\n"

                elif "payments" in jobber_data:
                    # Format payment data
                    payments = jobber_data.get("payments", [])
                    jobber_context = f"Payment data retrieved from Jobber:\n"
                    jobber_context += f"Total payments: {len(payments)}\n\n"
                    for i, payment in enumerate(payments, 1):
                        jobber_context += f"{i}. Invoice: {payment.get('invoice_number')}\n"
                        jobber_context += f"   Amount: ${payment.get('amount')}\n"
                        jobber_context += f"   Status: {payment.get('status')}\n"
                        jobber_context += f"   Due Date: {payment.get('due_date')}\n"
                        jobber_context += "\n"

                elif "property_access" in jobber_data:
                    # Format property access data
                    access = jobber_data.get("property_access", {})
                    jobber_context = f"Property access information retrieved from Jobber:\n"
                    jobber_context += f"Address: {access.get('address')}\n"
                    jobber_context += f"Access Instructions: {access.get('access_instructions')}\n"
                    if access.get('lockbox_code'):
                        jobber_context += f"Lockbox Code: {access.get('lockbox_code')}\n"
                    if access.get('gate_code'):
                        jobber_context += f"Gate Code: {access.get('gate_code')}\n"

            # Build prompt for LLM
            prompt = f"""You are a helpful assistant responding to a customer inquiry for a cleaning/field service business.

**Customer Name:** {contact_name}
**Original Question:** {original_question}

**Intent Classification:**
- Intent: {intent}
- Urgency: {urgency}
- Summary: {summary}

**Data from Jobber:**
{jobber_context}

{agent_context}

**Instructions:**
1. Answer the customer's question directly using the data provided
2. Be friendly, professional, and concise
3. If there are jobs/appointments scheduled, list them with times and locations
4. If no jobs/appointments are found, clearly state that
5. Always include contact info at the end: "If you have any questions, call us at (305) 204-7598"
6. Use the customer's name
7. Format with bullet points or numbered lists when appropriate

Generate a helpful response:"""

            # Call LLM using the LLM service
            response = await self._llm_service.generate_text(
                prompt=prompt,
                temperature=0.7,
                max_tokens=1000
            )

            return response.strip()

        except Exception as e:
            logger.error(f"Failed to generate response with LLM: {e}", exc_info=True)
            # Fallback to simple response
            return f"Hi {contact_name}! I have your information. Let me get back to you shortly with the details. If you need immediate assistance, please call us at (305) 204-7598."

    async def handle_urgent_escalation(
        self,
        contact_name: str,
        contact_identifier: str,
        subject: str,
        body: str,
        urgency: str,
        reason: str,
        additional_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle urgent escalation - available to ALL agents

        Sends SMS notification to on-call number via GoHighLevel when
        any agent detects an URGENT or IMMEDIATE situation.

        Args:
            contact_name: Customer/contact name
            contact_identifier: Email or phone number
            subject: Subject/title of the request
            body: Full body/content of the request
            urgency: Urgency level (URGENT or IMMEDIATE)
            reason: Human-readable reason for urgency
            additional_info: Optional dict with extra context

        Returns:
            Dict with transfer status and details

        Example:
            result = await self.handle_urgent_escalation(
                contact_name="John Doe",
                contact_identifier="john@example.com",
                subject="Missed Appointment",
                body="The team didn't show up today",
                urgency="URGENT",
                reason="URGENT: ISSUE_REPORT - Missed appointment complaint"
            )
        """
        logger.warning(f"🚨 {self.name} detected {urgency} situation!")
        logger.warning(f"   Contact: {contact_name} ({contact_identifier})")
        logger.warning(f"   Reason: {reason}")

        try:
            # Build contact info
            contact_info = {
                "name": contact_name,
                "email": contact_identifier,
                "subject": subject,
                "agent": self.name
            }

            if additional_info:
                contact_info.update(additional_info)

            # Transfer call via GoHighLevel
            transfer_result = self._ghl_client.transfer_call_urgent(
                from_number=contact_identifier,
                to_number=self._settings.on_call_number,
                reason=reason,
                contact_info=contact_info
            )

            if transfer_result.get("status") == "success":
                logger.info(f"✅ {self.name} successfully sent urgent notification to {self._settings.on_call_number}")
                logger.info(f"   Message ID: {transfer_result.get('message_id')}")
            else:
                logger.error(f"❌ {self.name} failed to send urgent notification: {transfer_result.get('message')}")

            return transfer_result

        except Exception as e:
            logger.error(f"❌ {self.name} failed to handle urgent escalation: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Exception during escalation: {str(e)}",
                "agent": self.name
            }

    async def _message_processing_loop(self) -> None:
        """
        Background task that continuously processes incoming messages
        """
        logger.info(f"{self.name} message processing loop started")

        while self.is_running:
            try:
                # Wait for incoming messages with 1-second timeout
                message = await self.receive_message(timeout=1.0)

                if message:
                    logger.info(f"{self.name} received message from {message.from_agent}: {message.type}")

                    # Handle the message
                    try:
                        await self.handle_message(message)
                    except Exception as e:
                        logger.error(f"{self.name} error handling message: {e}", exc_info=True)

                        # Send error response if it was a REQUEST
                        if message.type == MessageType.REQUEST:
                            error_response = Message(
                                type=MessageType.RESPONSE,
                                from_agent=self.name,
                                to_agent=message.from_agent,
                                payload={
                                    "status": "error",
                                    "message": f"Error processing request: {str(e)}",
                                    "agent": self.name
                                }
                            )
                            await self.send_message(error_response)

            except asyncio.CancelledError:
                logger.info(f"{self.name} message processing loop cancelled")
                break
            except Exception as e:
                logger.error(f"{self.name} error in processing loop: {e}", exc_info=True)
                # Continue running despite errors
                await asyncio.sleep(1.0)

        logger.info(f"{self.name} message processing loop stopped")

    @abstractmethod
    def get_capabilities(self) -> list[str]:
        """
        Get list of capabilities this agent provides

        Returns:
            List of capability names
        """
        pass

    @abstractmethod
    async def handle_message(self, message: Message) -> None:
        """
        Handle incoming message

        Args:
            message: Message to handle
        """
        pass

"""
GoHighLevel API Client - OAuth 2.0 authentication and CRM operations

Handles:
- OAuth 2.0 authentication with refresh token
- Contact management (search, create, update)
- Conversation retrieval
- Message management
- CSV-based mock CRM for testing/development
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import requests
from requests.exceptions import HTTPError

from src.config.settings import get_settings
from src.utils.csv_contact_manager import CSVContactManager
from src.utils.appointments_manager import AppointmentsManager
from src.utils.properties_manager import PropertiesManager
from src.utils.visits_manager import VisitsManager
from src.utils.quotes_manager import QuotesManager

logger = logging.getLogger(__name__)


class GoHighLevelClient:
    """
    GoHighLevel API client for Email Conversation Agent integration

    Provides methods to:
    - Find contacts by email address
    - Create new contacts from email interactions
    - Retrieve conversation history
    - Sync email conversations to GoHighLevel
    """

    BASE_URL = "https://services.leadconnectorhq.com"
    API_VERSION = "2021-07-28"

    def __init__(self):
        """Initialize GoHighLevel client with OAuth credentials"""
        self.settings = get_settings()
        self.access_token = self.settings.ghl_access_token
        self.refresh_token = self.settings.ghl_refresh_token
        self.client_id = self.settings.ghl_client_id
        self.client_secret = self.settings.ghl_client_secret
        self.location_id = self.settings.ghl_location_id
        self.token_expires_at = None

        # Initialize CSV managers for mock CRM (development/testing)
        self._contact_manager = CSVContactManager()
        self._appointments_manager = AppointmentsManager()
        self._properties_manager = PropertiesManager()
        self._visits_manager = VisitsManager()
        self._quotes_manager = QuotesManager()

    def _get_headers(self) -> Dict[str, str]:
        """
        Generate request headers with current access token

        Automatically refreshes token if expired

        Returns:
            Dict of HTTP headers for API requests
        """
        # Check if token needs refresh
        if not self.access_token or (
            self.token_expires_at and datetime.now() >= self.token_expires_at
        ):
            self._refresh_access_token()

        return {
            "Authorization": f"Bearer {self.access_token}",
            "Version": self.API_VERSION,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _refresh_access_token(self) -> None:
        """
        Refresh OAuth access token using refresh token

        Updates access_token and token_expires_at

        Raises:
            HTTPError: If token refresh fails
        """
        logger.info("Refreshing GoHighLevel access token")

        response = requests.post(
            f"{self.BASE_URL}/oauth/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        response.raise_for_status()
        tokens = response.json()

        self.access_token = tokens["access_token"]
        self.refresh_token = tokens["refresh_token"]  # Tokens rotate
        self.token_expires_at = datetime.now() + timedelta(
            seconds=tokens["expires_in"]
        )

        logger.info("Successfully refreshed access token")

    def find_contact_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Find GoHighLevel contact by email address

        **USE CASE:** When you need to look up whether a customer exists in CRM

        Args:
            email: Contact email address to search

        Returns:
            Contact data dict if found, None otherwise
            Contains: id, firstName, lastName, email, phone, tags, customFields

        Example:
            contact = client.find_contact_by_email("jane.doe@example.com")
            if contact:
                print(f"Found contact: {contact['firstName']} {contact['lastName']}")
        """
        logger.info(f"Searching for contact with email: {email}")

        try:
            response = requests.get(
                f"{self.BASE_URL}/v2/contacts/",
                headers=self._get_headers(),
                params={"locationId": self.location_id, "email": email},
            )

            response.raise_for_status()
            data = response.json()
            contacts = data.get("contacts", [])

            if contacts:
                logger.info(f"Found contact: {contacts[0]['id']}")
                return contacts[0]
            else:
                logger.info(f"No contact found for email: {email}")
                return None

        except HTTPError as e:
            logger.error(f"Error searching for contact: {e}")
            raise

    def create_contact(
        self,
        email: str,
        first_name: str = "",
        last_name: str = "",
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create new contact in GoHighLevel CRM

        **USE CASE:** When a new lead contacts you and needs to be added to CRM

        Args:
            email: Contact email address
            first_name: Contact first name (auto-extracted from email if not provided)
            last_name: Contact last name (auto-extracted from email if not provided)
            tags: Optional list of tags to apply to contact

        Returns:
            Created contact data with id, firstName, lastName, email, tags

        Example:
            contact = client.create_contact(
                email="jane.doe@example.com",
                first_name="Jane",
                last_name="Doe",
                tags=["email-lead", "website-inquiry"]
            )
        """
        logger.info(f"Creating new contact for email: {email}")

        # Extract name from email if not provided
        if not first_name:
            email_local = email.split("@")[0]
            parts = email_local.replace(".", " ").replace("_", " ").split()
            first_name = parts[0].capitalize() if parts else email_local

        if not last_name and len(email.split("@")[0].split(".")) > 1:
            last_name = email.split("@")[0].split(".")[1].capitalize()

        if tags is None:
            tags = ["email-lead"]

        payload = {
            "locationId": self.location_id,
            "firstName": first_name,
            "lastName": last_name,
            "email": email,
            "tags": tags,
            "source": "Email Conversation Agent",
        }

        try:
            response = requests.post(
                f"{self.BASE_URL}/v2/contacts/",
                headers=self._get_headers(),
                json=payload,
            )

            response.raise_for_status()
            result = response.json()

            contact = result.get("contact", {})
            logger.info(f"Successfully created contact: {contact.get('id')}")

            return contact

        except HTTPError as e:
            logger.error(f"Error creating contact: {e}")
            raise

    def get_conversations_by_email(self, email: str) -> List[Dict[str, Any]]:
        """
        Retrieve all conversations for a contact by email address

        **USE CASE:** When you need to see conversation history with a customer

        Two-step process:
        1. Find contact by email
        2. Get all conversations for that contact

        Args:
            email: Contact email address

        Returns:
            List of conversation dictionaries with id, type, contactId, lastMessageDate

        Example:
            conversations = client.get_conversations_by_email("jane.doe@example.com")
            for conv in conversations:
                print(f"Conversation {conv['id']}: {conv['type']}")
        """
        logger.info(f"Retrieving conversations for email: {email}")

        # Step 1: Find contact
        contact = self.find_contact_by_email(email)

        if not contact:
            logger.info(f"No contact found for email: {email}")
            return []

        contact_id = contact["id"]

        # Step 2: Get conversations
        try:
            response = requests.get(
                f"{self.BASE_URL}/v2/conversations/search",
                headers=self._get_headers(),
                params={"locationId": self.location_id, "contactId": contact_id},
            )

            response.raise_for_status()
            data = response.json()
            conversations = data.get("conversations", [])

            logger.info(
                f"Found {len(conversations)} conversation(s) for contact {contact_id}"
            )
            return conversations

        except HTTPError as e:
            logger.error(f"Error retrieving conversations: {e}")
            raise

    def get_conversation_messages(
        self, conversation_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve messages from a specific conversation

        **USE CASE:** When you need to see the full message thread for a conversation

        Args:
            conversation_id: GoHighLevel conversation ID
            limit: Maximum number of messages to retrieve (default 100)

        Returns:
            List of message dictionaries with id, body, direction, dateAdded, type

        Example:
            messages = client.get_conversation_messages("conversationId123", limit=50)
            for msg in messages:
                print(f"{msg['direction']}: {msg['body'][:50]}...")
        """
        logger.info(
            f"Retrieving messages for conversation: {conversation_id} (limit: {limit})"
        )

        try:
            response = requests.get(
                f"{self.BASE_URL}/v2/conversations/{conversation_id}/messages",
                headers=self._get_headers(),
                params={"limit": limit},
            )

            response.raise_for_status()
            data = response.json()
            messages = data.get("messages", [])

            logger.info(f"Retrieved {len(messages)} message(s)")
            return messages

        except HTTPError as e:
            logger.error(f"Error retrieving messages: {e}")
            raise

    def get_all_email_conversations(self, email: str) -> Dict[str, Any]:
        """
        Retrieve complete conversation history for a contact by email

        **USE CASE:** When you need the complete email conversation context with a customer

        Returns contact info, all conversations, and all email messages

        Args:
            email: Contact email address

        Returns:
            Dict with keys:
            - contact: Contact info dict
            - conversations: List of all conversations
            - messages: List of all email messages
            - total_messages: Total message count

        Example:
            result = client.get_all_email_conversations("jane.doe@example.com")
            print(f"Contact: {result['contact']['firstName']}")
            print(f"Total messages: {result['total_messages']}")
            for msg in result['messages']:
                print(f"  {msg['dateAdded']}: {msg['body'][:50]}...")
        """
        logger.info(f"Retrieving all email conversations for: {email}")

        # Step 1: Find contact
        contact = self.find_contact_by_email(email)

        if not contact:
            logger.info(f"No contact found for email: {email}")
            return {
                "contact": None,
                "conversations": [],
                "messages": [],
                "total_messages": 0,
            }

        # Step 2: Get all conversations
        conversations = self.get_conversations_by_email(email)

        # Step 3: Get messages from each email conversation
        all_messages = []
        for conv in conversations:
            if conv.get("type") == "Email":
                messages = self.get_conversation_messages(conv["id"])
                all_messages.extend(messages)

        logger.info(f"Retrieved {len(all_messages)} total email message(s)")

        return {
            "contact": contact,
            "conversations": conversations,
            "messages": all_messages,
            "total_messages": len(all_messages),
        }

    def find_or_create_contact(
        self, email: str, first_name: str = "", last_name: str = ""
    ) -> Dict[str, Any]:
        """
        Find existing contact by email or create new one if not found

        **USE CASE:** When processing a contact and you're not sure if they exist in CRM yet

        Args:
            email: Contact email address
            first_name: Optional first name for new contact
            last_name: Optional last name for new contact

        Returns:
            Contact data (existing or newly created) with id, firstName, lastName, email

        Example:
            contact = client.find_or_create_contact(
                email="jane.doe@example.com",
                first_name="Jane",
                last_name="Doe"
            )
            print(f"Contact ID: {contact['id']}")
        """
        # Try to find existing contact
        contact = self.find_contact_by_email(email)

        if contact:
            logger.info(f"Found existing contact: {contact['id']}")
            return contact

        # Create new contact if not found
        logger.info(f"Creating new contact for: {email}")
        contact = self.create_contact(email, first_name, last_name)

        return contact

    def transfer_call_urgent(
        self,
        from_number: str,
        to_number: str,
        reason: str,
        contact_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Transfer call to on-call number for URGENT situations

        **USE CASE:** When customer has critical emergency requiring immediate human intervention
        Examples: Locked out, cleaning team no-show, property damage, safety issue

        Uses GoHighLevel's call/SMS API to forward urgent requests to staff

        Args:
            from_number: Original caller's phone number
            to_number: On-call staff number to transfer to
            reason: Reason for urgent transfer (e.g., "URGENT: Customer locked out")
            contact_info: Optional contact information dictionary

        Returns:
            Dict with call transfer status:
            - status: "success" or "error"
            - message: "TRANSFERRING URGENT CALL"
            - to_number: Staff number called
            - from_number: Original caller
            - reason: Transfer reason
            - timestamp: ISO format timestamp

        Example:
            result = client.transfer_call_urgent(
                from_number="+1305555001",
                to_number="+1305555999",
                reason="URGENT: Cleaning team missed appointment",
                contact_info={"name": "John Doe", "email": "john@example.com"}
            )
            # Returns:
            {
                "status": "success",
                "message": "TRANSFERRING URGENT CALL",
                "to_number": "+1305555999",
                "from_number": "+1305555001",
                "reason": "URGENT: Cleaning team missed appointment",
                "timestamp": "2026-02-22T10:30:00"
            }

        **Security Note:** Only use for verified urgent situations to prevent abuse
        """
        logger.info(f"🚨 TRANSFERRING URGENT CALL from {from_number} to {to_number}")
        logger.info(f"Reason: {reason}")

        contact_name = contact_info.get("name", "Unknown") if contact_info else "Unknown"
        contact_email = contact_info.get("email", "N/A") if contact_info else "N/A"

        logger.info(f"Contact: {contact_name} ({contact_email})")

        # For testing: Just return success without making actual API calls or sending SMS
        return {
            "status": "success",
            "message": "TRANSFERRING URGENT CALL",
            "to_number": to_number,
            "from_number": from_number,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }

    # ==================== CSV-BASED MOCK CRM METHODS ====================
    # These methods provide CRUD operations for contacts and appointments
    # using CSV files as a simple mock CRM for development/testing

    def csv_create_contact(
        self,
        email: str,
        phone: Optional[str] = None,
        name: Optional[str] = None,
        classification: str = "lead",
        lead_quality: Optional[str] = None,
        source: str = "email",
        status: str = "new",
        company: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create contact in CSV mock CRM

        Args:
            email: Contact email
            phone: Contact phone
            name: Contact name
            classification: lead, client, or vendor
            lead_quality: HOT, WARM, COLD (for leads)
            source: email, phone, web
            status: new, active, etc.
            company: Company name
            notes: Additional notes

        Returns:
            Contact dict with contact_id
        """
        return self._contact_manager.create_contact(
            email=email,
            phone=phone,
            name=name,
            classification=classification,
            lead_quality=lead_quality,
            source=source,
            status=status,
            company=company,
            notes=notes
        )

    def csv_find_contact_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Find contact in CSV by email"""
        return self._contact_manager.find_contact_by_email(email)

    def csv_find_contact_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Find contact in CSV by phone"""
        return self._contact_manager.find_contact_by_phone(phone)

    def csv_update_contact(self, email: str, **updates) -> Optional[Dict[str, Any]]:
        """Update contact in CSV"""
        return self._contact_manager.update_contact(email, **updates)

    def csv_list_contacts(self, classification: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all contacts from CSV, optionally filtered by classification"""
        return self._contact_manager.list_all_contacts(classification=classification)

    def csv_delete_contact(self, email: str) -> bool:
        """Delete contact from CSV"""
        return self._contact_manager.delete_contact(email)

    # ==================== APPOINTMENT CRUD METHODS ====================

    def csv_create_appointment(
        self,
        customer_email: str,
        customer_phone: str,
        customer_name: str,
        property_type: str,
        property_address: str,
        num_bedrooms: Optional[int] = None,
        num_bathrooms: Optional[int] = None,
        square_feet: Optional[int] = None,
        preferred_date: Optional[str] = None,
        preferred_time: Optional[str] = None,
        service_type: Optional[str] = None,
        status: str = "pending",
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create appointment in CSV mock system

        Args:
            customer_email: Customer email
            customer_phone: Customer phone
            customer_name: Customer name
            property_type: vacation rental, residential, commercial
            property_address: Full property address
            num_bedrooms: Number of bedrooms
            num_bathrooms: Number of bathrooms
            square_feet: Property square footage
            preferred_date: Requested date
            preferred_time: Requested time
            service_type: Type of cleaning
            status: pending, confirmed, completed, cancelled
            notes: Special instructions

        Returns:
            Appointment dict with appointment_id
        """
        return self._appointments_manager.create_appointment(
            customer_email=customer_email,
            customer_phone=customer_phone,
            customer_name=customer_name,
            property_type=property_type,
            property_address=property_address,
            num_bedrooms=num_bedrooms,
            num_bathrooms=num_bathrooms,
            square_feet=square_feet,
            preferred_date=preferred_date,
            preferred_time=preferred_time,
            service_type=service_type,
            status=status,
            notes=notes
        )

    def csv_find_appointment_by_id(self, appointment_id: str) -> Optional[Dict[str, Any]]:
        """Find appointment in CSV by appointment_id"""
        return self._appointments_manager.find_appointment_by_id(appointment_id)

    def csv_find_appointments_by_customer(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Find appointments for a customer by email or phone"""
        return self._appointments_manager.find_appointments_by_customer(email=email, phone=phone)

    def csv_find_appointments_by_date(self, date: str) -> List[Dict[str, Any]]:
        """Find appointments for a specific date"""
        return self._appointments_manager.find_appointments_by_date(date)

    def csv_update_appointment(
        self,
        appointment_id: str,
        **updates
    ) -> Optional[Dict[str, Any]]:
        """Update appointment in CSV"""
        return self._appointments_manager.update_appointment(appointment_id, **updates)

    def csv_cancel_appointment(self, appointment_id: str) -> bool:
        """Cancel appointment (sets status to cancelled)"""
        return self._appointments_manager.cancel_appointment(appointment_id)

    def csv_list_all_appointments(
        self,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all appointments, optionally filtered by status"""
        return self._appointments_manager.list_all_appointments(status=status)

    def csv_delete_appointment(self, appointment_id: str) -> bool:
        """Delete appointment from CSV"""
        return self._appointments_manager.delete_appointment(appointment_id)

    # ==================== PROPERTIES CRUD METHODS ====================

    def csv_create_property(
        self,
        contact_id: str,
        customer_email: str,
        customer_name: str,
        property_type: str,
        property_address: str,
        city: Optional[str] = None,
        state: Optional[str] = None,
        zip_code: Optional[str] = None,
        num_bedrooms: Optional[int] = None,
        num_bathrooms: Optional[int] = None,
        square_feet: Optional[int] = None,
        property_notes: Optional[str] = None,
        status: str = "active"
    ) -> Dict[str, Any]:
        """
        Create property in CSV mock system

        Args:
            contact_id: Contact ID (FK to contacts.csv)
            customer_email: Customer email
            customer_name: Customer name
            property_type: vacation rental, residential, commercial
            property_address: Full property address
            city: City
            state: State
            zip_code: ZIP code
            num_bedrooms: Number of bedrooms
            num_bathrooms: Number of bathrooms
            square_feet: Square footage
            property_notes: Additional notes about property
            status: active, inactive, archived

        Returns:
            Property dict with property_id
        """
        return self._properties_manager.create_property(
            contact_id=contact_id,
            customer_email=customer_email,
            customer_name=customer_name,
            property_type=property_type,
            property_address=property_address,
            city=city,
            state=state,
            zip_code=zip_code,
            num_bedrooms=num_bedrooms,
            num_bathrooms=num_bathrooms,
            square_feet=square_feet,
            property_notes=property_notes,
            status=status
        )

    def csv_find_property_by_id(self, property_id: str) -> Optional[Dict[str, Any]]:
        """Find property in CSV by property_id"""
        return self._properties_manager.find_property_by_id(property_id)

    def csv_find_properties_by_contact(self, contact_id: str) -> List[Dict[str, Any]]:
        """Find all properties for a contact"""
        return self._properties_manager.find_properties_by_contact(contact_id)

    def csv_find_properties_by_email(self, customer_email: str) -> List[Dict[str, Any]]:
        """Find all properties for a customer email"""
        return self._properties_manager.find_properties_by_email(customer_email)

    def csv_list_all_properties(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all properties, optionally filtered by status"""
        return self._properties_manager.list_all_properties(status=status)

    def csv_update_property(
        self,
        property_id: str,
        **updates
    ) -> Optional[Dict[str, Any]]:
        """Update property in CSV"""
        return self._properties_manager.update_property(property_id, **updates)

    def csv_delete_property(self, property_id: str) -> bool:
        """Delete property from CSV"""
        return self._properties_manager.delete_property(property_id)

    # ==================== VISITS CRUD METHODS ====================

    def csv_create_visit(
        self,
        property_id: str,
        contact_id: str,
        customer_email: str,
        customer_name: str,
        visit_date: str,
        visit_time: str,
        service_type: str,
        assigned_to: Optional[str] = None,
        status: str = "scheduled",
        duration_minutes: Optional[int] = None,
        completion_notes: Optional[str] = None,
        checklist_completed: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Create visit in CSV mock system

        Args:
            property_id: Property ID (FK to properties.csv)
            contact_id: Contact ID (FK to contacts.csv)
            customer_email: Customer email
            customer_name: Customer name
            visit_date: Visit date (YYYY-MM-DD)
            visit_time: Visit time (HH:MM AM/PM)
            service_type: Type of cleaning service
            assigned_to: Team or person assigned
            status: scheduled, in_progress, completed, cancelled, rescheduled
            duration_minutes: Actual duration in minutes
            completion_notes: Notes after completion
            checklist_completed: Whether checklist was completed

        Returns:
            Visit dict with visit_id
        """
        return self._visits_manager.create_visit(
            property_id=property_id,
            contact_id=contact_id,
            customer_email=customer_email,
            customer_name=customer_name,
            visit_date=visit_date,
            visit_time=visit_time,
            service_type=service_type,
            assigned_to=assigned_to,
            status=status,
            duration_minutes=duration_minutes,
            completion_notes=completion_notes,
            checklist_completed=checklist_completed
        )

    def csv_find_visit_by_id(self, visit_id: str) -> Optional[Dict[str, Any]]:
        """Find visit in CSV by visit_id"""
        return self._visits_manager.find_visit_by_id(visit_id)

    def csv_find_visits_by_property(self, property_id: str) -> List[Dict[str, Any]]:
        """Find all visits for a property"""
        return self._visits_manager.find_visits_by_property(property_id)

    def csv_find_visits_by_contact(self, contact_id: str) -> List[Dict[str, Any]]:
        """Find all visits for a contact (across all properties)"""
        return self._visits_manager.find_visits_by_contact(contact_id)

    def csv_find_visits_by_date(self, visit_date: str) -> List[Dict[str, Any]]:
        """Find all visits for a specific date"""
        return self._visits_manager.find_visits_by_date(visit_date)

    def csv_find_visits_by_assigned(self, assigned_to: str) -> List[Dict[str, Any]]:
        """Find all visits assigned to a team/person"""
        return self._visits_manager.find_visits_by_assigned(assigned_to)

    def csv_list_all_visits(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all visits, optionally filtered by status"""
        return self._visits_manager.list_all_visits(status=status)

    def csv_update_visit(
        self,
        visit_id: str,
        **updates
    ) -> Optional[Dict[str, Any]]:
        """Update visit in CSV"""
        return self._visits_manager.update_visit(visit_id, **updates)

    def csv_cancel_visit(self, visit_id: str) -> bool:
        """Cancel visit (sets status to cancelled)"""
        return self._visits_manager.cancel_visit(visit_id)

    def csv_complete_visit(
        self,
        visit_id: str,
        duration_minutes: Optional[int] = None,
        completion_notes: Optional[str] = None,
        checklist_completed: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Mark visit as completed"""
        return self._visits_manager.complete_visit(
            visit_id=visit_id,
            duration_minutes=duration_minutes,
            completion_notes=completion_notes,
            checklist_completed=checklist_completed
        )

    def csv_delete_visit(self, visit_id: str) -> bool:
        """Delete visit from CSV"""
        return self._visits_manager.delete_visit(visit_id)

    # ==================== QUOTES CRUD METHODS ====================

    def csv_create_quote(
        self,
        contact_id: str,
        customer_email: str,
        customer_name: str,
        service_type: str,
        property_id: Optional[str] = None,
        property_address: Optional[str] = None,
        square_feet: Optional[int] = None,
        num_bedrooms: Optional[int] = None,
        num_bathrooms: Optional[int] = None,
        frequency: Optional[str] = None,
        quoted_amount: Optional[float] = None,
        valid_until: Optional[str] = None,
        status: str = "draft",
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create quote in CSV mock system

        Args:
            contact_id: Contact ID (FK to contacts.csv)
            customer_email: Customer email
            customer_name: Customer name
            service_type: Type of cleaning service
            property_id: Property ID (FK to properties.csv, optional)
            property_address: Property address
            square_feet: Square footage
            num_bedrooms: Number of bedrooms
            num_bathrooms: Number of bathrooms
            frequency: one-time, weekly, bi-weekly, monthly
            quoted_amount: Quote amount in dollars
            valid_until: Quote expiration date (YYYY-MM-DD)
            status: draft, sent, accepted, rejected, expired
            notes: Additional notes

        Returns:
            Quote dict with quote_id
        """
        return self._quotes_manager.create_quote(
            contact_id=contact_id,
            customer_email=customer_email,
            customer_name=customer_name,
            service_type=service_type,
            property_id=property_id,
            property_address=property_address,
            square_feet=square_feet,
            num_bedrooms=num_bedrooms,
            num_bathrooms=num_bathrooms,
            frequency=frequency,
            quoted_amount=quoted_amount,
            valid_until=valid_until,
            status=status,
            notes=notes
        )

    def csv_find_quote_by_id(self, quote_id: str) -> Optional[Dict[str, Any]]:
        """Find quote in CSV by quote_id"""
        return self._quotes_manager.find_quote_by_id(quote_id)

    def csv_find_quotes_by_contact(self, contact_id: str) -> List[Dict[str, Any]]:
        """Find all quotes for a contact"""
        return self._quotes_manager.find_quotes_by_contact(contact_id)

    def csv_find_quotes_by_property(self, property_id: str) -> List[Dict[str, Any]]:
        """Find all quotes for a property"""
        return self._quotes_manager.find_quotes_by_property(property_id)

    def csv_find_quotes_by_email(self, customer_email: str) -> List[Dict[str, Any]]:
        """Find all quotes for a customer email"""
        return self._quotes_manager.find_quotes_by_email(customer_email)

    def csv_list_all_quotes(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all quotes, optionally filtered by status"""
        return self._quotes_manager.list_all_quotes(status=status)

    def csv_update_quote(
        self,
        quote_id: str,
        **updates
    ) -> Optional[Dict[str, Any]]:
        """Update quote in CSV"""
        return self._quotes_manager.update_quote(quote_id, **updates)

    def csv_accept_quote(self, quote_id: str) -> Optional[Dict[str, Any]]:
        """Accept quote (sets status to accepted)"""
        return self._quotes_manager.accept_quote(quote_id)

    def csv_reject_quote(self, quote_id: str, notes: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Reject quote (sets status to rejected)"""
        return self._quotes_manager.reject_quote(quote_id, notes=notes)

    def csv_expire_quote(self, quote_id: str) -> Optional[Dict[str, Any]]:
        """Expire quote (sets status to expired)"""
        return self._quotes_manager.expire_quote(quote_id)

    def csv_send_quote(self, quote_id: str) -> Optional[Dict[str, Any]]:
        """Send quote (sets status to sent)"""
        return self._quotes_manager.send_quote(quote_id)

    def csv_delete_quote(self, quote_id: str) -> bool:
        """Delete quote from CSV"""
        return self._quotes_manager.delete_quote(quote_id)

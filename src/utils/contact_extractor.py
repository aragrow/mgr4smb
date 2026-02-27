"""
Contact Extractor Tool - Extract phone/email from text before LLM processing

Provides regex-based extraction of contact information from messages
to reduce LLM costs and improve reliability
"""

import re
import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


class ContactExtractor:
    """
    Tool to extract contact information (phone, email) from text

    Uses regex patterns to identify phone numbers and email addresses
    before sending to LLM for processing
    """

    # Email pattern - matches most common email formats
    EMAIL_PATTERN = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    )

    # Phone patterns - multiple formats
    PHONE_PATTERNS = [
        # (123) 456-7890
        re.compile(r'\((\d{3})\)\s*(\d{3})-(\d{4})'),
        # 123-456-7890
        re.compile(r'(\d{3})-(\d{3})-(\d{4})'),
        # 123.456.7890
        re.compile(r'(\d{3})\.(\d{3})\.(\d{4})'),
        # 1234567890 (10 digits)
        re.compile(r'\b(\d{10})\b'),
        # +1 123 456 7890 or +1-123-456-7890
        re.compile(r'\+1\s*(\d{3})\s*(\d{3})\s*(\d{4})'),
        # +1 (123) 456-7890
        re.compile(r'\+1\s*\((\d{3})\)\s*(\d{3})-(\d{4})'),
    ]

    @classmethod
    def extract_email(cls, text: str) -> Optional[str]:
        """
        Extract email address from text

        Args:
            text: Text to search for email

        Returns:
            First email found, or None
        """
        if not text:
            return None

        match = cls.EMAIL_PATTERN.search(text)
        if match:
            email = match.group(0)
            logger.info(f"✓ Extracted email: {email}")
            return email

        return None

    @classmethod
    def extract_phone(cls, text: str) -> Optional[str]:
        """
        Extract phone number from text

        Args:
            text: Text to search for phone number

        Returns:
            First phone number found (normalized), or None
        """
        if not text:
            return None

        # Try each pattern
        for pattern in cls.PHONE_PATTERNS:
            match = pattern.search(text)
            if match:
                # Extract groups and normalize
                if len(match.groups()) == 1:
                    # Single group (10 digits)
                    digits = match.group(1)
                else:
                    # Multiple groups - join them
                    digits = ''.join(match.groups())

                # Normalize to format: +1-XXX-XXX-XXXX
                if len(digits) == 10:
                    normalized = f"+1-{digits[0:3]}-{digits[3:6]}-{digits[6:10]}"
                    logger.info(f"✓ Extracted phone: {normalized} (from: {match.group(0)})")
                    return normalized

        return None

    @classmethod
    def extract_contacts(cls, text: str) -> Dict[str, Optional[str]]:
        """
        Extract both email and phone from text

        Args:
            text: Text to search

        Returns:
            Dict with 'email' and 'phone' keys (values can be None)
        """
        if not text:
            return {"email": None, "phone": None}

        email = cls.extract_email(text)
        phone = cls.extract_phone(text)

        result = {
            "email": email,
            "phone": phone
        }

        if email or phone:
            logger.info(f"Contact extraction result: {result}")
        else:
            logger.debug(f"No contact info found in text: {text[:100]}...")

        return result

    @classmethod
    def extract_all_emails(cls, text: str) -> List[str]:
        """
        Extract all email addresses from text

        Args:
            text: Text to search

        Returns:
            List of all emails found
        """
        if not text:
            return []

        matches = cls.EMAIL_PATTERN.findall(text)
        if matches:
            logger.info(f"Found {len(matches)} email(s): {matches}")

        return matches

    @classmethod
    def extract_all_phones(cls, text: str) -> List[str]:
        """
        Extract all phone numbers from text

        Args:
            text: Text to search

        Returns:
            List of all normalized phone numbers found
        """
        if not text:
            return []

        phones = []
        for pattern in cls.PHONE_PATTERNS:
            for match in pattern.finditer(text):
                if len(match.groups()) == 1:
                    digits = match.group(1)
                else:
                    digits = ''.join(match.groups())

                if len(digits) == 10:
                    normalized = f"+1-{digits[0:3]}-{digits[3:6]}-{digits[6:10]}"
                    if normalized not in phones:
                        phones.append(normalized)

        if phones:
            logger.info(f"Found {len(phones)} phone(s): {phones}")

        return phones

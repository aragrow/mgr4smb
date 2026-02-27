#!/usr/bin/env python3
"""
Quick test script for ContactExtractor tool
"""

from src.utils.contact_extractor import ContactExtractor


def test_extraction():
    """Test various contact extraction scenarios"""

    print("=" * 60)
    print("Contact Extractor Tool - Test Cases")
    print("=" * 60)

    test_cases = [
        # Email tests
        {
            "name": "Simple email",
            "text": "Hi, my email is john.doe@example.com",
            "expected": {"email": "john.doe@example.com", "phone": None}
        },
        {
            "name": "Email in sentence",
            "text": "You can reach me at contact@company.org for any questions",
            "expected": {"email": "contact@company.org", "phone": None}
        },
        # Phone tests
        {
            "name": "Phone with parentheses",
            "text": "Call me at (305) 555-1234",
            "expected": {"email": None, "phone": "+1-305-555-1234"}
        },
        {
            "name": "Phone with dashes",
            "text": "My number is 305-555-1234",
            "expected": {"email": None, "phone": "+1-305-555-1234"}
        },
        {
            "name": "Phone with dots",
            "text": "Reach me at 305.555.1234",
            "expected": {"email": None, "phone": "+1-305-555-1234"}
        },
        {
            "name": "10 digit phone",
            "text": "My phone is 3055551234",
            "expected": {"email": None, "phone": "+1-305-555-1234"}
        },
        {
            "name": "Phone with +1",
            "text": "Call +1 305 555 1234",
            "expected": {"email": None, "phone": "+1-305-555-1234"}
        },
        # Both email and phone
        {
            "name": "Email and phone together",
            "text": "Contact me at john@example.com or call (305) 555-1234",
            "expected": {"email": "john@example.com", "phone": "+1-305-555-1234"}
        },
        {
            "name": "Complex message",
            "text": "Hi! I'm interested in your services. You can email me at customer@gmail.com or text 305-555-9999. Thanks!",
            "expected": {"email": "customer@gmail.com", "phone": "+1-305-555-9999"}
        },
        # Edge cases
        {
            "name": "No contact info",
            "text": "I need help with my order",
            "expected": {"email": None, "phone": None}
        },
    ]

    passed = 0
    failed = 0

    for i, test in enumerate(test_cases, 1):
        print(f"\n{i}. {test['name']}")
        print(f"   Input: {test['text']}")

        result = ContactExtractor.extract_contacts(test['text'])

        print(f"   Expected: {test['expected']}")
        print(f"   Got:      {result}")

        if result == test['expected']:
            print(f"   ✅ PASS")
            passed += 1
        else:
            print(f"   ❌ FAIL")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 60)


if __name__ == "__main__":
    test_extraction()

"""Test phone number formatting logic"""
import os
os.environ["DEFAULT_COUNTRY_CODE"] = "91"

from utils.whatsapp import format_phone_number

# Test cases
test_cases = [
    ("+911234567890", "911234567890", "International with +"),
    ("911234567890", "911234567890", "International without +"),
    ("01234567890", "911234567890", "Local format with leading 0"),
    ("09876543210", "919876543210", "Another local format with 0"),
    ("1234567890", "911234567890", "10 digits without country code"),
    ("+1234567890", "1234567890", "Non-Indian international (11 digits)"),
    ("12345678901", "12345678901", "Already has country code (11 digits)"),
    ("", "", "Empty string"),
    ("+91-9876-543210", "919876543210", "With dashes and +"),
]

print("=" * 70)
print("PHONE NUMBER FORMATTING TESTS")
print("=" * 70)
print(f"Default Country Code: {os.environ.get('DEFAULT_COUNTRY_CODE', '91')}")
print("=" * 70)

all_passed = True
for input_num, expected, description in test_cases:
    result = format_phone_number(input_num)
    passed = result == expected
    status = "✅ PASS" if passed else "❌ FAIL"
    
    print(f"{status} | {description}")
    print(f"       Input:    '{input_num}'")
    print(f"       Expected: '{expected}'")
    print(f"       Got:      '{result}'")
    print("-" * 70)
    
    if not passed:
        all_passed = False

print("=" * 70)
if all_passed:
    print("✅ ALL TESTS PASSED!")
else:
    print("❌ SOME TESTS FAILED!")
print("=" * 70)

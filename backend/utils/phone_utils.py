"""
Phone number utilities extracted from server.py.

These functions handle phone number normalization and validation.
"""

from typing import Any


def normalize_phone_number(value: Any) -> str:
    """
    Normalize a phone number to a consistent format.
    
    Handles Brazilian phone numbers and adds country code if needed.
    
    Args:
        value: The phone number to normalize
        
    Returns:
        Normalized phone number string
    """
    s = str(value or '').strip()
    if not s:
        return ''
    
    # Extract only digits
    digits = ''.join(ch for ch in s if ch.isdigit())
    if not digits:
        return ''
    
    # Remove leading zeros for long numbers
    if len(digits) > 10:
        digits = digits.lstrip('0')
    
    # Handle international prefix 00
    if digits.startswith('00'):
        digits = digits[2:]
        digits = digits.lstrip('0')
    
    # Already has Brazilian country code
    if digits.startswith('55'):
        return digits
    
    # US/Russia 11-digit numbers starting with 1 or 7
    if len(digits) == 11 and digits[0] in ('1', '7'):
        return digits
    
    # Brazilian numbers without country code (10 or 11 digits)
    if len(digits) == 10:
        return f"55{digits}"
    if len(digits) == 11:
        return f"55{digits}"
    
    return digits


def format_phone_for_display(phone: str) -> str:
    """
    Format a phone number for display.
    
    Args:
        phone: The normalized phone number
        
    Returns:
        Formatted phone number string
    """
    if not phone:
        return ""
    
    # Brazilian numbers
    if phone.startswith("55") and len(phone) >= 12:
        # +55 (XX) XXXX-XXXX or +55 (XX) XXXXX-XXXX
        country = phone[:2]
        area = phone[2:4]
        rest = phone[4:]
        
        if len(rest) == 8:
            return f"+{country} ({area}) {rest[:4]}-{rest[4:]}"
        elif len(rest) == 9:
            return f"+{country} ({area}) {rest[:5]}-{rest[5:]}"
    
    return phone


def extract_phone_from_jid(jid: str) -> str:
    """
    Extract phone number from WhatsApp JID.
    
    Args:
        jid: WhatsApp JID (e.g., "5511999999999@s.whatsapp.net")
        
    Returns:
        Phone number string
    """
    if not jid:
        return ""
    
    # Remove @s.whatsapp.net or similar suffixes
    phone = str(jid).split("@")[0]
    
    # Remove any non-digit characters
    phone = ''.join(ch for ch in phone if ch.isdigit())
    
    return phone


def phone_to_jid(phone: str) -> str:
    """
    Convert phone number to WhatsApp JID.
    
    Args:
        phone: The phone number
        
    Returns:
        WhatsApp JID string
    """
    normalized = normalize_phone_number(phone)
    if not normalized:
        return ""
    return f"{normalized}@s.whatsapp.net"


# Backwards compatibility alias
normalize_phone = normalize_phone_number

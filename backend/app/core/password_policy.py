from __future__ import annotations

import re

MIN_PASSWORD_LENGTH: int = 8
MAX_PASSWORD_LENGTH: int = 128
MAX_PASSWORD_BYTES: int = 72 # bcrypt limitation

def validate_password_strength(value: str) -> str:
    """
    Checks the password complexity and returns it unchanged.
    """
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"The password must contain at least {MIN_PASSWORD_LENGTH} characters"
        )
    if len(value) > MAX_PASSWORD_LENGTH:
        raise ValueError(
            f"The password must contain no more than {MAX_PASSWORD_LENGTH} characters"
        )
    
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"The password too long (maximum {MAX_PASSWORD_BYTES} bytes)"
        )
    
    if not re.search(r"[A-ZА-ЯЇІЄҐ]", value):
        raise ValueError("The password must contain at least one uppercase letter")
    if not re.search(r"[a-zа-яїієґ]", value):
        raise ValueError("The password must contain at least one lowercase letter")
    if not re.search(r"\d", value):
        raise ValueError("The password must contain at least one digit")
    
    return value

import re
from typing import Any

# Allowed domains
PUBLIC_DOMAINS: set[str] = {
    "gmail.com",
    "outlook.com",
    "yahoo.com",
    "icloud.com",
    "hotmail.com",
}

# Prohibited domains (e.g. spam)
BANNED_DOMAINS: set[str] | None = {
    "tempmail.com",
    "maximail.vip",
    "freeml.net",
}

# Email format validation (for a quick 422 response, without DNS checks)
EMAIL_PATTERN: re.Pattern[str] = re.compile(
    r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)

def normalize_and_validate_email(value: str) -> str:
    """
    Normalize email address:
    - converts the email to lowercase.

    Email validity check:
    - length (must be <= 255 characters);
    - by EMAIL_PATTERN;
    - local part length (must be <= 64 characters);
    - by BANNED_DOMAINS;
    - by EMAIL_PATTERN;
    - domain validity check
    """
    if not isinstance(value, str):
        raise ValueError(f"Email must be a string")
    
    value = value.strip().lower()
    
    if len(value) > 255:
        raise ValueError(f"Email must be at most 255 characters long")
    
    if not EMAIL_PATTERN.match(value):
        raise ValueError("Invalid email address")
    
    local_part, domain = value.rsplit("@", 1)
    
    if len(local_part) > 64:
        raise ValueError("Email local part (before '@' too long")
    
    if domain in BANNED_DOMAINS:
        raise ValueError("This email address is temporary or blocked")
    
    if domain not in PUBLIC_DOMAINS:
        if "." not in domain:
            raise ValueError("Invalid domain format")
        
        tld = domain.rsplit(".", 1)[-1]
        if len(tld) < 2:
            raise ValueError("The zone of the domain is incorrect")
    
    return value

def trim_names(value: Any) -> Any:
    if isinstance(value, str):
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be empty or contain only spaces")
    return value
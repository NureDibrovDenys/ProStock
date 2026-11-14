
from __future__ import annotations

from decimal import Decimal

def volume_m3(width: Decimal | float, length: Decimal | float, height: Decimal | float) -> Decimal:
    
    return Decimal(str(width)) * Decimal(str(length)) * Decimal(str(height))

def percent(used: Decimal | float, total: Decimal | float) -> float:
    
    total_dec = Decimal(str(total))
    if total_dec <= 0:
        return 0.0
    value = Decimal(str(used)) / total_dec * Decimal(100)
    return round(float(value), 1)

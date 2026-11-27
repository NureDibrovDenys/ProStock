from enum import Enum

class RoleName(str, Enum):
    ROOT = "root"
    ADMIN = "administrator"
    WAREHOUSE_MANAGER = "warehouse_manager"
    WORKER = "storekeeper"
    GUEST = "guest"

class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"

class ShelfStatus(str, Enum):
    ACTIVE = "active"
    OCCUPIED = "occupied"
    INACTIVE = "inactive" # Не функціонує

class InactiveReason(str, Enum):
    DAMAGED = "damaged" # Фізичне пошкодження
    MAINTENANCE = "maintenance" # Планове технічне обслуговування
    STOCKTAKING = "stocktaking" # Інвентаризація
    QUALITY_CONTROL = "quality_control" # Перевірка якості
    OTHER = "other"

class ZoneType(str, Enum):
    INBOUND_DOCK = "inbound_dock" # Зона приймання
    STORAGE_AREA = "storage_area" # Зона зберігання
    OUTBOUND_DOCK = "outbound_dock" # Зона відвантаження

class ObstacleType(str, Enum):
    COLUMN = "column" # Колона
    PILLAR = "pillar" # Стовп
    NICHE = "niche" # Заглиблення
    RESTRICTED_ZONE = "restricted_zone" # Зона обмеженого доступу
    OTHER = "other"

class PointType(str, Enum):
    INBOUND = "inbound" # Точка прийняття
    OUTBOUND = "outbound" # Точка відвантаження
    GENERAL_ENTRY = "general_entry" # Основний вхід

class UnitOfMeasure(str, Enum):
    PCS = "pcs"
    KG = "kg"
    POUND = "pound"
    BOX = "box"
    PALLET = "pallet"
    OTHER = "other"

class SupplierStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"

class RecipientStatus(str, Enum):
    ACTIVE = "active" # Дозвіл на співпрацю
    INACTIVE = "inactive" # Архівування (видалення)
    BLOCKED = "blocked" # Заборона співпраці

class OrderStatus(str, Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    READY = "ready" # сформовано завдання
    COMPLETED = "completed"
    CANCELED = "canceled"

class StockMovementType(str, Enum):
    
    INBOUND_ORDER = "inbound_order" # приймання за прихідною накладною
    OUTBOUND_ORDER = "outbound_order" # відвантаження за вихідною накладною
    MANUAL = "manual" # ручна корекція залишку

class OrderType(str, Enum):
    
    INBOUND = "inbound"
    OUTBOUND = "outbound"

class TaskType(str, Enum):
    PUTAWAY = "putaway"  # розміщення товару з прихідної накладної
    PICKING = "picking"  # відбір товару (для вихідних накладних)

class TaskStatus(str, Enum):
    NEW = "new"  # створено, в черзі
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELED = "canceled"

class TaskStepStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELED = "canceled"

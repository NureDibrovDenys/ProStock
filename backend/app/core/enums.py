from enum import Enum

# TODO: internationalization (i18n) and localization (i10n)
#       with gettext() or gettext_lazy(): _()

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
    INBOUND = "inbound" # Точка прийому
    OUTBOUND = "outbound" # Точка відвантаження
    GENERAL_ENTRY = "general_entry" # Основний вхід
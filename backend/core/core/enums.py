from django.db import models

# TODO: internationalization (i18n) and localization (i10n)
#       with gettext() or gettext_lazy(): _()

class RoleNameEnum(models.TextChoices):
    ROOT = 'root', 'Root'
    ADMIN = 'administrator', 'Адміністратор'
    WAREHOUSE_MANAGER = 'warehouse_manager', 'Менеджер складу'
    WORKER = 'storekeeper', 'Комірник'

class UserStatusEnum(models.TextChoices):
    ACTIVE = 'active', 'Активний'
    INACTIVE = 'inactive', 'Неактивний'
    BLOCKED = 'blocked', 'Заблокований'

class ShelfStatusEnum(models.TextChoices):
    ACTIVE = 'active', 'Активна'
    OCCUPIED = 'occupied', 'Зайнята'
    INACTIVE = 'inactive', 'Не функціонує'

class InactiveReasonEnum(models.TextChoices):
    DAMAGED = 'damaged', 'Фізичне пошкодження'
    MAINTENANCE = 'maintenance', 'Планове технічне обслуговування'
    STOCKTAKING = 'stocktaking', 'Інвентаризація'
    QUALITY_CONTROL = 'quality_control', 'Перевірка якості'
    OTHER = 'other', 'Інша причина'

class ZoneTypeEnum(models.TextChoices):
    INBOUND_DOCK = 'inbound_dock', 'Зона приймання'
    STORAGE_AREA = 'storage_area', 'Зона зберігання'
    OUTBOUND_DOCK = 'outbound_dock', 'Зона відвантаження'

class ObstacleTypeEnum(models.TextChoices):
    COLUMN = 'column', 'Колона'
    PILLAR = 'pillar', 'Стовп'
    NICHE = 'niche', 'Заглиблення'
    RESTRICTED_ZONE = 'restricted_zone', 'Зона обмеженого доступу'
    OTHER = 'other', 'Інша перешкода'

class PointTypeEnum(models.TextChoices):
    INBOUND = 'inbound', 'Точка прийома'
    OUTBOUND = 'outbound', 'Точка відвантаження'
    GENERAL_ENTRY = 'general_entry', 'Основний вхід'
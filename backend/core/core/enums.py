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
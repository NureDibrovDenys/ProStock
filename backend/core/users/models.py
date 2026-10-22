from django.db import models
from core.core.enums import RoleNameEnum, UserStatusEnum

class Role(models.Model):
    role_id = models.BigAutoField(primary_key=True)
    role_name = models.CharField(
        max_length=50,
        choices=RoleNameEnum.choices,
        unique=True
    )
    
    def __str__(self):
        return self.role_name
    
    class Meta:
        db_table = 'role'
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'

class User(models.Model):
    user_id = models.BigAutoField(primary_key=True)
    user_email = models.CharField(
        max_length=255,
        unique=True
    )
    password_hash = models.CharField(max_length=255)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    role = models.ForeignKey(
        Role,
        on_delete=models.RESTRICT,
        db_column='role_id'
    )
    status = models.CharField(
        max_length=20,
        choices=UserStatusEnum.choices,
        default=UserStatusEnum.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.user_email})"
    
    class Meta:
        db_table = 'user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
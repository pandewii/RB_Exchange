from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from .manager import CustomUserManager

# Tu importeras ZoneMonetaire depuis core.models plus tard
# from core.models import ZoneMonetaire

class CustomUser(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ('SUPERADMIN', 'SuperAdmin'),
        ('ADMIN_TECH', 'AdminTechnique'),
        ('ADMIN_ZONE', 'AdminZone'),
        ('WS_USER', 'WebServiceUser'),
    )

    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    
    zone = models.ForeignKey(
        'core.ZoneMonetaire',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['role']

    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"  # type: ignore

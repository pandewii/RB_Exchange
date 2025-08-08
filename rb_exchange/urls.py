# rb_exchange/urls.py

from django.contrib import admin
from django.urls import path, include
from authentication.views.impersonate import ImpersonateView, RevertImpersonationView
from web_interface.views.common.audit_logs import AuditLogView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # 1. Interface Web (HTMX)
    path('', include('web_interface.urls')),

    # 2. Authentification API DRF (login, logout, token/refresh)
    path('auth/', include('authentication.urls')),  

    # 3. Endpoints API métier (ex: taux de change)
    path('api/', include('api.urls')),

    # 4. Impersonation
    path('impersonate/<int:user_id>/', ImpersonateView.as_view(), name='impersonate_user'),
    path('impersonate/revert/', RevertImpersonationView.as_view(), name='revert_impersonation'),

    # 5. Audit logs & notifications
    path('audit-logs/', AuditLogView.as_view(), name='audit_logs'),
    # 6. Documentation
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
   
]

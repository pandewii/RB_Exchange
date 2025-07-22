# rb_exchange/urls.py

from django.contrib import admin
from django.urls import path, include

# NOUVEL AJOUT : Importer la vue d'impersonation (déjà fait)
from authentication.views.impersonate import ImpersonateView, RevertImpersonationView
# NOUVEL AJOUT : Importer les vues d'audit log
from web_interface.views.common.audit_logs import AuditLogView, MarkUINotificationReadView


urlpatterns = [
    path('admin/', admin.site.urls),
    
    # URLs de l'interface web (login/logout/dashboards)
    path('', include('web_interface.urls')), 

    # URLs pour l'impersonation (déjà fait)
    path('impersonate/<int:user_id>/', ImpersonateView.as_view(), name='impersonate_user'),
    path('revert/', RevertImpersonationView.as_view(), name='revert_impersonation'),

    # NOUVEL AJOUT : URL pour la vue d'audit log
    path('audit-logs/', AuditLogView.as_view(), name='audit_logs'),
    # NOUVEL AJOUT : URL pour marquer les notifications UI comme lues
    path('notifications/read/<int:pk>/', MarkUINotificationReadView.as_view(), name='mark_notification_read'),
]
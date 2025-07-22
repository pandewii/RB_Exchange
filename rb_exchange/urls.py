from django.contrib import admin
from django.urls import path, include
from authentication.views.impersonate import ImpersonateView, RevertImpersonationView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('api/auth/', include('authentication.urls')),
    
    # Cette ligne est cruciale : elle pointe vers le fichier "aiguilleur" de l'étape 2
    path('', include('web_interface.urls')), 

    path('impersonate/<int:user_id>/', ImpersonateView.as_view(), name='impersonate_user'),
    path('revert/', RevertImpersonationView.as_view(), name='revert_impersonation'),
]
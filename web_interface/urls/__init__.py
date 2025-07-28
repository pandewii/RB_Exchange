from django.urls import path, include
# L'import correct : on prend index_view et login_view depuis le même fichier
from web_interface.views.login import index_view, login_view
from web_interface.views.logout import logout_view

urlpatterns = [
    # Routes principales
    path('', index_view, name='index'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    
    # On inclut les URLs de chaque rôle avec un préfixe
    path('superadmin/', include('web_interface.urls.superadmin')),
    path('admin-tech/', include('web_interface.urls.admin_technique')),
    path('admin-zone/', include('web_interface.urls.admin_zone')),
]

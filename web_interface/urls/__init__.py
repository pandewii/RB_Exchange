# web_interface/urls.py

from django.urls import path, include
from web_interface.views import login, logout

urlpatterns = [
    # URLs de base pour la connexion/déconnexion
    path('', login.index_view, name='index'),
    path('login/', login.login_view, name='login'),
    path('logout/', logout.logout_view, name='logout'),

    # On branche ici les URLs de chaque rôle
    path('superadmin/', include('web_interface.urls.superadmin')),
    path('admin-tech/', include('web_interface.urls.admin_technique')),
    path('admin-zone/', include('web_interface.urls.admin_zone')),
]

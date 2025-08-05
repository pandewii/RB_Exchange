# web_interface/urls.py (This is the __init__.py in web_interface/urls/)

from django.urls import path, include
from web_interface.views import login
from web_interface.views import logout # Import the logout module from web_interface.views

urlpatterns = [
    # URLs de base pour la connexion/déconnexion
    path('', login.index_view, name='index'),
    path('login/', login.login_view, name='login'),
    path('logout/', logout.logout_view, name='logout'), # Point to the web_interface.views.logout_view

    # On branche ici les URLs de chaque rôle
    path('superadmin/', include('web_interface.urls.superadmin')),
    path('admin-tech/', include('web_interface.urls.admin_technique')),
    path('admin-zone/', include('web_interface.urls.admin_zone')),
]
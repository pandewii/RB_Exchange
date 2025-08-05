# authentication/urls.py

from django.urls import path
from .views.login import LoginView
from .views.logout import APILogoutView # Only APILogoutView remains
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView,
)
from authentication.views.impersonate_helper import impersonate_login_helper # NEW IMPORT


urlpatterns = [
    path('login/', LoginView.as_view(), name='api_login'),
    path('api-logout/', APILogoutView.as_view(), name='api_logout'), 
    # REMOVED: path('logout/', WebLogoutView.as_view(), name='logout'), # This path must be removed
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('impersonate/login_helper/', impersonate_login_helper, name='impersonate_login_helper'), # NEW PATH

    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
]
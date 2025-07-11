from django.urls import path
from .views.login import LoginView
from .views.logout import LogoutView
from rest_framework_simplejwt.views import (
    TokenRefreshView,    # Pour rafraîchir le access_token
    TokenVerifyView,     # Pour vérifier la validité d'un token
)


urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
]
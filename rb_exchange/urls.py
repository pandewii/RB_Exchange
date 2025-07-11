from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('api/auth/', include('authentication.urls')),
    
    # Cette ligne est cruciale : elle pointe vers le fichier "aiguilleur" de l'étape 2
    path('', include('web_interface.urls')), 
]
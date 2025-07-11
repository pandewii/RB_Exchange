from django.urls import path
from web_interface.views.superadmin import (
    dashboard, 
    add_admin, 
    edit_admin, 
    delete_admin, # Importation de la classe DeleteAdminView
    toggle_admin,
    add_consumer
)

urlpatterns = [
    path('', dashboard.dashboard_view, name='superadmin_dashboard'),
    path('add-admin-form/', add_admin.add_admin_view, name='superadmin_add_admin_view'),
    path('add-consumer-form/', add_consumer.add_consumer_view, name='superadmin_add_consumer_view'),
    path('edit-admin-form/<int:pk>/', edit_admin.edit_admin_view, name='superadmin_edit_admin_view'),
    # CORRECTION: Utiliser .as_view() pour la classe DeleteAdminView
    path('delete-admin-form/<int:pk>/', delete_admin.DeleteAdminView.as_view(), name='superadmin_delete_admin_view'),
    path('toggle-admin/<int:pk>/', toggle_admin.toggle_admin_view, name='superadmin_toggle_admin'),
]
# web_interface/urls/admin_technique.py

from django.urls import path
from web_interface.views.admin_technique import (
    dashboard, 
    add_zone, 
    delete_zone, 
    toggle_zone, # Importation de la classe
    zone_detail,
    manage_source,
    delete_source,
    manage_alias,
    manage_schedule,
    delete_schedule # Importation de la classe
)

urlpatterns = [
    path('', dashboard.dashboard_view, name='admin_technique_dashboard'),
    path('add-zone/', add_zone.AddZoneView.as_view(), name='admin_technique_add_zone'),
    path('delete-zone/<int:pk>/', delete_zone.DeleteZoneView.as_view(), name='admin_technique_delete_zone'),
    # CORRECTION: Utiliser .as_view() pour la classe ToggleZoneView
    path('toggle-zone/<int:pk>/', toggle_zone.ToggleZoneView.as_view(), name='admin_technique_toggle_zone'),
    path('zone/<int:pk>/', zone_detail.ZoneDetailView.as_view(), name='admin_technique_zone_detail'),
    path('zone/<int:pk>/manage-source/', manage_source.ManageSourceView.as_view(), name='admin_technique_manage_source'),
    path('delete-source/<int:pk>/', delete_source.DeleteSourceView.as_view(), name='admin_technique_delete_source'),
    path('manage-alias/<int:raw_currency_id>/', manage_alias.ManageAliasView.as_view(), name='admin_technique_manage_alias'),
    path('manage-schedule/<int:source_id>/', manage_schedule.ManageScheduleView.as_view(), name='admin_technique_manage_schedule'),
    # CORRECTION: Utiliser .as_view() pour la classe DeleteScheduleView
    path('delete-schedule/<int:source_id>/', delete_schedule.DeleteScheduleView.as_view(), name='admin_technique_delete_schedule'),
]

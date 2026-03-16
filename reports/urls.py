from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.reports_index, name="index"),
    path("tickets/", views.ticket_report, name="ticket_report"),
    path("asset-inventory/", views.asset_inventory_report, name="asset_inventory"),
    path(
        "assets-by-department/",
        views.assets_by_department_report,
        name="assets_by_department",
    ),
    path(
        "assets-by-location/",
        views.assets_by_location_report,
        name="assets_by_location",
    ),
    path("assigned-assets/", views.assigned_assets_report, name="assigned_assets"),
    path("maintenance/", views.maintenance_report, name="maintenance_report"),
    path("software-inventory/", views.software_inventory_report, name="software_inventory"),
    path("depreciation/", views.depreciation_report, name="depreciation_report"),
    path("audit/", views.audit_report, name="audit_report"),
]

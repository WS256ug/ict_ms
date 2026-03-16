from django.urls import path

from . import views

app_name = "tickets"

urlpatterns = [
    path("", views.ticket_list, name="ticket_list"),
    path("create/", views.ticket_create, name="ticket_create"),
    path("asset-field/", views.ticket_asset_field, name="ticket_asset_field"),
    path("<int:pk>/workflow/", views.ticket_workflow_panel, name="ticket_workflow_panel"),
    path("<int:pk>/workflow/update/", views.ticket_workflow_update, name="ticket_workflow_update"),
    path("<int:pk>/resolution/", views.ticket_resolution_panel, name="ticket_resolution_panel"),
    path("<int:pk>/resolution/update/", views.ticket_resolution_update, name="ticket_resolution_update"),
    path("<int:pk>/comments/", views.ticket_comments_panel, name="ticket_comments_panel"),
    path("<int:pk>/", views.ticket_detail, name="ticket_detail"),
    path("<int:pk>/update/", views.ticket_update, name="ticket_update"),
    path("<int:pk>/comments/create/", views.ticket_comment_create, name="ticket_comment_create"),
    path("<int:pk>/attachments/", views.ticket_attachment_panel, name="ticket_attachment_panel"),
    path("<int:pk>/attachments/upload/", views.ticket_attachment_upload, name="ticket_attachment_upload"),
    path("<int:pk>/create-maintenance/", views.ticket_create_maintenance, name="ticket_create_maintenance"),
]

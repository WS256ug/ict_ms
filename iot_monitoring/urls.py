from django.urls import path

from . import views

app_name = "iot_monitoring"

urlpatterns = [
    path("gps/ingest/", views.gps_ingest, name="gps_ingest"),
]

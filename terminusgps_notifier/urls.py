from django.urls import path

from . import views

app_name = "terminusgps_notifier"
urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("contact/", views.contact, name="contact"),
    path("source/", views.source_code, name="source"),
    path("terms/", views.terms, name="terms"),
    path("privacy/", views.privacy, name="privacy"),
    path(
        "notifications/<int:resource_id>/list/",
        views.list_notification,
        name="list notification",
    ),
    path(
        "notifications/<int:resource_id>/<int:notification_id>/details/",
        views.detail_notification,
        name="detail notification",
    ),
    path(
        "notifications/create/",
        views.create_notification,
        name="create notification",
    ),
    path(
        "notifications/resources/select/",
        views.select_resource,
        name="select resource",
    ),
    path(
        "notifications/units/select/", views.select_units, name="select units"
    ),
    path(
        "notifications/triggers/parameters/",
        views.trigger_parameters,
        name="trigger parameters",
    ),
    path("wialon/callback/", views.wialon_callback, name="wialon callback"),
    path("wialon/login/", views.wialon_login, name="wialon login"),
    path("v3/health/", views.HealthCheckView.as_view(), name="health check"),
    path(
        "v3/notify/<str:method>/",
        views.NotificationDispatchView.as_view(),
        name="notify",
    ),
]

from django.urls import path

from . import views

app_name = "terminusgps_notifier"
urlpatterns = [
    path(
        "",
        views.HtmxTemplateView.as_view(
            template_name="terminusgps_notifier/home.html"
        ),
        name="home",
    ),
    path(
        "dashboard/",
        views.ProtectedHtmxTemplateView.as_view(
            template_name="terminusgps_notifier/dashboard.html"
        ),
        name="dashboard",
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
        "notifications/actions/select/",
        views.select_action,
        name="select action",
    ),
    path(
        "notifications/triggers/select/",
        views.select_trigger,
        name="select triggers",
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

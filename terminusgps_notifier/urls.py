from django.urls import path
from django.views.generic import RedirectView

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
    path("v3/health/", views.HealthCheckView.as_view(), name="health check"),
    path(
        "v3/notify/<str:method>/",
        views.NotificationDispatchView.as_view(),
        name="notify",
    ),
    path(
        "dashboard/",
        views.ProtectedHtmxTemplateView.as_view(
            template_name="terminusgps_notifier/dashboard.html"
        ),
        name="dashboard",
    ),
    path(
        "wialon/callback/",
        views.WialonCallbackView.as_view(
            template_name="terminusgps_notifier/wialon_callback.html"
        ),
        name="wialon callback",
    ),
    path(
        "wialon/login/",
        RedirectView.as_view(
            url="https://hosting.terminusgps.com/login.html", query_string=True
        ),
        name="wialon login",
    ),
    path(
        "notifications/create/",
        views.WialonNotificationCreateView.as_view(
            template_name="terminusgps_notifier/wialonnotification_create.html"
        ),
        name="create notifications",
    ),
    path(
        "notifications/list/",
        views.WialonNotificationListView.as_view(
            template_name="terminusgps_notifier/wialonnotification_list.html"
        ),
        name="list notifications",
    ),
    path(
        "messages/count/",
        views.CustomerMessageCountView.as_view(
            template_name="terminusgps_notifier/messages_count.html"
        ),
        name="messages count",
    ),
]

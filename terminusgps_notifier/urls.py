from django.urls import path

from . import views

app_name = "terminusgps_notifier"
urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.TerminusGPSNotifierLoginView.as_view(), name="login"),
    path(
        "logged_out/",
        views.TerminusGPSNotifierLogoutView.as_view(),
        name="logout",
    ),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("contact/", views.contact, name="contact"),
    path("source/", views.source_code, name="source"),
    path("terms/", views.terms, name="terms"),
    path("privacy/", views.privacy, name="privacy"),
    path("resources/list/", views.list_resources, name="list resources"),
    path(
        "resources/<str:resource_id>/details/",
        views.detail_resources,
        name="detail resources",
    ),
    path(
        "notifications/<str:resource_id>/create/",
        views.create_notification,
        name="create notification",
    ),
    path(
        "subscriptions/create/",
        views.create_subscription,
        name="create subscription",
    ),
    path(
        "billing-portal/<str:customer_id>/",
        views.billing_portal,
        name="billing portal",
    ),
    path("wialon/login/", views.wialon_login, name="wialon login"),
    path("v3/health/", views.HealthCheckView.as_view(), name="health check"),
    path(
        "v3/notify/<str:method>/",
        views.NotificationDispatchView.as_view(),
        name="notify",
    ),
]

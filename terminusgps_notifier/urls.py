from django.urls import path

from . import views

app_name = "terminusgps_notifier"
urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register_form, name="register"),
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
    path("resources/select/", views.select_resources, name="select resources"),
    path("resources/list/", views.list_resources, name="list resources"),
    path(
        "resources/<int:resource_id>/details/",
        views.detail_resources,
        name="detail resources",
    ),
    path(
        "notifications/<int:resource_id>/<int:notification_id>/details/",
        views.detail_notifications,
        name="detail notifications",
    ),
    path(
        "units/<int:resource_id>/select/",
        views.select_units,
        name="select units",
    ),
    path(
        "triggers/parameters/",
        views.trigger_parameters,
        name="trigger parameters",
    ),
    path("units/<int:resource_id>/form/", views.units_form, name="units form"),
    path(
        "triggers/<int:resource_id>/form/",
        views.trigger_form,
        name="trigger form",
    ),
    path(
        "notifications/<int:resource_id>/create/",
        views.create_notifications,
        name="create notifications",
    ),
    path(
        "units/<int:unit_id>/details/", views.detail_units, name="detail units"
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

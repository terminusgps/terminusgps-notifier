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
    path("select-resources/", views.select_resources, name="select resources"),
    path("list-resources/", views.list_resources, name="list resources"),
    path(
        "detail-resources/<int:resource_id>/",
        views.detail_resources,
        name="detail resources",
    ),
    path(
        "detail-notifications/<int:resource_id>/<int:notification_id>/",
        views.detail_notifications,
        name="detail notifications",
    ),
    path(
        "select-units/<int:resource_id>/units/select/",
        views.select_units,
        name="select units",
    ),
    path(
        "trigger-parameters",
        views.trigger_parameters,
        name="trigger parameters",
    ),
    path("units-form/<int:resource_id>/", views.units_form, name="units form"),
    path(
        "trigger-form/<int:resource_id>/",
        views.trigger_form,
        name="trigger form",
    ),
    path(
        "create-notifications/<int:resource_id>/",
        views.create_notifications,
        name="create notifications",
    ),
    path(
        "detail-units/<int:unit_id>/", views.detail_units, name="detail units"
    ),
    path("checkout/", views.checkout, name="checkout"),
    path("checkout/success/", views.checkout_success, name="checkout success"),
    path(
        "detail-subscriptions/<str:subscription_id>/",
        views.detail_subscription,
        name="detail subscription",
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

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
    path("resources/select/", views.select_resources, name="select resources"),
    path("resources/list/", views.list_resources, name="list resources"),
    path(
        "resources/<int:resource_id>/details/",
        views.detail_resources,
        name="detail resources",
    ),
    path(
        "notifications/<int:resource_id>/<int:notification_id>/",
        views.detail_notifications,
        name="detail notifications",
    ),
    path(
        "resources/<int:resource_id>/units/select/",
        views.select_units,
        name="select units",
    ),
    path(
        "triggers/parameters/",
        views.trigger_parameters,
        name="trigger parameters",
    ),
    path(
        "resources/<int:resource_id>/units/form/",
        views.units_form,
        name="units form",
    ),
    path(
        "resources/<int:resource_id>/trigger/form/",
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
        "subscriptions/<int:subscription_id>/details/",
        views.detail_subscription,
        name="detail subscription",
    ),
    path("forms/address/", views.address_form, name="address form"),
    path("forms/payment/", views.payment_form, name="payment form"),
    path("payments/new/", views.save_payment, name="save payment"),
    path("wialon/callback/", views.wialon_callback, name="wialon callback"),
    path("wialon/login/", views.wialon_login, name="wialon login"),
    path("v3/health/", views.HealthCheckView.as_view(), name="health check"),
    path(
        "v3/notify/<str:method>/",
        views.NotificationDispatchView.as_view(),
        name="notify",
    ),
]

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
    path("units/select/", views.select_units, name="select units"),
    path("resources/select/", views.select_resources, name="select resources"),
    path("resources/list/", views.list_resources, name="list resources"),
    path(
        "resources/<str:resource_id>/details/",
        views.detail_resources,
        name="detail resources",
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
    path(
        "notifications/create/step-one/",
        views.create_notification_step_one,
        name="create notification step one",
    ),
    path(
        "notifications/create/step-two/",
        views.create_notification_step_two,
        name="create notification step two",
    ),
    path(
        "notifications/create/step-three/",
        views.create_notification_step_three,
        name="create notification step three",
    ),
    path(
        "notifications/create/step-four/",
        views.create_notification_step_four,
        name="create notification step four",
    ),
    path(
        "notifications/create/review/",
        views.create_notification_step_review,
        name="create notification step review",
    ),
    path(
        "forms/triggers/parameters/",
        views.trigger_parameters_form,
        name="trigger parameters form",
    ),
    path("wialon/login/", views.wialon_login, name="wialon login"),
    path("v3/health/", views.HealthCheckView.as_view(), name="health check"),
    path(
        "v3/notify/<str:method>/",
        views.NotificationDispatchView.as_view(),
        name="notify",
    ),
]

from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.HealthCheckView.as_view(), name="health check"),
    path(
        "notify/<str:method>/",
        views.DispatchNotificationView.as_view(),
        name="notify",
    ),
]

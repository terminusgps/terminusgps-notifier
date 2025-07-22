from django.urls import path

from . import views

urlpatterns = [
    path("", views.CheckHealthView.as_view(), name="check health"),
    path(
        "v3/notify/<str:method>/",
        views.DispatchNotificationView.as_view(),
        name="notify",
    ),
]

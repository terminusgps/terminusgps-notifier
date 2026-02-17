from django.urls import path

from . import models, views

urlpatterns = [
    path("health/", views.HealthCheckView.as_view(), name="health check"),
    path(
        "notify/<str:method>/",
        views.NotificationDispatchView.as_view(),
        name="notify",
    ),
    path(
        "units/<int:resource_id>/list/",
        views.WialonObjectListView.as_view(model=models.WialonUnit),
        name="list wialon units",
    ),
    path(
        "unit-groups/<int:resource_id>/list/",
        views.WialonObjectListView.as_view(model=models.WialonUnitGroup),
        name="list wialon unit groups",
    ),
]

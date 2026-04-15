from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "payments/",
        include("terminusgps_payments.urls", namespace="terminusgps_payments"),
    ),
    path(
        "",
        include("terminusgps_notifier.urls", namespace="terminusgps_notifier"),
    ),
]

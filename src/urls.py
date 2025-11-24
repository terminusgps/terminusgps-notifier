from django.urls import include, path

urlpatterns = [path("v3/", include("terminusgps_notifier.urls"))]

from django.urls import path

from . import views

urlpatterns = [
    path(
        "notify/<str:method>/", views.DispatchNotificationView.as_view(), name="notify"
    )
]

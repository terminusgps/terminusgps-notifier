import logging

from django.http import HttpRequest, HttpResponse
from django.views.generic import View

from .forms import NotificationDispatchForm

logger = logging.getLogger(__name__)


class HealthCheckView(View):
    content_type = "text/plain"
    http_method_names = ["get"]

    async def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Responds with status code 200."""
        return HttpResponse("I'm alive\n".encode("utf-8"), status=200)


class NotificationDispatchView(View):
    content_type = "text/plain"
    http_method_names = ["get"]

    async def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """
        Dispatches a notification based on path parameters.

        Returns 200 if notifications were successfully dispatched or the unit didn't have phone numbers.

        Returns 4XX in any other case.

        """
        # Validate user input
        form = NotificationDispatchForm(request.GET)
        if not form.is_valid():
            return HttpResponse(
                "Bad notification parameters\n".encode("utf-8"), status=406
            )
        return HttpResponse(status=200)

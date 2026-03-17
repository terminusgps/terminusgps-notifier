import asyncio
import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.http.response import sync_to_async
from django.views.generic import View
from terminusgps.wialon.session import WialonSession

from terminusgps_notifier.dispatchers import (
    AWSNotificationDispatcher,
    TwilioNotificationDispatcher,
)
from terminusgps_notifier.forms import NotificationDispatchForm
from terminusgps_notifier.validators import validate_e164_phone_number
from terminusgps_notifier.wialon import get_phone_numbers

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

    @staticmethod
    @sync_to_async
    def clean_phones(phones: list[str]) -> list[str]:
        cleaned = []
        for phone in phones:
            try:
                validate_e164_phone_number(phone)
                cleaned.append(phone)
            except ValidationError:
                logger.warning(f"Improperly formatted phone number: {phone}")
                continue
        return cleaned

    async def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """
        Dispatches a notification based on path parameters.

        Returns 200 if notifications were successfully dispatched or the unit didn't have phone numbers.

        Returns 502 if all notification dispatchers fail to deliver notifications.

        Returns 4XX in any other case.

        """
        if self.kwargs["method"] not in ("sms", "voice"):
            msg = f"Invalid method: '{self.kwargs['method']}'\n"
            logger.error(msg.removesuffix("\n"))
            return HttpResponse(msg.encode("utf-8"), status=404)
        form = NotificationDispatchForm(request.GET)
        if not form.is_valid():
            msg = "Bad notification parameters\n"
            logger.error(msg.removesuffix("\n"))
            return HttpResponse(msg.encode("utf-8"), status=406)
        with WialonSession(token=settings.WIALON_TOKEN) as session:
            dirty_phones = await get_phone_numbers(form, session)
            if not dirty_phones:
                msg = f"No destination phone numbers retrieved for unit #{form.cleaned_data['unit_id']}\n"
                logger.info(msg.removesuffix("\n"))
                return HttpResponse(msg.encode("utf-8"), status=200)
            target_phones = await self.clean_phones(dirty_phones)

        dispatchers = [
            AWSNotificationDispatcher(form),
            TwilioNotificationDispatcher(form),
        ]
        method = self.kwargs["method"]
        for dispatcher in dispatchers:
            tasks = [
                dispatcher.send_notification(to_number=phone, method=method)
                for phone in target_phones
            ]
            try:
                await asyncio.gather(*tasks)
                logger.info(f"Dispatched via {type(dispatcher).__name__}")
                return HttpResponse(status=200)
            except Exception as error:
                logger.warning(f"{type(dispatcher).__name__} failed: {error}")
        logger.error(f"All dispatchers failed for method '{method}'")
        return HttpResponse(status=502)

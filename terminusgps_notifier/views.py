import asyncio
import logging
from datetime import datetime

import aioboto3
from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.http.response import sync_to_async
from django.template.loader import render_to_string
from django.utils.translation import ngettext
from django.views.generic import View
from terminusgps.wialon.session import WialonSession

from terminusgps_notifier.forms import NotificationDispatchForm
from terminusgps_notifier.pinpoint import dispatch_notification
from terminusgps_notifier.validators import validate_e164_phone_number
from terminusgps_notifier.wialon import get_phone_numbers

logger = logging.getLogger(__name__)


@sync_to_async
def render_notification_message(
    form: NotificationDispatchForm, date_format: str = "%Y-%m-%d %H:%M:%S"
) -> str:
    date = datetime.utcfromtimestamp(form.cleaned_data["msg_time_int"])
    return render_to_string(
        "terminusgps_notifier/message.txt",
        context={
            "date": date.strftime(date_format),
            "base": form.cleaned_data["message"],
            "location": form.cleaned_data.get("location"),
            "unit_name": form.cleaned_data.get("unit_name"),
        },
    ).removesuffix("\n")


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
        # Validate method
        if self.kwargs["method"] not in ("sms", "voice"):
            msg = f"Invalid method: '{self.kwargs['method']}'\n"
            logger.error(msg.removesuffix("\n"))
            return HttpResponse(msg.encode("utf-8"), status=404)

        # Validate path parameters
        form = NotificationDispatchForm(request.GET)
        if not form.is_valid():
            msg = "Bad notification parameters\n"
            logger.error(msg.removesuffix("\n"))
            return HttpResponse(msg.encode("utf-8"), status=406)

        # Retrieve target phone numbers from Wialon api
        with WialonSession(token=settings.WIALON_TOKEN) as session:
            phones = await get_phone_numbers(form, session)
            # Early 200 if no phones were returned from Wialon api
            if not phones:
                msg = f"No phones retrieved for unit #{form.cleaned_data['unit_id']}\n"
                logger.info(msg.removesuffix("\n"))
                return HttpResponse(msg.encode("utf-8"), status=200)
            # Clean phone numbers before passing them in boto3 api calls
            for phone in phones:
                try:
                    validate_e164_phone_number(phone)
                except ValidationError:
                    phones.remove(phone)

        # Render end-user message
        date_fmt = "%Y-%m-%d %H:%M:%S"
        message = await render_notification_message(form, date_fmt)
        async with aioboto3.Session().client(
            "pinpoint-sms-voice-v2", region_name="us-east-1"
        ) as client:
            # Login to AWS and dispatch notifications
            responses = await asyncio.gather(
                *[
                    dispatch_notification(
                        to_number=to_number,
                        message=message,
                        method=self.kwargs["method"],
                        client=client,
                        dry_run=form.cleaned_data["dry_run"],
                    )
                    for to_number in phones
                ]
            )

        # Count up how many notifications were dispatched
        num_messages = len([msg.get("MessageId") for msg in responses])
        # Return 200
        msg = f"Sent {num_messages} {ngettext('message', 'messages', num_messages)}"
        logger.info(msg)
        return HttpResponse(msg.encode("utf-8"), status=200)

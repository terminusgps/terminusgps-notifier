import asyncio
import logging
from datetime import datetime

import aioboto3
from django.core.exceptions import ValidationError
from django.db.models import F
from django.http import HttpRequest, HttpResponse
from django.http.response import sync_to_async
from django.template.loader import render_to_string
from django.utils.translation import ngettext
from django.views.generic import View
from terminusgps.wialon.session import WialonSession

from terminusgps_notifier.forms import NotificationDispatchForm
from terminusgps_notifier.models import TerminusGPSNotifierCustomer
from terminusgps_notifier.phones import get_phone_numbers
from terminusgps_notifier.pinpoint import dispatch_notification
from terminusgps_notifier.validators import validate_e164_phone_number

logger = logging.getLogger(__name__)


@sync_to_async(thread_sensitive=False)
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


async def increment_customer_messages_count(
    customer: TerminusGPSNotifierCustomer, num_messages: int
) -> None:
    if customer.messages_count < customer.messages_limit:
        customer.messages_count = F("messages_count") + num_messages
        await customer.asave(update_fields=["messages_count"])


async def increment_message_packages_count(
    customer: TerminusGPSNotifierCustomer, num_messages: int
) -> None:
    if (
        customer.messages_count < customer.messages_limit
        or await customer.packages.acount() <= 0
    ):
        return
    async for package in customer.packages.all():
        if package.count >= package.limit:
            continue
        else:
            package.count = F("count") + num_messages
            await package.asave(update_fields=["count"])
            break


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
        form = NotificationDispatchForm(request.GET)
        if not form.is_valid():
            return HttpResponse(
                "Bad notification parameters\n".encode("utf-8"), status=406
            )

        try:
            unit_id = form.cleaned_data["unit_id"]
            customer = await TerminusGPSNotifierCustomer.objects.aget(
                user__pk=unit_id
            )
        except TerminusGPSNotifierCustomer.DoesNotExist:
            msg = f"No customer for user: #{unit_id}"
            logger.error(msg)
            return HttpResponse(msg.encode("utf-8"), status=400)

        if customer.token is None:
            return HttpResponse(status=403)
        if customer.subscription is None:
            return HttpResponse(status=403)
        if customer.subscription.status != "active":
            return HttpResponse(status=403)

        with WialonSession(token=customer.token.name) as session:
            phones = await get_phone_numbers(form, session)
            if not phones:
                msg = f"No phones retrieved for unit #{unit_id}"
                logger.info(msg)
                return HttpResponse(msg.encode("utf-8"), status=200)
            for phone in phones:
                try:
                    validate_e164_phone_number(phone)
                except ValidationError:
                    phones.remove(phone)

        try:
            async with aioboto3.Session().client(
                "pinpoint-sms-voice-v2", region_name="us-east-1"
            ) as client:
                message = await render_notification_message(
                    form, "%Y-%m-%d %H:%M:%S"
                )
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
        except ValueError as error:
            logger.error(error)
            return HttpResponse(str(error).encode("utf-8"), status=400)

        num_messages = len([msg.get("MessageId") for msg in responses])
        await increment_customer_messages_count(customer, num_messages)
        await increment_message_packages_count(customer, num_messages)
        msg = f"Sent {num_messages} {ngettext('message', 'messages', num_messages)}"
        logger.info(msg)
        return HttpResponse(msg.encode("utf-8"), status=200)

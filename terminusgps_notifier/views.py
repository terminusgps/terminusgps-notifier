import asyncio
import logging

import aioboto3
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ngettext
from django.views.generic import View
from terminusgps.wialon.session import WialonSession

from .forms import WialonUnitNotificationForm
from .services import (
    get_phone_numbers,
    get_token,
    has_messages,
    has_subscription,
    increment_customer_message_count,
    increment_packages_message_count,
    render_message,
    send_notification,
)
from .validators import validate_e164_phone_number

logger = logging.getLogger(__name__)


class HealthCheckView(View):
    content_type = "text/plain"
    http_method_names = ["get"]

    async def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Responds with status code 200."""
        return HttpResponse("I'm alive".encode("utf-8"), status=200)


class DispatchNotificationView(View):
    content_type = "text/plain"
    http_method_names = ["get"]

    async def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """
        Dispatches a notification based on path parameters.

        Returns 200 if notifications were successfully dispatched or the unit didn't have phone numbers.

        Returns 4XX in any other case.

        """
        form = WialonUnitNotificationForm(request.GET)
        if not form.is_valid():
            return HttpResponse(
                "Bad notification parameters".encode("utf-8"), status=406
            )

        target_phones = []
        unit_id = form.cleaned_data["unit_id"]
        user_id = form.cleaned_data["user_id"]
        message = form.cleaned_data["message"]
        token = await get_token(user_id)

        if token is None:
            log = f"Failed to retrieve token from user id: '{user_id}'"
            logger.warning(log)
            return HttpResponse(log.encode("utf-8"), status=400)
        if not await has_subscription(user_id):
            log = f"Invalid subscription from user id: '{user_id}'"
            logger.warning(log)
            return HttpResponse(log.encode("utf-8"), status=403)
        if not await has_messages(user_id):
            log = f"Invalid message count from user id: '{user_id}'"
            logger.warning(log)
            return HttpResponse(log.encode("utf-8"), status=403)

        with WialonSession(token=token) as session:
            phones = get_phone_numbers(unit_id, session)
            if not phones:
                msg = f"No phones retrieved for unit_id: '{unit_id}'"
                logger.info(msg)
                return HttpResponse(msg.encode("utf-8"), status=200)
            for phone in phones:
                try:
                    validate_e164_phone_number(phone)
                    target_phones.append(phone)
                except ValidationError as e:
                    logger.warning(e)
                    continue

        try:
            rendered = await render_message(
                base=message,
                user_id=user_id,
                msg_time_int=form.cleaned_data["msg_time_int"],
                location=form.cleaned_data.get("location"),
                unit_name=form.cleaned_data.get("unit_name"),
            )
            async with aioboto3.Session().client(
                "pinpoint-sms-voice-v2", region_name="us-east-1"
            ) as client:
                messages_response = await asyncio.gather(
                    *[
                        send_notification(
                            to_number=phone,
                            message=rendered,
                            method=self.kwargs["method"],
                            client=client,
                            dry_run=form.cleaned_data["dry_run"],
                        )
                        for phone in target_phones
                    ]
                )

            msg_ids = [msg.get("MessageId") for msg in messages_response]
            await increment_customer_message_count(user_id, len(msg_ids))
            await increment_packages_message_count(user_id, len(msg_ids))
            msg = f"Sent {len(msg_ids)} {ngettext('message', 'messages', len(msg_ids))}: {msg_ids}"
            logger.info(msg)
            return HttpResponse(msg.encode("utf-8"), status=200)
        except ValueError as e:
            logger.warning(e)
            return HttpResponse(str(e).encode("utf-8"), status=406)

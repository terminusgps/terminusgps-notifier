import asyncio
import logging

import aioboto3
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ngettext
from django.views.generic import View
from terminusgps.wialon.session import WialonSession

from .forms import NotificationDispatchForm
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
                "Bad notification parameters".encode("utf-8"), status=406
            )

        # Check if provided user has permission to dispatch a notification
        user_id = form.cleaned_data["user_id"]
        token = await get_token(user_id)
        if token is None:
            msg = f"Failed to retrieve token for user #{user_id}."
            logger.warning(msg)
            return HttpResponse(msg.encode("utf-8"), status=400)
        if not await has_subscription(user_id):
            msg = f"Invalid subscription for user #{user_id}."
            logger.warning(msg)
            return HttpResponse(msg.encode("utf-8"), status=403)
        if not await has_messages(user_id):
            msg = f"Invalid message count for user #{user_id}."
            logger.warning(msg)
            return HttpResponse(msg.encode("utf-8"), status=403)

        # Retrieve target phones for unit from Wialon API
        target_phones = []
        with WialonSession(token=token) as session:
            unit_id = form.cleaned_data["unit_id"]
            phones = get_phone_numbers(unit_id, session)
            if not phones:
                msg = f"No phones retrieved for unit #{unit_id}."
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
            # Render notification message
            if self.kwargs["method"] not in ("sms", "voice"):
                raise ValueError(f"Invalid method: '{self.kwargs['method']}'")
            rendered = await render_message(
                base=form.cleaned_data["message"],
                user_id=user_id,
                msg_time_int=form.cleaned_data["msg_time_int"],
                location=form.cleaned_data.get("location"),
                unit_name=form.cleaned_data.get("unit_name"),
                method=self.kwargs["method"],
            )

            # Dispatch notification messages to target phones
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

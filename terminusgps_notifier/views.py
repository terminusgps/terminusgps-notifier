import asyncio
import datetime
import logging

import aioboto3
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.views.generic import View
from terminusgps.wialon.session import WialonSession

from .forms import WialonUnitNotificationForm
from .services import (
    get_date_format,
    get_phone_numbers,
    get_token,
    has_messages,
    has_subscription,
    increment_customer_message_count,
    increment_packages_message_count,
)

logger = logging.getLogger(__name__)


class HealthCheckView(View):
    content_type = "text/plain"
    http_method_names = ["get"]

    async def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Responds with status code 200."""
        return HttpResponse(b"I'm alive\n", status=200)


class DispatchNotificationView(View):
    content_type = "text/plain"
    http_method_names = ["get"]

    async def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """
        Dispatches a notification based on path parameters.

        Returns 200 if notifications were successfully dispatched.

        Returns 200 if the provided unit id didn't have attached phone numbers.

        Returns 4XX in any other case.

        """
        form = WialonUnitNotificationForm(request.GET)
        if not form.is_valid():
            return HttpResponse(b"Bad notification params\n", status=406)

        unit_id = form.cleaned_data["unit_id"]
        user_id = form.cleaned_data["user_id"]
        message = form.cleaned_data["message"]
        has_sub = await has_subscription(user_id)
        has_msg = await has_messages(user_id)
        token = await get_token(user_id)

        if not has_sub:
            err = f"Invalid subscription from user id: '{user_id}'"
            logger.warning(err)
            return HttpResponse(f"{err}\n".encode("utf-8"), status=403)
        if not has_msg:
            err = f"Invalid message count from user id: '{user_id}'"
            logger.warning(err)
            return HttpResponse(f"{err}\n".encode("utf-8"), status=403)
        if token is None:
            err = f"Failed to retrieve token from user id: '{user_id}'."
            logger.warning(err)
            return HttpResponse(f"{err}\n".encode("utf-8"), status=400)

        with WialonSession(token=token) as session:
            target_phones = get_phone_numbers(unit_id, session)
            if not target_phones:
                logger.info(f"No phones retrieved for #{unit_id}\n")
                return HttpResponse(status=200)
        try:
            constructed_message = await self.construct_message(
                base=message,
                user_id=user_id,
                msg_time_int=form.cleaned_data.get("msg_time_int"),
                location=form.cleaned_data.get("location"),
                unit_name=form.cleaned_data.get("unit_name"),
            )
            messages_response = await asyncio.gather(
                *[
                    self.send_notification(
                        to_number=phone,
                        message=constructed_message,
                        method=str(self.kwargs["method"]),
                        dry_run=form.cleaned_data["dry_run"],
                    )
                    for phone in target_phones
                ]
            )
            message_ids = [msg.get("MessageId") for msg in messages_response]
            logger.info(f"Sent messages: {message_ids}")
            await increment_customer_message_count(user_id, len(message_ids))
            logger.info(f"Incremented customer messages for user #{user_id}")
            await increment_packages_message_count(user_id, len(message_ids))
            logger.info(f"Incremented packages messages for user #{user_id}")
            return HttpResponse(status=200)
        except ValueError:
            return HttpResponse(b"Bad notification method\n", status=406)

    async def construct_message(
        self,
        base: str,
        user_id: int,
        *,
        msg_time_int: int | None = None,
        location: str | None = None,
        unit_name: str | None = None,
    ) -> str:
        """
        Returns a constructed message to be delivered to a destination phone number.

        :param base: Base message.
        :type base: str
        :param user_id: A Django user id.
        :type user_id: int
        :param msg_time_int: Message time as UNIX-timestamp. Default is :py:obj:`None`.
        :type msg_time_int: int | None
        :param location: Location of the notification trigger. Default is :py:obj:`None`.
        :type location: str | None
        :param unit_name: Name of the triggering unit. Default is :py:obj:`None`.
        :type unit_name: str | None
        :returns: A constructed notification message.
        :rtype: str

        """
        msg_parts: list[str] = []
        if msg_time_int:
            date_fmt = await get_date_format(user_id)
            msg_time = datetime.datetime.utcfromtimestamp(msg_time_int)
            msg_parts.append(f"[{msg_time.strftime(date_fmt)}]")
        if location:
            msg_parts.append(f"[{location}]")
        if unit_name:
            msg_parts.append(f"[{unit_name}]")
        return (
            " ".join(msg_parts + [f"{base}"])
            if any([unit_name, msg_time_int, location])
            else base
        )

    async def send_notification(
        self, to_number: str, message: str, method: str, dry_run: bool = False
    ) -> dict[str, str] | None:
        """
        Sends a notification to ``to_number`` via ``method``.

        :param to_number: Destination (target) phone number.
        :type to_number: str
        :param message: Notification message.
        :type message: str
        :param method: Notification method. Options are ``sms`` or ``voice``.
        :type method: str
        :param dry_run: Whether to execute the API call as a dry run. Default is :py:obj:`False`.
        :type dry_run: bool
        :raises ValueError: If the method was invalid.
        :returns: A dictionary of message ids.
        :rtype: dict[str, str] | None

        """
        logger.info(f"Sending '{message}' to '{to_number}' via {method}...")
        match method:
            case "sms":
                return await self._send_sms_message(
                    to_number, message, dry_run=dry_run
                )
            case "voice":
                return await self._send_voice_message(
                    to_number, message, dry_run=dry_run
                )
            case _:
                raise ValueError(f"Invalid method: '{method}'")

    async def _send_sms_message(
        self,
        to_number: str,
        message: str,
        ttl: int = 300,
        region_name: str = "us-east-1",
        dry_run: bool = False,
    ) -> dict[str, str] | None:
        """
        Sends ``message`` to ``to_number`` via sms.

        :param to_number: Destination phone number.
        :type to_number: str
        :param message: A message to deliver to the destination phone number via sms.
        :type message: str
        :param ttl: Time to live in seconds. Default is ``300`` seconds.
        :type ttl: int
        :param region_name: An AWS region to use for the message dispatch. Default is ``"us-east-1"``.
        :type region_name: str
        :param dry_run: Whether to execute the API call as a dry run. Default is :py:obj:`False`.
        :type dry_run: bool
        :returns: A dictionary containing the PinpointSMSVoiceV2 message id.
        :rtype: dict[str, str] | None

        """
        async with aioboto3.Session().client(
            "pinpoint-sms-voice-v2", region_name=region_name
        ) as client:
            return await client.send_text_message(
                **{
                    "DestinationPhoneNumber": to_number,
                    "OriginationIdentity": settings.AWS_PINPOINT_POOL_ARN,
                    "MessageBody": message,
                    "MessageType": "TRANSACTIONAL",
                    "ConfigurationSetName": settings.AWS_PINPOINT_CONFIGURATION_ARN,
                    "MaxPrice": settings.AWS_PINPOINT_MAX_PRICE_SMS,
                    "TimeToLive": ttl,
                    "DryRun": dry_run,
                    "ProtectConfigurationId": settings.AWS_PINPOINT_PROTECT_ID,
                }
            )

    async def _send_voice_message(
        self,
        to_number: str,
        message: str,
        message_type: str = "TEXT",
        voice_id: str = "MATTHEW",
        region_name: str = "us-east-1",
        dry_run: bool = False,
    ) -> dict[str, str] | None:
        """
        Sends ``message`` to ``to_number`` via voice.

        :param to_number: Destination phone number.
        :type to_number: str
        :param message: A message to read aloud to the destination phone number via voice.
        :type message: str
        :param message_type: An AWS End User Messaging message type. Default is ``"TEXT"``.
        :type message_type: str
        :param voice_id: An AWS End User Messaging synthetic voice id. Default is ``"MATTHEW"``.
        :type voice_id: str
        :param region_name: An AWS region to use for the message dispatch. Default is ``"us-east-1"``.
        :type region_name: str
        :param dry_run: Whether to execute the API call as a dry run. Default is :py:obj:`False`.
        :type dry_run: bool
        :returns: A dictionary containing the PinpointSMSVoiceV2 message id.
        :rtype: dict[str, str] | None

        """
        async with aioboto3.Session().client(
            "pinpoint-sms-voice-v2", region_name=region_name
        ) as client:
            return await client.send_voice_message(
                **{
                    "DestinationPhoneNumber": to_number,
                    "OriginationIdentity": settings.AWS_PINPOINT_POOL_ARN,
                    "MessageBody": message,
                    "MessageBodyTextType": message_type,
                    "VoiceId": voice_id,
                    "ConfigurationSetName": settings.AWS_PINPOINT_CONFIGURATION_ARN,
                    "MaxPricePerMinute": settings.AWS_PINPOINT_MAX_PRICE_VOICE,
                    "DryRun": dry_run,
                    "ProtectConfigurationId": settings.AWS_PINPOINT_PROTECT_ID,
                }
            )

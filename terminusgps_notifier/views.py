import asyncio
import logging

import aioboto3
from django.conf import ImproperlyConfigured, settings
from django.http import HttpRequest, HttpResponse
from django.views.generic import View

from .forms import WialonUnitNotificationForm
from .services import get_phone_numbers

logger = logging.getLogger(__name__)


REQUIRED_SETTINGS = [
    "AWS_PINPOINT_CONFIGURATION_ARN",
    "AWS_PINPOINT_MAX_PRICE_SMS",
    "AWS_PINPOINT_MAX_PRICE_VOICE",
    "AWS_PINPOINT_POOL_ARN",
    "AWS_PINPOINT_PROTECT_ID",
]

for setting in REQUIRED_SETTINGS:
    if not hasattr(settings, setting):
        raise ImproperlyConfigured(f"'{setting}' setting is required.")


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

        Returns 406 if the unit id, message or method was invalid.

        """
        form = WialonUnitNotificationForm(request.GET)
        if not form.is_valid():
            return HttpResponse(b"Bad notification params\n", status=406)

        unit_id = str(form.cleaned_data["unit_id"])
        message = str(form.cleaned_data["message"])
        dry_run = bool(form.cleaned_data["dry_run"])
        # TODO: retrieve token from db instead of settings
        target_phones = get_phone_numbers(unit_id, settings.WIALON_TOKEN)
        if not target_phones:
            logger.info(f"No phones retrieved for #{unit_id}\n")
            return HttpResponse(status=200)

        try:
            method = str(self.kwargs["method"])
            message_ids = await asyncio.gather(
                *[
                    self.send_notification(phone, message, method, dry_run)
                    for phone in target_phones
                ]
            )
            logger.info(f"Sent messages: '{message_ids}'.")
            return HttpResponse(status=200)
        except ValueError:
            return HttpResponse(b"Bad notification method\n", status=406)

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
        :raises ValueError: If the notification method was invalid.
        :returns: .
        :rtype: None

        """
        match method:
            case "sms":
                return await self._send_sms_message(
                    to_number, message, dry_run
                )
            case "voice":
                return await self._send_voice_message(
                    to_number, message, dry_run
                )
            case _:
                raise ValueError(f"Invalid method: '{method}'")

    async def _send_sms_message(
        self, to_number: str, message: str, dry_run: bool = False
    ) -> dict[str, str] | None:
        """
        Sends ``message`` to ``to_number`` via sms.

        :param to_number: Destination phone number.
        :type to_number: str
        :param message: A message to deliver to the destination phone number via sms.
        :type message: str
        :param dry_run: Whether or not to execute the API call as a dry run. Default is :py:obj:`False`.
        :type dry_run: bool
        :returns: A dictionary containing the PinpointSMSVoiceV2 message id.
        :rtype: dict[str, str] | None

        """
        async with aioboto3.Session().client(
            "pinpoint-sms-voice-v2"
        ) as client:
            return await client.send_text_message(
                **{
                    "DestinationPhoneNumber": to_number,
                    "OriginationIdentity": settings.AWS_PINPOINT_POOL_ARN,
                    "MessageBody": message,
                    "MessageType": "TRANSACTIONAL",
                    "ConfigurationSetName": settings.AWS_PINPOINT_CONFIGURATION_ARN,
                    "MaxPrice": settings.AWS_PINPOINT_MAX_PRICE_SMS,
                    "TimeToLive": 300,
                    "DryRun": dry_run,
                    "ProtectConfigurationId": settings.AWS_PINPOINT_PROTECT_ID,
                }
            )

    async def _send_voice_message(
        self, to_number: str, message: str, dry_run: bool = False
    ) -> dict[str, str] | None:
        """
        Sends ``message`` to ``to_number`` via voice.

        :param to_number: Destination phone number.
        :type to_number: str
        :param message: A message to read aloud to the destination phone number via voice.
        :type message: str
        :param dry_run: Whether or not to execute the API call as a dry run. Default is :py:obj:`False`.
        :type dry_run: bool
        :returns: A dictionary containing the PinpointSMSVoiceV2 message id.
        :rtype: dict[str, str] | None

        """
        async with aioboto3.Session().client(
            "pinpoint-sms-voice-v2"
        ) as client:
            return await client.send_voice_message(
                **{
                    "DestinationPhoneNumber": to_number,
                    "OriginationIdentity": settings.AWS_PINPOINT_POOL_ARN,
                    "MessageBody": message,
                    "MessageBodyTextType": "TEXT",
                    "VoiceId": "MATTHEW",
                    "ConfigurationSetName": settings.AWS_PINPOINT_CONFIGURATION_ARN,
                    "MaxPricePerMinute": settings.AWS_PINPOINT_MAX_PRICE_VOICE,
                    "DryRun": dry_run,
                    "ProtectConfigurationId": settings.AWS_PINPOINT_PROTECT_ID,
                }
            )

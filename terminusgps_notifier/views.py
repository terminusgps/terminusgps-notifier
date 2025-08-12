import asyncio
import logging
from itertools import compress

import aioboto3
from django import forms
from django.conf import ImproperlyConfigured, settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.views.generic import View
from terminusgps.wialon.items import WialonUnit
from terminusgps.wialon.session import WialonSession

from .forms import WialonUnitNotificationForm

logger = logging.getLogger(__name__)


def get_phone_numbers_from_wialon(unit_id: int | str, token: str) -> list[str]:
    """Returns a list of the unit's assigned phone numbers from the Wialon API."""
    with WialonSession(token=token) as session:
        return WialonUnit(unit_id, session).get_phone_numbers()


def get_phone_numbers(unit_id: int | str, wialon_token: str) -> list[str]:
    """Returns a list of the unit's assigned phone numbers."""
    if cached_phones := cache.get(unit_id):
        return cached_phones
    wialon_phones = get_phone_numbers_from_wialon(unit_id, wialon_token)
    cache.set(unit_id, wialon_phones)
    return wialon_phones


def get_wialon_api_token() -> str:
    """Returns an activated Wialon API token, raises :py:exec:`~django.conf.ImproperlyConfigured` if the 'WIALON_TOKEN' wasn't set."""
    # TODO: Retrieve from database
    if not hasattr(settings, "WIALON_TOKEN"):
        raise ImproperlyConfigured("'WIALON_TOKEN' setting is required.")
    return settings.WIALON_TOKEN


class HealthCheckView(View):
    content_type = "text/plain"
    http_method_names = ["get"]

    async def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Responds with status code 200."""
        return HttpResponse(b"I'm alive\n", status=200)


class DispatchNotificationView(View):
    content_type = "text/plain"
    http_method_names = ["get"]

    def __init__(self, *args, **kwargs) -> None:
        REQUIRED_SETTINGS = [
            "AWS_PINPOINT_POOL_ARN",
            "AWS_PINPOINT_CONFIGURATION_ARN",
            "AWS_PINPOINT_MAX_PRICE_SMS",
            "AWS_PINPOINT_MAX_PRICE_VOICE",
            "AWS_PINPOINT_PROTECT_ID",
        ]

        for setting in REQUIRED_SETTINGS:
            if not hasattr(settings, setting):
                raise ImproperlyConfigured(f"'{setting}' setting is required.")
        return super().__init__(*args, **kwargs)

    async def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """
        Dispatches a notification based on query parameters.

        Returns 200 if notifications were successfully dispatched.

        Returns 200 if the provided unit id didn't have attached phone numbers.

        Returns 406 if the unit id, message or method was invalid.

        """
        form: forms.Form = WialonUnitNotificationForm(request.GET)
        if not form.is_valid():
            return HttpResponse(
                f"{form.errors.as_json(escape_html=True)}\n".encode("utf-8"),
                status=406,
            )

        unit_id: str = str(form.cleaned_data["unit_id"])
        message: str = str(form.cleaned_data["message"])
        dry_run: bool = bool(form.cleaned_data["dry_run"])
        wialon_token: str = get_wialon_api_token()
        target_phones: list[str] = get_phone_numbers(unit_id, wialon_token)

        if not target_phones:
            return HttpResponse(
                f"No phones retrieved for #{unit_id}\n".encode("utf-8"),
                status=200,
            )

        try:
            method: str = str(self.kwargs["method"])
            message_ids: list[str | None] = await asyncio.gather(
                *[
                    self.send_notification(phone, message, method, dry_run)
                    for phone in target_phones
                ]
            )
            success_mask = [bool(msg_id) for msg_id in message_ids]
            delivery_successes = list(compress(target_phones, success_mask))
            delivery_failures = list(
                compress(target_phones, [not _ for _ in success_mask])
            )
            if delivery_failures:
                logger.warning(
                    f"Failed to deliver notifications to: '{delivery_failures}'."
                )
            logger.info(
                f"Successfully sent '{message}' to: '{delivery_successes}' via {method}."
            )
            return HttpResponse("Success".encode("utf-8"), status=200)
        except ValueError as e:
            content = str(e)
            logger.warning(content)
            return HttpResponse(f"{content}\n".encode("utf-8"), status=406)

    async def send_notification(
        self, to_number: str, message: str, method: str, dry_run: bool = False
    ) -> None:
        """
        Sends a notification to ``to_number`` via ``method``.

        :param to_number: Destination (target) phone number.
        :type to_number: :py:obj:`str`
        :param message: Notification message.
        :type message: :py:obj:`str`
        :param method: Notification method. Options are ``sms`` or ``voice``.
        :type method: :py:obj:`str`
        :param dry_run: Whether or not to execute the API call as a dry run. Default is :py:obj:`False`.
        :type dry_run: :py:obj:`bool`
        :raises ValueError: If the provided notification method was invalid.
        :returns: Nothing.
        :rtype: :py:obj:`None`

        """
        match method:
            case "sms":
                await self._send_sms_message(to_number, message, dry_run)
            case "voice":
                await self._send_voice_message(to_number, message, dry_run)
            case _:
                raise ValueError(f"Invalid method: '{method}'")

    async def _send_sms_message(
        self, to_number: str, message: str, dry_run: bool = False
    ) -> str | None:
        """
        Sends ``message`` to ``to_number`` via sms.

        :param to_number: Destination phone number.
        :type to_number: :py:obj:`str`
        :param message: A message to deliver to the destination phone number via sms.
        :type message: :py:obj:`str`
        :param dry_run: Whether or not to execute the API call as a dry run. Default is :py:obj:`False`.
        :type dry_run: :py:obj:`bool`
        :returns: A message id, if sent.
        :rtype: :py:obj:`str` | :py:obj:`None`

        """
        async with aioboto3.Session().client(
            "pinpoint-sms-voice-v2"
        ) as client:
            response = await client.send_text_message(
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
            return response.get("MessageId")

    async def _send_voice_message(
        self, to_number: str, message: str, dry_run: bool = False
    ) -> str | None:
        """
        Sends ``message`` to ``to_number`` via voice.

        :param to_number: Destination phone number.
        :type to_number: :py:obj:`str`
        :param message: A message to read aloud to the destination phone number via voice.
        :type message: :py:obj:`str`
        :param dry_run: Whether or not to execute the API call as a dry run. Default is :py:obj:`False`.
        :type dry_run: :py:obj:`bool`
        :returns: A message id, if sent.
        :rtype: :py:obj:`str` | :py:obj:`None`

        """
        async with aioboto3.Session().client(
            "pinpoint-sms-voice-v2"
        ) as client:
            response = await client.send_voice_message(
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
            return response.get("MessageId")

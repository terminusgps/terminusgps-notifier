import logging

import boto3
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.views.generic import View
from terminusgps.wialon.items import WialonUnit
from terminusgps.wialon.session import WialonSession

from .forms import WialonUnitNotificationForm

logger = logging.getLogger(__file__)


class HealthCheckView(View):
    content_type = "text/plain"
    http_method_names = ["get"]

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Responds with status code 200."""
        return HttpResponse(b"I'm alive\n", status=200)


class DispatchNotificationView(View):
    content_type = "text/plain"
    http_method_names = ["get"]

    def setup(self, request: HttpRequest, *args, **kwargs) -> None:
        """Adds ``pinpoint_client`` to the view."""
        self.pinpoint_client = boto3.client("pinpoint-sms-voice-v2")
        return super().setup(request, *args, **kwargs)

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """
        Dispatches a notification based on query parameters.

        Returns 200 if notifications were successfully dispatched.

        Returns 200 if the provided unit id didn't have attached phone numbers.

        Returns 406 if the unit id, message or method was invalid.

        """
        form = WialonUnitNotificationForm(request.GET)
        if not form.is_valid():
            content = form.errors.as_json(escape_html=True)
            return HttpResponse(f"{content}\n".encode("utf-8"), status=406)

        unit_id = str(form.cleaned_data["unit_id"])
        message = str(form.cleaned_data["message"])

        logger.debug(f"Retrieving phone numbers for #{unit_id} from Wialon...")
        target_phones: list[str] = self.get_wialon_phone_numbers(
            unit_id, settings.WIALON_TOKEN
        )

        # Early 200 response if no phones
        if not target_phones:
            content = f"No phones for #{unit_id}"
            logger.warning(content)
            return HttpResponse(f"{content}\n".encode("utf-8"), status=200)

        # Handle notifications if phones
        try:
            method: str = str(self.kwargs["method"])
            for phone in target_phones:
                self.send_notification(phone, message, method)

            content = f"Sent '{message}' to: {target_phones} via {method}"
            logger.debug(content)
            return HttpResponse(f"{content}\n".encode("utf-8"), status=200)
        except ValueError as e:
            content = str(e)
            logger.warning(content)
            return HttpResponse(f"{content}\n".encode("utf-8"), status=406)

    @staticmethod
    def get_wialon_phone_numbers(
        unit_id: str, wialon_api_token: str
    ) -> list[str]:
        """
        Returns a list of phone numbers for a Wialon unit.

        :param unit_id: A Wialon unit id.
        :type unit_id: :py:obj:`str`
        :param wialon_api_token: An enabled Wialon API token.
        :type wialon_api_token: :py:obj:`str`
        :returns: A list of phone numbers associated with the Wialon unit.
        :rtype: :py:obj:`list`[:py:obj:`str`]

        """
        with WialonSession(token=wialon_api_token) as session:
            return WialonUnit(unit_id, session).get_phone_numbers()

    def send_notification(
        self, to_number: str, message: str, method: str
    ) -> None:
        """
        Sends a notification to ``to_number`` via ``method``.

        :param to_number: Destination (target) phone number.
        :type to_number: :py:obj:`str`
        :param message: Notification message.
        :type message: :py:obj:`str`
        :param method: Notification method. Options are ``sms`` or ``voice``.
        :type method: :py:obj:`str`
        :raises ValueError: If the provided notification method was invalid.
        :returns: Nothing.
        :rtype: :py:obj:`None`

        """
        match method:
            case "sms":
                logger.debug(
                    f"Sending '{message}' to '{to_number}' via sms..."
                )
                self._send_sms_message(to_number, message)
            case "voice":
                logger.debug(
                    f"Sending '{message}' to '{to_number}' via voice..."
                )
                self._send_voice_message(to_number, message)
            case _:
                raise ValueError(f"Invalid method: '{method}'")

    def _send_sms_message(
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
        response = self.pinpoint_client.send_text_message(
            **{
                "DestinationPhoneNumber": to_number,
                "OriginationIdentity": settings.AWS_PINPOINT_POOL_ARN,
                "MessageBody": message,
                "MessageType": "TRANSACTIONAL",
                "ConfigurationSetName": settings.AWS_PINPOINT_CONFIGURATION_ARN,
                "MaxPrice": settings.AWS_PINPOINT_MAX_PRICE_SMS,
                "TimeToLive": 300,
                "DryRun": dry_run or settings.DEBUG,
                "ProtectConfigurationId": settings.AWS_PINPOINT_PROTECT_ID,
            }
        )
        return response.get("MessageId")

    def _send_voice_message(
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
        response = self.pinpoint_client.send_voice_message(
            **{
                "DestinationPhoneNumber": to_number,
                "OriginationIdentity": settings.AWS_PINPOINT_POOL_ARN,
                "MessageBody": message,
                "MessageBodyTextType": "TEXT",
                "VoiceId": "MATTHEW",
                "ConfigurationSetName": settings.AWS_PINPOINT_CONFIGURATION_ARN,
                "MaxPricePerMinute": settings.AWS_PINPOINT_MAX_PRICE_VOICE,
                "DryRun": dry_run or settings.DEBUG,
                "ProtectConfigurationId": settings.AWS_PINPOINT_PROTECT_ID,
            }
        )
        return response.get("MessageId")

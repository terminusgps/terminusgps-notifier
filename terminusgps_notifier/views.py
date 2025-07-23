import logging

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.views.generic import View
from terminusgps.wialon.items import WialonUnit
from terminusgps.wialon.session import WialonSession
from twilio.rest import Client

from .forms import WialonUnitNotificationForm

logger = logging.getLogger()


class HealthCheckView(View):
    content_type = "text/plain"
    http_method_names = ["get"]

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Responds with status code 200."""
        return HttpResponse(b"I'm alive", status=200)


class DispatchNotificationView(View):
    content_type = "text/plain"
    http_method_names = ["get"]

    def setup(self, request: HttpRequest, *args, **kwargs) -> None:
        """Adds ``twilio_client`` to the view for notification dispatching."""
        self.twilio_client = Client(settings.TWILIO_SID, settings.TWILIO_TOKEN)
        return super().setup(request, *args, **kwargs)

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """
        Dispatches a notification using Twilio based on query parameters.

        Returns 200 if notifications were successfully dispatched.

        Returns 406 if the unit id, message or method was invalid.

        """
        form = WialonUnitNotificationForm(request.GET)
        if not form.is_valid():
            msg = form.errors.as_json(escape_html=True)
            return HttpResponse(bytes(msg, encoding="utf-8"), status=406)

        unit_id = str(form.cleaned_data["unit_id"])
        message = str(form.cleaned_data["message"])
        target_phones: list[str] = self.get_wialon_phone_numbers(
            unit_id, settings.WIALON_TOKEN
        )

        if not target_phones:
            msg = bytes(f"No phones for unit #{unit_id}", encoding="utf-8")
            logger.warning(str(msg))
            return HttpResponse(msg, status=406)

        try:
            method: str = str(self.kwargs["method"])
            for phone in target_phones:
                self.send_notification(phone, message, method)

            msg = f"Sent '{message}' to: {target_phones} via {method}"
            logger.debug(msg)
            return HttpResponse(bytes(msg, encoding="utf-8"), status=200)
        except ValueError as e:
            return HttpResponse(bytes(str(e), encoding="utf-8"), status=406)

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
            logger.debug(
                f"Retrieving phone numbers for unit #{unit_id} using sid #{session.id}..."
            )
            return WialonUnit(unit_id, session).get_phone_numbers()

    def send_notification(
        self, to_number: str, message: str, method: str
    ) -> None:
        """
        Sends a notification to ``to_number`` via ``method``.

        :param to_number: Notification recipient (target) phone number.
        :type to_number: :py:obj:`str`
        :param message: Notification message.
        :type message: :py:obj:`str`
        :param method: Notification method. Options are ``sms``, ``call`` or ``phone``.
        :type method: :py:obj:`str`
        :raises ValueError: If the provided method was invalid.
        :returns: Nothing.
        :rtype: :py:obj:`None`

        """
        match method:
            case "sms":
                logger.debug(
                    f"Sending '{message}' to '{to_number}' via {method}..."
                )
                self._send_sms_notification(to_number, message)
            case "call" | "phone" | "voice":
                logger.debug(
                    f"Sending '{message}' to '{to_number}' via {method}..."
                )
                self._send_voice_notification(to_number, message)
            case _:
                raise ValueError(f"Invalid method: '{method}'")

    def _send_sms_notification(self, to_number: str, message: str) -> None:
        """Sends ``message`` to ``to_number`` via sms."""
        if settings.DEBUG:
            return

        self.twilio_client.messages.create(
            to=to_number, from_=settings.TWILIO_FROM_NUMBER, body=message
        )

    def _send_voice_notification(self, to_number: str, message: str) -> None:
        """Sends ``message`` to ``to_number`` via voice."""
        if settings.DEBUG:
            return

        self.twilio_client.calls.create(
            to=to_number,
            from_=settings.TWILIO_FROM_NUMBER,
            twiml=f"<Response><Say>{message}</Say></Response>",
        )

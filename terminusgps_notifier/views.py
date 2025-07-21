import typing

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.views.generic import View
from terminusgps.wialon.items import WialonUnit
from terminusgps.wialon.session import WialonSession
from twilio.rest import Client

from .forms import WialonUnitNotificationForm


class DispatchNotificationView(View):
    content_type = "application/x-www-form-urlencoded"
    http_method_names = ["post"]

    def setup(self, request: HttpRequest, *args, **kwargs) -> None:
        self.twilio_client = Client(settings.TWILIO_SID, settings.TWILIO_TOKEN)
        self.method_map = {
            "sms": self.send_sms_notification,
            "call": self.send_voice_notification,
            "phone": self.send_voice_notification,
        }
        return super().setup(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        try:
            method = str(self.kwargs["method"])
            notify = self.get_notification_func(method)
        except ValueError as e:
            error_msg = bytes(str(e), encoding="utf-8")
            return HttpResponse(error_msg, status=406)

        form = WialonUnitNotificationForm(request.POST)
        if not form.is_valid():
            error_msg = bytes(form.errors.as_json(escape_html=True), encoding="utf-8")
            return HttpResponse(error_msg, status=406)
        else:
            unit_id = str(form.cleaned_data["unit_id"])
            message = str(form.cleaned_data["message"])

            target_phones = self.get_wialon_phone_numbers(unit_id)
            if not target_phones:
                error_msg = bytes(f"No phones for unit #{unit_id}", encoding="utf-8")
                return HttpResponse(error_msg, status=406)

            for phone in target_phones:
                notify(phone, message)
            response_msg = bytes(
                f"Sent '{message}' to: {target_phones} via '{method}'", encoding="utf-8"
            )
            return HttpResponse(response_msg, status=200)

    def get_notification_func(self, method_name: str) -> typing.Callable:
        if method_name not in self.method_map:
            raise ValueError(f"Invalid notification method: '{method_name}'")
        return self.method_map[method_name]

    def get_wialon_phone_numbers(self, unit_id: str) -> list[str]:
        with WialonSession(token=settings.WIALON_TOKEN) as session:
            return WialonUnit(unit_id, session).get_phone_numbers()

    def send_sms_notification(self, to_number: str, message: str) -> None:
        self.twilio_client.messages.create(
            to=to_number, from_=settings.TWILIO_FROM_NUMBER, body=message
        )

    def send_voice_notification(self, to_number: str, message: str) -> None:
        self.twilio_client.calls.create(
            to=to_number,
            from_=settings.TWILIO_FROM_NUMBER,
            twiml=f"<Response><Say>{message}</Say></Response>",
        )

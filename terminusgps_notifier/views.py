from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.views.generic import View
from terminusgps.wialon.items import WialonUnit
from terminusgps.wialon.session import WialonSession
from twilio.rest import Client

from .forms import WialonUnitNotificationForm


def get_wialon_phone_numbers(unit_id: str, wialon_api_token: str) -> list[str]:
    with WialonSession(token=wialon_api_token) as session:
        unit = WialonUnit(unit_id, session)
        return unit.get_phone_numbers()


class DispatchNotificationView(View):
    content_type = "application/x-www-form-urlencoded"
    http_method_names = ["get"]

    def setup(self, request: HttpRequest, *args, **kwargs) -> None:
        self.twilio_client = Client(settings.TWILIO_SID, settings.TWILIO_TOKEN)
        return super().setup(request, *args, **kwargs)

    def send_notification(self, to_number: str, message: str, method: str) -> None:
        match method:
            case "sms":
                self.twilio_client.messages.create(
                    to=to_number, from_=settings.TWILIO_FROM_NUMBER, body=message
                )
            case "call" | "phone":
                self.twilio_client.calls.create(
                    to=to_number,
                    from_=settings.TWILIO_FROM_NUMBER,
                    twiml=f"<Response><Say>{message}</Say></Response>",
                )
            case _:
                raise ValueError(f"Invalid method: '{method}'")

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        form = WialonUnitNotificationForm(request.GET)
        if not form.is_valid():
            error_msg = bytes(form.errors.as_json(escape_html=True), encoding="utf-8")
            return HttpResponse(error_msg, status=406)
        else:
            unit_id = str(form.cleaned_data["unit_id"])
            message = str(form.cleaned_data["message"])

            target_phones = get_wialon_phone_numbers(unit_id, settings.WIALON_TOKEN)
            if not target_phones:
                error_msg = bytes(f"No phones for unit #{unit_id}", encoding="utf-8")
                return HttpResponse(error_msg, status=406)

            try:
                method = str(self.kwargs["method"])
                for phone in target_phones:
                    self.send_notification(phone, message, method)

                return HttpResponse(
                    bytes(
                        f"Sent '{message}' to: {target_phones} via {method}",
                        encoding="utf-8",
                    ),
                    status=200,
                )
            except ValueError as e:
                error_msg = bytes(str(e), encoding="utf-8")
                return HttpResponse(error_msg, status=200)

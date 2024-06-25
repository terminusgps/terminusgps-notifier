from fastapi import FastAPI, Form, Request

from integrations.twilio import TwilioCaller
from models import NotificationErrorResponse, NotificationResponse
from validators import ValidationError, validate_to_number


def clean_to_number(to_number: str) -> list[str] | str:
    if "," in to_number:
        return to_number.strip().split(",")
    else:
        return to_number.strip()


class TerminusNotifierApp:
    def __init__(self) -> None:
        self.app = FastAPI()
        self.create_routes()

        return None

    def create_routes(self) -> None:
        @self.app.post("/notify/{method}")
        async def notify(
            request: Request,
            method: str = "call",
            to_number: str = Form(...),
            message: str = Form(...),
        ) -> NotificationResponse | NotificationErrorResponse:
            """Send a notification to phone numbers using Twilio."""
            try:
                validate_to_number(to_number)
            except ValidationError:
                return NotificationErrorResponse(
                    to_number=to_number,
                    message=message,
                    method=method,
                    error="Invalid to_number",
                    error_desc=f"Invalid to_number '{to_number}'.",
                )
            else:
                to_number: str | list[str] = clean_to_number(to_number)

            caller = TwilioCaller()
            if isinstance(to_number, list):
                await caller.batch_message(
                    to_number=to_number,
                    message=message,
                    method=method,
                )
            else:
                await caller.send_message(
                    to_number=to_number,
                    message=message,
                    method=method,
                )

            return NotificationResponse(
                to_number=to_number,
                message=message,
                method=method,
            )

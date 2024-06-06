import logging

from fastapi import FastAPI, Form, Request

from integrations.twilio import TwilioCaller
from models import NotificationResponse

logger = logging.getLogger(__name__)


def clean_to_number(to_number: str) -> list[str] | str:
    if "," in to_number:
        clean_num = to_number.split(",")
    else:
        clean_num = to_number
    return clean_num


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
        ) -> NotificationResponse:
            """Send a notification to phone numbers using Twilio."""

            data = {
                "to_number": to_number,
                "message": message,
            }
            to_number = clean_to_number(data.get("to_number"))
            message = data.get("message", "")

            caller = TwilioCaller()
            if method in caller.valid_methods:
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
                success = True

            else:
                message = f"Invalid method: {method}"
                success = False

            return NotificationResponse(
                to_number=to_number,
                message=message,
                method=method,
                success=success,
            )

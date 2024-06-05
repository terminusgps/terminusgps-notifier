from fastapi import FastAPI

from integrations.twilio import TwilioCaller
from request import NotificationRequest
from response import NotificationResponse


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
        @self.app.post("/v2/notify/{method}")
        async def notify(
            request: NotificationRequest,
            method: str = "call",
        ) -> NotificationResponse:
            """Send a notification to phone numbers using Twilio."""
            caller = TwilioCaller()
            valid_methods = caller.valid_methods
            if method not in valid_methods:
                return NotificationResponse(
                    to_number=request.to_number,
                    message=request.message,
                    method=method,
                    success=False,
                )

            await caller.send_message(
                to_number=request.to_number,
                msg=request.message,
                method=method,
            )

            return NotificationResponse(
                to_number=request.to_number,
                message=request.message,
                method=method,
                success=True,
            )

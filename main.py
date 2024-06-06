from fastapi import FastAPI

from integrations.twilio import TwilioCaller
from models import NotificationRequest, NotificationResponse


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
            request: NotificationRequest,
            method: str = "call",
        ) -> NotificationResponse:
            """Send a notification to phone numbers using Twilio."""
            caller = TwilioCaller()
            to_number = clean_to_number(request.to_number)
            message = request.message

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

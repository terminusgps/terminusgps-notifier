import asyncio
from typing import Annotated, Any, Optional
from asyncio.tasks import Task
from fastapi import FastAPI, Form
from twilio.base.exceptions import TwilioRestException
from wialon.api import WialonError

from terminusgps.twilio.caller import TwilioCaller
from terminusgps.wialon.session import WialonSession
from terminusgps.wialon.items import WialonUnit
from models.responses import NotificationResponse, NotificationErrorResponse

app = FastAPI()


def create_tasks(
    phone_numbers: list[str], message: str, method: str, caller: TwilioCaller
) -> list[Task[Any]]:
    tasks = []
    for to_number in phone_numbers:
        tasks.append(
            caller.create_notification(
                to_number=to_number, message=message, method=method
            )
        )
    return tasks


def get_phone_numbers(
    to_number: str | None = None, unit_id: int | None = None
) -> list[str]:
    if to_number is None and unit_id is None:
        raise ValueError("Must provide at least one 'to_number' or 'unit_id'.")

    phone_numbers = []
    if to_number is not None:
        phone_numbers.extend([to_number])
    if unit_id is not None:
        with WialonSession() as session:
            unit = WialonUnit(id=str(unit_id), session=session)
            unit_phones = unit.get_phone_numbers()
            if unit_phones:
                phone_numbers.extend(unit_phones)
    return phone_numbers


@app.post("/notify/{method}")
async def notify(
    method: str,
    message: Annotated[str, Form()],
    unit_id: Annotated[Optional[int], Form()] = None,
    to_number: Annotated[Optional[str], Form()] = None,
) -> NotificationResponse | NotificationErrorResponse:
    """Send a notification to phone numbers using Twilio."""
    try:
        phone_numbers: list[str] = get_phone_numbers(
            to_number=to_number, unit_id=unit_id
        )
    except ValueError as e:
        return NotificationErrorResponse(
            phones=[to_number] if to_number else [],
            unit_id=str(unit_id),
            message=message,
            method=method,
            error=str(e),
            error_desc=f"Got to_number: '{to_number}' and unit_id: '{unit_id}'.",
        )
    except WialonError as e:
        return NotificationErrorResponse(
            phones=[to_number] if to_number else [],
            unit_id=str(unit_id),
            message=message,
            method=method,
            error=str(e),
            error_desc="Something went wrong with Wialon.",
        )

    try:
        with TwilioCaller() as caller:
            tasks: list[Task[Any]] = create_tasks(
                phone_numbers=phone_numbers,
                message=message,
                method=method,
                caller=caller,
            )
            asyncio.gather(*tasks)
    except TwilioRestException as e:
        return NotificationErrorResponse(
            phones=phone_numbers,
            unit_id=str(unit_id),
            message=message,
            method=method,
            error=str(e),
            error_desc="Something went wrong with Twilio.",
        )
    else:
        return NotificationResponse(
            phones=phone_numbers, unit_id=str(unit_id), message=message, method=method
        )


def main() -> None:
    import requests

    url = "https://api.terminusgps.com/v2/notify/sms"
    data = {
        "to_number": "+17133049421",
        "message": "Hello, this is a test message from Terminus GPS!",
    }
    requests.post(url, data=data)
    data = {
        "unit_id": "28121664",
        "message": "Hello, this is a test message from Terminus GPS!",
    }
    requests.post(url, data=data)
    return


if __name__ == "__main__":
    main()

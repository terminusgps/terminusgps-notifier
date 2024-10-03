import asyncio
from typing import Any
from asyncio.tasks import Task
from fastapi import FastAPI
from twilio.base.exceptions import TwilioRestException
from wialon.api import WialonError

from caller import TwilioCaller
from models import NotificationResponse, NotificationErrorResponse
from wialonapi import WialonSession, WialonUnit
from wialonapi.items.unit import clean_phone_numbers

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


@app.post("/notify/{method}")
async def notify(
    method: str,
    message: str = "",
    unit_id: int | None = None,
    to_number: str | None = None,
) -> NotificationResponse | NotificationErrorResponse:
    """Send a notification to phone numbers using Twilio."""
    phone_numbers = []
    if not to_number and not unit_id:
        raise ValueError("No to_number or unit_id provided.")

    if to_number:
        phone_numbers.extend(clean_phone_numbers([to_number]))
    if unit_id:
        try:
            with WialonSession() as session:
                unit = WialonUnit(id=str(unit_id), session=session)
                phone_numbers.extend(unit.get_phone_numbers())
        except WialonError as e:
            return NotificationErrorResponse(
                phones=[],
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
            phones=phone_numbers,
            unit_id=str(unit_id),
            message=message,
            method=method,
        )

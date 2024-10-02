import asyncio
from typing import Any
from asyncio.tasks import Task
from fastapi import FastAPI, Request
from twilio.base.exceptions import TwilioRestException
from wialon.api import WialonError

from caller import TwilioCaller
from models import NotificationResponse, NotificationErrorResponse
from wialonapi import WialonSession, WialonUnit
from wialonapi.items.unit import clean_phone_numbers

app = FastAPI()


def create_tasks(
    phone_numbers: list[str], message: str, method: str
) -> list[Task[Any]]:
    caller = TwilioCaller()
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
    request: Request,
    method: str = "sms",
    message: str = "",
    unit_id: str | None = None,
    to_number: str | None = None,
) -> NotificationResponse | NotificationErrorResponse:
    """Send a notification to phone numbers using Twilio."""
    phone_numbers = []
    if to_number:
        phone_numbers.extend(to_number)
    if unit_id:
        try:
            with WialonSession() as session:
                unit = WialonUnit(id=unit_id, session=session)
        except WialonError as e:
            return NotificationErrorResponse(
                phones=[],
                unit_id=unit_id,
                message=message,
                method=method,
                error=str(e),
                error_desc="Something went wrong with Wialon.",
            )
        else:
            phone_numbers.extend(unit.get_phone_numbers())

    try:
        tasks: list[Task[Any]] = create_tasks(
            phone_numbers=phone_numbers,
            message=message,
            method=method,
        )
    except TwilioRestException as e:
        return NotificationErrorResponse(
            phones=phone_numbers,
            unit_id=unit_id,
            message=message,
            method=method,
            error=str(e),
            error_desc="Something went wrong with Twilio.",
        )
    else:
        asyncio.gather(*tasks)
        return NotificationResponse(
            phones=phone_numbers,
            unit_id=unit_id,
            message=message,
            method=method,
        )

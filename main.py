import asyncio
from typing import Annotated, Any, Optional
from asyncio.tasks import Task
from fastapi import FastAPI, Form
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
    message: Annotated[str, Form()],
    to_number: Annotated[Optional[str], Form()] = None,
    unit_id: Annotated[Optional[int], Form()] = None,
) -> NotificationResponse | NotificationErrorResponse:
    """Send a notification to phone numbers using Twilio."""
    phone_numbers = []
    if not to_number and not unit_id:
        return NotificationErrorResponse(
            phones=phone_numbers,
            unit_id=str(unit_id),
            message=message,
            method=method,
            error="",
            error_desc="No unit_id or to_number provided.",
        )

    if to_number:
        phone_numbers.extend(clean_phone_numbers([to_number]))
    if unit_id:
        try:
            with WialonSession() as session:
                unit = WialonUnit(id=str(unit_id), session=session)
                unit_phones = clean_phone_numbers(unit.get_phone_numbers())
                phone_numbers.extend(unit_phones)
        except WialonError as e:
            return NotificationErrorResponse(
                phones=phone_numbers,
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

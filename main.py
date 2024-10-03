import asyncio
from typing import Any
from asyncio.tasks import Task
from fastapi import FastAPI
from twilio.base.exceptions import TwilioRestException
from wialon.api import WialonError

from caller import TwilioCaller
from models import NotificationResponse, NotificationErrorResponse
from models.requests import NotificationRequest
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
    notification: NotificationRequest,
) -> NotificationResponse | NotificationErrorResponse:
    """Send a notification to phone numbers using Twilio."""
    phone_numbers = []
    if not notification.to_number and not notification.unit_id:
        return NotificationErrorResponse(
            phones=phone_numbers,
            unit_id=str(notification.unit_id),
            message=notification.message,
            method=method,
            error="",
            error_desc="No unit_id or to_number provided.",
        )

    if notification.to_number:
        phone_numbers.extend(clean_phone_numbers([notification.to_number]))
    if notification.unit_id:
        try:
            with WialonSession() as session:
                unit = WialonUnit(id=str(notification.unit_id), session=session)
                phone_numbers.extend(unit.get_phone_numbers())
        except WialonError as e:
            return NotificationErrorResponse(
                phones=phone_numbers,
                unit_id=str(notification.unit_id),
                message=notification.message,
                method=method,
                error=str(e),
                error_desc="Something went wrong with Wialon.",
            )

    try:
        with TwilioCaller() as caller:
            tasks: list[Task[Any]] = create_tasks(
                phone_numbers=phone_numbers,
                message=notification.message,
                method=method,
                caller=caller,
            )
            asyncio.gather(*tasks)
    except TwilioRestException as e:
        return NotificationErrorResponse(
            phones=phone_numbers,
            unit_id=str(notification.unit_id),
            message=notification.message,
            method=method,
            error=str(e),
            error_desc="Something went wrong with Twilio.",
        )
    else:
        return NotificationResponse(
            phones=phone_numbers,
            unit_id=str(notification.unit_id),
            message=notification.message,
            method=method,
        )

import asyncio
from asyncio.tasks import Task
from fastapi import FastAPI, Form, Request
from twilio.base.exceptions import TwilioRestException

from caller import TwilioCaller
from models import NotificationResponse, NotificationErrorResponse

app = FastAPI()

def clean_to_number(to_number: str) -> list[str] | str:
    if "," in to_number:
        return to_number.strip().split(",")
    else:
        return to_number.strip()


def create_tasks(to_number: str | list[str], message: str, method: str) -> list[Task]:
    caller = TwilioCaller()
    tasks = []
    if isinstance(to_number, str):
        tasks.append(caller.create_notification(
            to_number=to_number,
            message=message,
            method=method,
        ))
    elif isinstance(to_number, list):
        for num in to_number:
            tasks.append(caller.create_notification(
                to_number=num,
                message=message,
                method=method,
            ))

    return tasks
    

@app.post("/notify/{method}")
async def notify(
    request: Request,
    method: str,
    to_number: str = Form(...),
    message: str = Form(...),
) -> NotificationResponse | NotificationErrorResponse:
    """Send a notification to phone numbers using Twilio."""
    phone: str | list[str] = clean_to_number(to_number)
    try:
        tasks: list[Task] = create_tasks(
            to_number=phone,
            message=message,
            method=method,
        )
    except TwilioRestException as e:
        return NotificationErrorResponse(
            to_number=phone,
            message=message,
            method=method,
            error=str(e),
            error_desc="Something went wrong with Twilio.",
        )
    else:
        asyncio.gather(*tasks)
        return NotificationResponse(
            to_number=phone,
            message=message,
            method=method,
        )

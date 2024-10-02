import asyncio
from asyncio import Task
from os import getenv
from typing import Any

from twilio.rest import Client
from twilio.http.async_http_client import AsyncTwilioHttpClient


class TwilioCaller:
    def __init__(self) -> None:
        self.client = Client(
            getenv("TWILIO_SID", ""),
            getenv("TWILIO_TOKEN", ""),
            http_client=AsyncTwilioHttpClient(),
        )
        self.from_number = getenv("TWILIO_FROM_NUMBER", "")
        self.messaging_service_sid = getenv("TWILIO_MESSAGING_SID", "")

    async def create_notification(
        self, to_number: str, message: str, method: str = "sms"
    ) -> Task[Any]:
        match method:
            case "sms":
                print(f"Sending '{message}' to '{to_number}' via sms...")
                task = asyncio.create_task(
                    self.create_sms(to_number=to_number, message=message)
                )
            case "echo":
                print(f"Echo: '{message}'")
                task = asyncio.create_task(
                    self.create_sms(to_number="+17133049421", message=message)
                )
            case "call" | "phone" | "tts":
                print(
                    f"Sending '{message}' to '{to_number}' via text-to-speech call..."
                )
                task = asyncio.create_task(
                    self.create_call(to_number=to_number, message=message)
                )
            case _:
                raise Exception

        return task

    async def create_call(self, to_number: str, message: str) -> None:
        await self.client.calls.create_async(
            to=to_number,
            from_=self.from_number,
            twiml=f"<Response><Say>{message}</Say></Response>",
        )

    async def create_sms(self, to_number: str, message: str) -> None:
        await self.client.messages.create_async(
            to=to_number,
            from_=self.from_number,
            body=message,
            messaging_service_sid=self.messaging_service_sid,
        )

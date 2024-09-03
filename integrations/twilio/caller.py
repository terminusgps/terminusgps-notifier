import asyncio
from os import environ as env

from twilio.rest import Client


class TwilioCaller:
    def __init__(self) -> None:
        self.client = Client(
            env.get("TWILIO_SID", ""),
            env.get("TWILIO_TOKEN", ""),
        )
        self.from_ = env.get("TWILIO_FROM_NUMBER", "")
        self.messaging_service_sid = env.get("TWILIO_MESSAGING_SERVICE_SID", "")

        return None

    async def send_message(self, to_number: str, message: str, *, method: str) -> None:
        match method:
            case "call" | "phone":
                print(f"Sending '{message}' to '{to_number}' via Voice")
                self.client.calls.create(
                    to=to_number,
                    from_=self.from_,
                    twiml=f"<Response><Say>{message}</Say></Response>",
                )
            case "sms":
                print(f"Sending '{message}' to '{to_number}' via SMS")
                self.client.messages.create(
                    to=to_number,
                    messaging_service_sid=self.messaging_service_sid,
                    body=message,
                )
            case "echo":
                print(message)
            case _:
                print(f"Invalid method '{method}'")

    async def batch_message(
        self, to_number: list[str], message: str, *, method: str
    ) -> None:
        tasks = [
            asyncio.create_task(self.send_message(number, message, method=method))
            for number in to_number
        ]
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    # Usage example
    async def main():
        caller = TwilioCaller()

        # Call one number
        await caller.send_message(
            to_number="+17133049421",
            message="Hello! This is a test message from TerminusGPS Notifier.",
            method="sms",
        )

        # Send SMS to multiple numbers
        await caller.batch_message(
            to_number=["+15555555555", "+15555555555"],
            message="Hello! This is a test message from TerminusGPS Notifier.",
            method="sms",
        )

    asyncio.run(main())

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

        return None

    async def send_message(self, to_number: str, message: str, *, method: str) -> None:
        match method:
            case "call" | "phone":  # "phone" is an alias for "call" from v1
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
                    from_=self.from_,
                    body=message,
                )
            case "echo":
                print(f"Sending 'message' to stdout")
                print(message)
            case _:
                print(f"Invalid method '{method}'")

        return None

    async def batch_message(
        self, to_number: list[str], message: str, *, method: str = "call"
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
            method="call",
        )

        # Send SMS to multiple numbers
        await caller.batch_message(
            to_number=["+17133049421", "+18324518302"],
            message="Hello! This is a test message from TerminusGPS Notifier.",
            method="sms",
        )

    asyncio.run(main())

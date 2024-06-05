import asyncio
from os import environ as env

from twilio.rest import Client


class TwilioCaller:
    def __init__(self) -> None:
        self._token = env.get("TWILIO_TOKEN")
        self._sid = env.get("TWILIO_SID")
        self.client = Client(self._sid, self._token)
        self.valid_methods = ["call", "sms"]

        return None

    async def send_message(
        self, to_number: str, msg: str, *, method: str = "call"
    ) -> None:
        match method:
            case "call":
                print(f"Sending '{msg}' to '{to_number}' via Voice")
                self.client.calls.create(
                    to=to_number,
                    from_="+18447682706",
                    twiml=f"<Response><Say>{msg}</Say></Response>",
                )
            case "sms":
                print(f"Sending '{msg}' to '{to_number}' via SMS")
                self.client.messages.create(
                    to=to_number,
                    from_="+18447682706",
                    body=msg,
                )
            case _:
                print(f"Invalid method '{method}'")

        return None

    async def batch_message(
        self, to_number: list[str], msg: str, *, method: str = "call"
    ) -> None:
        tasks = [
            asyncio.create_task(self.send_message(number, msg, method=method))
            for number in to_number
        ]
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    # Usage example
    async def main():
        caller = TwilioCaller()

        # Call one number
        call = caller.send_message(
            to_number="+17133049421",
            msg="Hello! This is a test message from TerminusGPS",
            method="call",  # Default is "call"
        )
        await call

        # Send SMS to multiple numbers
        sms = caller.batch_message(
            to_number=["+17133049421", "+18324518302"],
            msg="Hello! This is a test message from TerminusGPS",
            method="sms",
        )
        await sms

    asyncio.run(main())

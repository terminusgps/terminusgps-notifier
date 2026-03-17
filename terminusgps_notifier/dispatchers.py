import datetime
from abc import ABC, abstractmethod

import aioboto3
from django.conf import settings
from django.http.response import sync_to_async
from django.template.loader import render_to_string
from twilio.http.async_http_client import AsyncTwilioHttpClient
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

from .forms import NotificationDispatchForm


class NotificationDispatcher(ABC):
    def __init__(self, form: NotificationDispatchForm) -> None:
        if not form.is_valid():
            raise ValueError("Form must be valid")
        self.form = form

    @abstractmethod
    async def send_voice(self, *args, **kwargs) -> str | None:
        raise NotImplementedError("Subclasses must implement this method.")

    @abstractmethod
    async def send_sms(self, *args, **kwargs) -> str | None:
        raise NotImplementedError("Subclasses must implement this method.")

    @sync_to_async
    def render_message(self, template_name: str) -> str:
        msg_time_int = self.form.cleaned_data["msg_time_int"]
        date = datetime.datetime.fromtimestamp(float(msg_time_int))
        context = self.form.cleaned_data.copy()
        context.update({"date": date})
        return render_to_string(template_name, context)

    async def send_notification(
        self, to_number: str, method: str
    ) -> str | None:
        match method:
            case "sms":
                return await self.send_sms(
                    to_number, dry_run=self.form.cleaned_data["dry_run"]
                )
            case "voice":
                return await self.send_voice(
                    to_number, dry_run=self.form.cleaned_data["dry_run"]
                )
            case _:
                raise ValueError(f"Invalid method: '{method}'")


class AWSNotificationDispatcher(NotificationDispatcher):
    def __init__(
        self, form: NotificationDispatchForm, region_name: str = "us-east-1"
    ) -> None:
        super().__init__(form=form)
        self.session = aioboto3.Session()
        self.service = "pinpoint-sms-voice-v2"
        self.region_name = region_name

    async def send_voice(
        self,
        to_number: str,
        *,
        message_type: str = "TEXT",
        voice_id: str = "MATTHEW",
        dry_run: bool = False,
        pool_arn: str | None = None,
        config_arn: str | None = None,
        mppm: str | None = None,
        protect_id: str | None = None,
    ):
        message = await self.render_message(
            "terminusgps_notifier/message_voice.txt"
        )
        async with self.session.client(
            self.service, region_name=self.region_name
        ) as client:
            return await client.send_voice_message(
                **{
                    "DestinationPhoneNumber": to_number,
                    "OriginationIdentity": pool_arn
                    or settings.AWS_PINPOINT_POOL_ARN,
                    "MessageBody": message,
                    "MessageBodyTextType": message_type,
                    "VoiceId": voice_id,
                    "ConfigurationSetName": config_arn
                    or settings.AWS_PINPOINT_CONFIGURATION_ARN,
                    "MaxPricePerMinute": mppm
                    or settings.AWS_PINPOINT_MAX_PRICE_VOICE,
                    "DryRun": dry_run,
                    "ProtectConfigurationId": protect_id
                    or settings.AWS_PINPOINT_PROTECT_ID,
                }
            )

    async def send_sms(
        self,
        to_number: str,
        *,
        ttl: int = 300,
        dry_run: bool = False,
        pool_arn: str | None = None,
        config_arn: str | None = None,
        mpps: str | None = None,
        protect_id: str | None = None,
    ):
        message = await self.render_message(
            "terminusgps_notifier/message_sms.txt"
        )
        async with self.session.client(
            self.service, region_name=self.region_name
        ) as client:
            return await client.send_text_message(
                **{
                    "DestinationPhoneNumber": to_number,
                    "OriginationIdentity": pool_arn
                    or settings.AWS_PINPOINT_POOL_ARN,
                    "MessageBody": message,
                    "MessageType": "TRANSACTIONAL",
                    "ConfigurationSetName": config_arn
                    or settings.AWS_PINPOINT_CONFIGURATION_ARN,
                    "MaxPrice": mpps or settings.AWS_PINPOINT_MAX_PRICE_SMS,
                    "TimeToLive": ttl,
                    "DryRun": dry_run,
                    "ProtectConfigurationId": protect_id
                    or settings.AWS_PINPOINT_PROTECT_ID,
                }
            )


class TwilioNotificationDispatcher(NotificationDispatcher):
    async def send_voice(
        self,
        to_number: str,
        voice: str = "woman",
        from_number: str | None = None,
        dry_run: bool = False,
    ):
        if dry_run:
            return
        raw = await self.render_message(
            "terminusgps_notifier/message_voice.txt"
        )
        message = VoiceResponse()
        message.say(raw, voice=voice)
        client = Client(http_client=AsyncTwilioHttpClient())
        return await client.calls.create_async(
            to=to_number,
            from_=from_number or settings.TWILIO_FROM_NUMBER,
            twiml=message,
        )

    async def send_sms(
        self,
        to_number: str,
        from_number: str | None = None,
        dry_run: bool = False,
    ):
        if dry_run:
            return
        message = await self.render_message(
            "terminusgps_notifier/message_sms.txt"
        )
        client = Client(http_client=AsyncTwilioHttpClient())
        return await client.messages.create_async(
            to=to_number,
            from_=from_number or settings.TWILIO_FROM_NUMBER,
            body=message,
        )

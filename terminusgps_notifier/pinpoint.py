from django.conf import settings
from types_aiobotocore_pinpoint_sms_voice_v2.client import (
    PinpointSMSVoiceV2Client,
)

__all__ = ["dispatch_notification", "send_sms_message", "send_voice_message"]


async def dispatch_notification(
    to_number: str,
    message: str,
    method: str,
    client: PinpointSMSVoiceV2Client,
    dry_run: bool = False,
) -> dict | None:
    match method:
        case "sms":
            return await send_sms_message(
                to_number=to_number,
                message=message,
                client=client,
                dry_run=dry_run,
            )
        case "voice":
            return await send_voice_message(
                to_number=to_number,
                message=message,
                client=client,
                dry_run=dry_run,
            )
        case _:
            raise ValueError(f"Invalid method: '{method}'.")


async def send_sms_message(
    to_number: str,
    message: str,
    client: PinpointSMSVoiceV2Client,
    *,
    ttl: int = 300,
    dry_run: bool = False,
) -> dict | None:
    return await client.send_text_message(
        **{
            "DestinationPhoneNumber": to_number,
            "OriginationIdentity": settings.AWS_PINPOINT_POOL_ARN,
            "MessageBody": message,
            "MessageType": "TRANSACTIONAL",
            "ConfigurationSetName": settings.AWS_PINPOINT_CONFIGURATION_ARN,
            "MaxPrice": settings.AWS_PINPOINT_MAX_PRICE_SMS,
            "TimeToLive": ttl,
            "DryRun": dry_run,
            "ProtectConfigurationId": settings.AWS_PINPOINT_PROTECT_ID,
        }
    )


async def send_voice_message(
    to_number: str,
    message: str,
    client: PinpointSMSVoiceV2Client,
    *,
    message_type: str = "TEXT",
    voice_id: str = "MATTHEW",
    dry_run: bool = False,
) -> dict | None:
    return await client.send_voice_message(
        **{
            "DestinationPhoneNumber": to_number,
            "OriginationIdentity": settings.AWS_PINPOINT_POOL_ARN,
            "MessageBody": message,
            "MessageBodyTextType": message_type,
            "VoiceId": voice_id,
            "ConfigurationSetName": settings.AWS_PINPOINT_CONFIGURATION_ARN,
            "MaxPricePerMinute": settings.AWS_PINPOINT_MAX_PRICE_VOICE,
            "DryRun": dry_run,
            "ProtectConfigurationId": settings.AWS_PINPOINT_PROTECT_ID,
        }
    )

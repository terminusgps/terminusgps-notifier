import asyncio
import logging

import aioboto3
from asgiref.sync import sync_to_async
from django.conf import ImproperlyConfigured, settings
from django.db.models import F
from django.http import HttpRequest, HttpResponse
from django.views.generic import View
from terminusgps.authorizenet.constants import SubscriptionStatus
from terminusgps.wialon.session import WialonSession
from terminusgps_notifications.models import (
    MessagePackage,
    TerminusgpsNotificationsCustomer,
    WialonToken,
)

from . import phones
from .forms import WialonUnitNotificationForm

logger = logging.getLogger(__name__)


REQUIRED_SETTINGS = [
    "AWS_PINPOINT_CONFIGURATION_ARN",
    "AWS_PINPOINT_MAX_PRICE_SMS",
    "AWS_PINPOINT_MAX_PRICE_VOICE",
    "AWS_PINPOINT_POOL_ARN",
    "AWS_PINPOINT_PROTECT_ID",
]

for setting in REQUIRED_SETTINGS:
    if not hasattr(settings, setting):
        raise ImproperlyConfigured(f"'{setting}' setting is required.")


def get_customer_from_user_id(
    user_id: str,
) -> TerminusgpsNotificationsCustomer | None:
    try:
        return TerminusgpsNotificationsCustomer.objects.get(
            user__id=int(user_id)
        )
    except TerminusgpsNotificationsCustomer.DoesNotExist:
        return


def get_token_from_user_id(user_id: str) -> str | None:
    try:
        customer = TerminusgpsNotificationsCustomer.objects.get(
            user__id=int(user_id)
        )
        return WialonToken.objects.get(customer=customer).name
    except (
        WialonToken.DoesNotExist,
        TerminusgpsNotificationsCustomer.DoesNotExist,
    ):
        return


def has_subscription(
    customer: TerminusgpsNotificationsCustomer | None = None,
) -> bool:
    if customer is None:
        return False
    return (
        customer.subscription.status == SubscriptionStatus.ACTIVE
        if customer.subscription is not None
        and hasattr(customer.subscription, "status")
        else False
    )


def has_messages(
    customer: TerminusgpsNotificationsCustomer | None = None,
) -> bool:
    if customer is None:
        return False
    if customer.messages_count <= customer.messages_max:
        return True
    packages = MessagePackage.objects.filter(customer=customer)
    if packages.count() > 0:
        for package in packages:
            if package.count <= package.max:
                return True
    return False


def increment_packages_message_count(
    customer: TerminusgpsNotificationsCustomer, num_messages: int
) -> TerminusgpsNotificationsCustomer:
    packages = MessagePackage.objects.filter(customer=customer)
    if packages.count() == 0:
        return customer
    for package in packages:
        if package.count >= package.max:
            continue
        else:
            package.count = F("count") + num_messages
            package.save(update_fields=["count"])
            break
    customer.refresh_from_db()
    return customer


def increment_customer_message_count(
    customer: TerminusgpsNotificationsCustomer, num_messages: int
) -> TerminusgpsNotificationsCustomer:
    if customer.messages_count < customer.messages_max:
        customer.messages_count = F("messages_count") + num_messages
        customer.save(update_fields=["messages_count"])
        customer.refresh_from_db()
    return customer


class HealthCheckView(View):
    content_type = "text/plain"
    http_method_names = ["get"]

    async def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Responds with status code 200."""
        return HttpResponse(b"I'm alive\n", status=200)


class DispatchNotificationView(View):
    content_type = "text/plain"
    http_method_names = ["get"]

    async def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """
        Dispatches a notification based on path parameters.

        Returns 200 if notifications were successfully dispatched.

        Returns 200 if the provided unit id didn't have attached phone numbers.

        Returns 406 if the unit id, user id, message or method was invalid.

        Returns 403 if the user id represents a non-existent user, a user without a subscription, a user with an inactive subscription or a user without a valid Wialon API token.

        """
        form = WialonUnitNotificationForm(request.GET)
        if not form.is_valid():
            return HttpResponse(b"Bad notification params\n", status=406)

        unit_id = str(form.cleaned_data["unit_id"])
        user_id = str(form.cleaned_data["user_id"])
        message = str(form.cleaned_data["message"])
        dry_run = bool(form.cleaned_data["dry_run"])
        customer = await sync_to_async(get_customer_from_user_id)(user_id)
        token = await sync_to_async(get_token_from_user_id)(user_id)
        has_sub = await sync_to_async(has_subscription)(customer)
        has_msgs = await sync_to_async(has_messages)(customer)
        if customer is None:
            return HttpResponse(b"Invalid customer\n", status=403)
        if token is None:
            return HttpResponse(b"Invalid Wialon API token\n", status=403)
        if not has_sub:
            return HttpResponse(
                b"Customer lacks a valid subscription\n", status=403
            )
        if not has_msgs:
            return HttpResponse(
                b"Customer lacks available messages\n", status=403
            )
        with WialonSession(token=token) as session:
            target_phones = await sync_to_async(
                phones.get_phone_numbers, thread_sensitive=True
            )(unit_id, session)
            if not target_phones:
                logger.info(f"No phones retrieved for #{unit_id}\n")
                return HttpResponse(status=200)

        try:
            method = str(self.kwargs["method"])
            message_ids = await asyncio.gather(
                *[
                    self.send_notification(phone, message, method, dry_run)
                    for phone in target_phones
                ]
            )
            logger.info(f"Sent messages: '{message_ids}'.")
            num_messages = len(target_phones)
            await sync_to_async(
                increment_customer_message_count, thread_sensitive=True
            )(customer, num_messages)
            logger.info(f"Incremented customer messages for '{customer}'.")
            await sync_to_async(
                increment_packages_message_count, thread_sensitive=True
            )(customer, num_messages)
            logger.info(f"Incremented packages messages for '{customer}'.")
            return HttpResponse(status=200)
        except ValueError:
            return HttpResponse(b"Bad notification method\n", status=406)

    async def send_notification(
        self, to_number: str, message: str, method: str, dry_run: bool = False
    ) -> dict[str, str] | None:
        """
        Sends a notification to ``to_number`` via ``method``.

        :param to_number: Destination (target) phone number.
        :type to_number: str
        :param message: Notification message.
        :type message: str
        :param method: Notification method. Options are ``sms`` or ``voice``.
        :type method: str
        :param dry_run: Whether to execute the API call as a dry run. Default is :py:obj:`False`.
        :type dry_run: bool
        :raises ValueError: If the method was invalid.
        :returns: A dictionary of message ids.
        :rtype: dict[str, str] | None

        """
        match method:
            case "sms":
                return await self._send_sms_message(
                    to_number, message, dry_run
                )
            case "voice":
                return await self._send_voice_message(
                    to_number, message, dry_run
                )
            case _:
                raise ValueError(f"Invalid method: '{method}'")

    async def _send_sms_message(
        self,
        to_number: str,
        message: str,
        ttl: int = 300,
        region_name: str = "us-east-1",
        dry_run: bool = False,
    ) -> dict[str, str] | None:
        """
        Sends ``message`` to ``to_number`` via sms.

        :param to_number: Destination phone number.
        :type to_number: str
        :param message: A message to deliver to the destination phone number via sms.
        :type message: str
        :param ttl: Time to live in seconds. Default is ``300`` seconds.
        :type ttl: int
        :param region_name: An AWS region to use for the message dispatch. Default is ``"us-east-1"``.
        :type region_name: str
        :param dry_run: Whether to execute the API call as a dry run. Default is :py:obj:`False`.
        :type dry_run: bool
        :returns: A dictionary containing the PinpointSMSVoiceV2 message id.
        :rtype: dict[str, str] | None

        """
        async with aioboto3.Session().client(
            "pinpoint-sms-voice-v2", region_name=region_name
        ) as client:
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

    async def _send_voice_message(
        self,
        to_number: str,
        message: str,
        message_type: str = "TEXT",
        voice_id: str = "MATTHEW",
        region_name: str = "us-east-1",
        dry_run: bool = False,
    ) -> dict[str, str] | None:
        """
        Sends ``message`` to ``to_number`` via voice.

        :param to_number: Destination phone number.
        :type to_number: str
        :param message: A message to read aloud to the destination phone number via voice.
        :type message: str
        :param message_type: An AWS End User Messaging message type. Default is ``"TEXT"``.
        :type message_type: str
        :param voice_id: An AWS End User Messaging synthetic voice id. Default is ``"MATTHEW"``.
        :type voice_id: str
        :param region_name: An AWS region to use for the message dispatch. Default is ``"us-east-1"``.
        :type region_name: str
        :param dry_run: Whether to execute the API call as a dry run. Default is :py:obj:`False`.
        :type dry_run: bool
        :returns: A dictionary containing the PinpointSMSVoiceV2 message id.
        :rtype: dict[str, str] | None

        """
        async with aioboto3.Session().client(
            "pinpoint-sms-voice-v2", region_name=region_name
        ) as client:
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

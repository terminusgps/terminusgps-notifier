import logging
from datetime import datetime
from functools import partial

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from django.db.models import F
from django.template.loader import render_to_string
from terminusgps.authorizenet.constants import SubscriptionStatus
from terminusgps.wialon import flags
from terminusgps.wialon.session import WialonAPIError, WialonSession
from terminusgps_notifications.models import (
    MessagePackage,
    TerminusgpsNotificationsCustomer,
)

logger = logging.getLogger(__name__)


def get_phone_numbers(unit_id: int, session: WialonSession) -> list[str]:
    """
    Returns a list of unit assigned phone numbers by id.

    :param unit_id: Wialon unit id.
    :type unit_id: int
    :param session: Active Wialon API session.
    :type session: ~terminusgps.wialon.session.WialonSession
    :returns: A list of phone numbers.
    :rtype: list[str]

    """
    driver_phones = cache.get_or_set(
        f"{unit_id}_get_driver_phone_numbers",
        partial(get_driver_phone_numbers, unit_id, session),
        timeout=60 * 15,
    )
    cfield_phones = cache.get_or_set(
        f"{unit_id}_get_cfield_phone_numbers",
        partial(get_cfield_phone_numbers, unit_id, session),
        timeout=60 * 15,
    )
    return list(frozenset(driver_phones + cfield_phones))


def get_driver_phone_numbers(
    unit_id: int, session: WialonSession
) -> list[str]:
    """
    Returns a list of the unit's attached driver phone numbers.

    :param unit_id: Wialon unit id.
    :type unit_id: int
    :param session: Active Wialon API session.
    :type session: ~terminusgps.wialon.session.WialonSession
    :returns: A list of phone numbers.
    :rtype: list[str]

    """
    logger.info(f"Retriving driver phones for unit #{unit_id}...")
    try:
        drivers = session.wialon_api.resource_get_unit_drivers(
            **{"unitId": unit_id}
        ).values()
        phones = [driver[0].get("ph") for driver in drivers]
        logger.debug(f"Driver phones retrieved for unit #{unit_id}: {phones}")
        return phones
    except WialonAPIError as e:
        logger.warning(e)
        return []


def get_cfield_phone_numbers(
    unit_id: int, session: WialonSession, cfield_key: str = "to_number"
) -> list[str]:
    """
    Returns a list of the unit's attached driver phone numbers.

    :param unit_id: Wialon unit id.
    :type unit_id: int
    :param session: Active Wialon API session.
    :type session: ~terminusgps.wialon.session.WialonSession
    :param cfield_key: Custom field key containing a comma-separated list of phone numbers. Default is :py:obj:`"to_number"`.
    :type cfield_key: str
    :param use_cache: Whether to use cached phones or force a Wialon API call. Default is :py:obj:`True`.
    :type use_cache: bool
    :returns: A list of phone numbers.
    :rtype: list[str]

    """
    logger.info(f"Retriving cfield phones for unit #{unit_id}...")
    try:
        response = session.wialon_api.core_search_item(
            **{"id": unit_id, "flags": flags.DataFlag.UNIT_CUSTOM_FIELDS}
        )["item"]
        if cfields := response.get("flds"):
            for cfield in cfields.values():
                if cfield["n"] == cfield_key:
                    phones = (
                        cfield["v"].split(",")
                        if "," in cfield["v"]
                        else [cfield["v"]]
                    )
                    logger.debug(
                        f"Cfield phones retrieved for unit #{unit_id}: {phones}"
                    )
                    return phones
        return []
    except WialonAPIError as e:
        logger.warning(e)
        return []


async def render_message(
    base: str,
    user_id: int,
    msg_time_int: int,
    *,
    location: str | None = None,
    unit_name: str | None = None,
) -> str:
    """
    Returns a rendered message to be delivered to a destination phone number.

    :param base: Base message.
    :type base: str
    :param user_id: A Django user id.
    :type user_id: int
    :param msg_time_int: Message date/time as a UNIX-timestamp.
    :type msg_time_int: int
    :param location: Location of the notification trigger. Default is :py:obj:`None`.
    :type location: str | None
    :param unit_name: Name of the triggering unit. Default is :py:obj:`None`.
    :type unit_name: str | None
    :returns: A constructed notification message.
    :rtype: str

    """
    date_format: str = await get_date_format(user_id)
    date: datetime = datetime.utcfromtimestamp(msg_time_int)
    return render_to_string(
        "terminusgps_notifier/message.txt",
        context={
            "date": date.strftime(date_format),
            "base": base,
            "location": location,
            "unit_name": unit_name,
        },
    ).removesuffix("\n")


async def get_customer(
    user_id: int,
) -> TerminusgpsNotificationsCustomer | None:
    """
    Returns a customer by id.

    :param user_id: Django user id.
    :type user_id: int
    :returns: A Terminus GPS Notifications customer, if found.
    :rtype: ~terminusgps_notifications.models.TerminusgpsNotificationsCustomer | None

    """
    try:
        return await TerminusgpsNotificationsCustomer.objects.aget(
            user__id=user_id
        )
    except TerminusgpsNotificationsCustomer.DoesNotExist:
        return


async def get_token(user_id: int) -> str | None:
    """
    Returns a customer's Wialon API token by id.

    :param user_id: Django user id.
    :type user_id: int
    :returns: A Wialon API token, if found.
    :rtype: str | None

    """
    if customer := await get_customer(user_id):
        if token := await sync_to_async(getattr)(customer, "token"):
            return await sync_to_async(getattr)(token, "name")


async def has_subscription(user_id: int) -> bool:
    """
    Returns whether a customer has a valid subscription.

    Returns :py:obj:`True` if the customer has a subscription with status 'active'.

    Returns :py:obj:`True` if the customer user is staff.

    Returns :py:obj:`False` in any other case.

    :param user_id: Django user id.
    :type user_id: int
    :returns: Whether the customer has a valid subscription.
    :rtype: bool

    """
    if customer := await get_customer(user_id):
        user = await sync_to_async(getattr)(customer, "user")
        subscription = await sync_to_async(getattr)(customer, "subscription")
        return (
            subscription.status == SubscriptionStatus.ACTIVE
            if subscription is not None
            else False
        ) or (user is not None and user.is_staff)
    return False


async def has_messages(user_id: int) -> bool:
    """
    Returns whether a customer has available messages.

    :param user_id: Django user id.
    :type user_id: int
    :returns: Whether the customer has available messages.
    :rtype: bool

    """
    if customer := await get_customer(user_id):
        if customer.messages_count < customer.messages_max:
            return True
        packages_qs = MessagePackage.objects.filter(customer=customer)
        if await packages_qs.acount() > 0:
            async for package in packages_qs:
                if package.count < package.max:
                    return True
    return False


async def increment_packages_message_count(
    user_id: int, num_messages: int
) -> None:
    """
    Adds ``num_messages`` to the first customer package with room.

    :param user_id: A Django user id.
    :type user_id: int
    :param num_messages: Number of messages to add.
    :type num_messages: int
    :returns: Nothing.
    :rtype: None

    """
    if customer := await get_customer(user_id):
        packages_qs = MessagePackage.objects.filter(customer=customer)
        if (
            customer.messages_count < customer.messages_max
            or await packages_qs.acount() <= 0
        ):
            return
        async for package in packages_qs:
            if package.count >= package.max:
                continue
            else:
                package.count = F("count") + num_messages
                await package.asave(update_fields=["count"])
                logger.info(
                    f"Incremented package messages for user #{user_id}"
                )
                break


async def increment_customer_message_count(
    user_id: int, num_messages: int
) -> None:
    """
    Adds ``num_messages`` to the customer's message count.

    :param user_id: A Django user id.
    :type user_id: int
    :param num_messages: Number of messages to add.
    :type num_messages: int
    :returns: Nothing.
    :rtype: None

    """
    if customer := await get_customer(user_id):
        if customer.messages_count < customer.messages_max:
            customer.messages_count = F("messages_count") + num_messages
            await customer.asave(update_fields=["messages_count"])
            logger.info(f"Incremented customer messages for user #{user_id}")


async def get_date_format(user_id: int) -> str:
    """
    Returns the date format for a customer.

    Default date format: '%Y-%m-%d %H:%M:%S'

    :param user_id: A Django user id.
    :type user_id: int
    :returns: A strftime format string.
    :rtype: str

    """
    if customer := await get_customer(user_id):
        return customer.date_format
    return "%Y-%m-%d %H:%M:%S"


async def send_sms_message(
    to_number: str,
    message: str,
    client,
    *,
    ttl: int = 300,
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
    :rtype: dict | None

    """
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
    client,
    *,
    message_type: str = "TEXT",
    voice_id: str = "MATTHEW",
    dry_run: bool = False,
) -> dict | None:
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
    :rtype: dict | None

    """
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


async def send_notification(
    to_number: str, message: str, method: str, client, dry_run: bool = False
) -> dict | None:
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
    :param client: An asyncronous boto3 AWS Pinpoint Messaging client.
    :raises ValueError: If the method was invalid.
    :returns: A dictionary of message ids.
    :rtype: dict[str, str] | None

    """
    logger.info(f"Sending '{message}' to '{to_number}' via {method}...")
    match method:
        case "sms":
            return await send_sms_message(
                to_number, message, client, dry_run=dry_run
            )
        case "voice":
            return await send_voice_message(
                to_number, message, client, dry_run=dry_run
            )
        case _:
            raise ValueError(f"Invalid method: '{method}'")

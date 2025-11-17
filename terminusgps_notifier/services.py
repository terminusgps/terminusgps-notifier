from django.core.cache import cache
from django.db.models import F
from terminusgps.authorizenet.constants import SubscriptionStatus
from terminusgps.wialon import flags
from terminusgps.wialon.session import WialonSession
from terminusgps_notifications.models import (
    MessagePackage,
    TerminusgpsNotificationsCustomer,
    WialonToken,
)


def get_phone_numbers(unit_id: str, session: WialonSession) -> list[str]:
    """
    Returns a list of unit assigned phone numbers by id.

    :param unit_id: Wialon unit id.
    :type unit_id: str
    :param session: Active Wialon API session.
    :type session: ~terminusgps.wialon.session.WialonSession
    :returns: A list of phone numbers.
    :rtype: list[str]

    """
    driver_phones = get_driver_phone_numbers(unit_id, session)
    cfield_phones = get_cfield_phone_numbers(unit_id, session)
    return list(frozenset(driver_phones + cfield_phones))


def get_driver_phone_numbers(
    unit_id: str, session: WialonSession
) -> list[str]:
    """
    Returns a list of the unit's attached driver phone numbers.

    :param unit_id: Wialon unit id.
    :type unit_id: str
    :param session: Active Wialon API session.
    :type session: ~terminusgps.wialon.session.WialonSession
    :returns: A list of phone numbers.
    :rtype: list[str]

    """
    cache_key = f"{unit_id}_get_driver_phone_numbers"
    if cached_driver_phones := cache.get(cache_key):
        return cached_driver_phones
    response = session.wialon_api.resource_get_unit_drivers(
        **{"unitId": unit_id}
    )
    phones = [driver[0].get("ph") for driver in response.values()]
    cache.set(cache_key, phones)
    return phones


def get_cfield_phone_numbers(
    unit_id: str, session: WialonSession, cfield_key: str = "to_number"
) -> list[str]:
    """
    Returns a list of the unit's attached driver phone numbers.

    :param unit_id: Wialon unit id.
    :type unit_id: str
    :param session: Active Wialon API session.
    :type session: ~terminusgps.wialon.session.WialonSession
    :param cfield_key: Custom field key containing a comma-separated list of phone numbers. Default is :py:obj:`"to_number"`.
    :type cfield_key: str
    :returns: A list of phone numbers.
    :rtype: list[str]

    """
    cache_key = f"{unit_id}_get_cfield_phone_numbers"
    if cached_cfield_phones := cache.get(cache_key):
        return cached_cfield_phones
    response = session.wialon_api.core_search_item(
        **{"id": unit_id, "flags": flags.DataFlag.UNIT_CUSTOM_FIELDS}
    )
    phones = []
    dirty_phones = [
        cfield["v"]
        for cfield in response["item"]["flds"].values()
        if cfield["n"] == cfield_key
    ]
    for num in dirty_phones:
        phones.extend(num.split(",")) if "," in num else phones.append(num)
    cache.set(cache_key, phones)
    return phones


async def get_customer_from_user_id(
    user_id: str,
) -> TerminusgpsNotificationsCustomer | None:
    """
    Returns a Terminus GPS Notifications customer by id.

    :param user_id: A Django user id.
    :type user_id: str
    :returns: A Terminus GPS Notifications customer, if found.
    :rtype: ~terminusgps_notifications.models.TerminusgpsNotificationsCustomer | None

    """
    try:
        return await TerminusgpsNotificationsCustomer.objects.aget(
            user__id=int(user_id)
        )
    except TerminusgpsNotificationsCustomer.DoesNotExist:
        return


async def get_token_from_user_id(user_id: str) -> str | None:
    """
    Returns a Terminus GPS Notifications customer's Wialon API token by id.

    :param user_id: A Django user id.
    :type user_id: str
    :returns: A Wialon API token, if found.
    :rtype: str | None

    """
    try:
        customer = await TerminusgpsNotificationsCustomer.objects.aget(
            user__id=int(user_id)
        )
        token = await WialonToken.objects.aget(customer=customer)
        return token.name
    except (
        WialonToken.DoesNotExist,
        TerminusgpsNotificationsCustomer.DoesNotExist,
    ):
        return


def has_subscription(
    customer: TerminusgpsNotificationsCustomer | None = None,
) -> bool:
    """
    Returns whether a Terminus GPS Notifications customer has a valid subscription.

    :param customer: A Terminus GPS Notifications customer. Default is :py:obj:`None` (probably not helpful).
    :type customer: ~terminusgps_notifications.models.TerminusgpsNotificationsCustomer | None
    :returns: Whether the customer has a valid subscription.
    :rtype: bool

    """
    if customer is None:
        return False
    return (
        customer.subscription.status == SubscriptionStatus.ACTIVE
        if customer.subscription is not None
        and hasattr(customer.subscription, "status")
        else False
    )


async def has_messages(
    customer: TerminusgpsNotificationsCustomer | None = None,
) -> bool:
    """
    Returns whether a Terminus GPS Notifications customer has available messages.

    :param customer: A Terminus GPS Notifications customer. Default is :py:obj:`None` (probably not helpful).
    :type customer: ~terminusgps_notifications.models.TerminusgpsNotificationsCustomer | None
    :returns: Whether the customer has available messages.
    :rtype: bool

    """
    if customer is None:
        return False
    if customer.messages_count <= customer.messages_max:
        return True

    packages_qs = MessagePackage.objects.filter(customer=customer)
    num_packages = await packages_qs.acount()
    if num_packages > 0:
        async for package in packages_qs:
            if package.count < package.max:
                return True
    return False


async def increment_packages_message_count(
    customer: TerminusgpsNotificationsCustomer, num_messages: int
) -> TerminusgpsNotificationsCustomer:
    """
    Adds ``num_messages`` to the first customer package with room before returning the customer.

    :param customer: A Terminus GPS Notifications customer.
    :type customer: ~terminusgps_notifications.models.TerminusgpsNotificationsCustomer
    :param num_messages: Number of messages to add.
    :type num_messages: int
    :returns: The Terminus GPS Notifications customer.
    :rtype: ~terminusgps_notifications.models.TerminusgpsNotificationsCustomer

    """
    packages_qs = MessagePackage.objects.filter(customer=customer)
    num_packages = await packages_qs.acount()
    if num_packages == 0 or customer.messages_count < customer.messages_max:
        return customer
    async for package in packages_qs:
        if package.count >= package.max:
            continue
        else:
            package.count = F("count") + num_messages
            await package.asave(update_fields=["count"])
            break
    await customer.arefresh_from_db()
    return customer


async def increment_customer_message_count(
    customer: TerminusgpsNotificationsCustomer, num_messages: int
) -> TerminusgpsNotificationsCustomer:
    """
    Adds ``num_messages`` to the customer's message count before returning it.

    :param customer: A Terminus GPS Notifications customer.
    :type customer: ~terminusgps_notifications.models.TerminusgpsNotificationsCustomer
    :param num_messages: Number of messages to add.
    :type num_messages: int
    :returns: The Terminus GPS Notifications customer.
    :rtype: ~terminusgps_notifications.models.TerminusgpsNotificationsCustomer

    """
    if customer.messages_count < customer.messages_max:
        customer.messages_count = F("messages_count") + num_messages
        await customer.asave(update_fields=["messages_count"])
        await customer.arefresh_from_db()
    return customer

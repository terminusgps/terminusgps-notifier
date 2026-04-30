import logging
import typing
from collections.abc import Sequence
from functools import partial

from django.core.cache import cache
from django.http.response import sync_to_async
from terminusgps.wialon import flags
from terminusgps.wialon.session import WialonAPIError, WialonSession

from .forms import NotificationDispatchForm

logger = logging.getLogger(__name__)


@sync_to_async
def get_notification_data(
    session: WialonSession,
    resource_id: int,
    notification_ids: Sequence[int] | None = None,
) -> list[dict]:
    params: dict[str, typing.Any] = {}
    params["itemId"] = resource_id
    if notification_ids is not None:
        params["col"] = notification_ids
    return session.wialon_api.resource_get_notification_data(**params)


@sync_to_async
def get_resource_data(
    session: WialonSession, resource_id: int, flags: int = 1025
) -> dict:
    params: dict[str, typing.Any] = {}
    params["id"] = resource_id
    params["flags"] = flags
    return session.wialon_api.core_search_item(**params)


@sync_to_async
def get_resources(
    session: WialonSession,
    force: bool = False,
    from_index: int = 0,
    to_index: int = 0,
    flags: int = 1025,
) -> dict:
    params: dict[str, typing.Any] = {"spec": {}}
    params["spec"]["itemsType"] = "avl_resource"
    params["spec"]["propName"] = "sys_name"
    params["spec"]["propValueMask"] = "*"
    params["spec"]["propType"] = "property"
    params["spec"]["sortType"] = "sys_name"
    params["force"] = int(force)
    params["from"] = from_index
    params["to"] = to_index
    params["flags"] = flags
    return session.wialon_api.core_search_items(**params)


@sync_to_async
def get_units(
    session: WialonSession,
    resource_id: int,
    force: bool = False,
    from_index: int = 0,
    to_index: int = 0,
    flags: int = 1,
) -> dict:
    params: dict[str, typing.Any] = {"spec": {}}
    params["spec"]["itemsType"] = "avl_unit"
    params["spec"]["propName"] = "sys_name,sys_billing_account_guid"
    params["spec"]["propValueMask"] = f"*,{resource_id}"
    params["spec"]["propType"] = "property,property"
    params["spec"]["sortType"] = "sys_name,sys_name"
    params["force"] = int(force)
    params["from"] = from_index
    params["to"] = to_index
    params["flags"] = flags
    return session.wialon_api.core_search_items(**params)


@sync_to_async
def get_unit_groups(
    session: WialonSession,
    resource_id: int,
    force: bool = False,
    from_index: int = 0,
    to_index: int = 0,
    flags: int = 1,
) -> list[dict]:
    params: dict[str, typing.Any] = {"spec": {}}
    params["spec"]["itemsType"] = "avl_unit_group"
    params["spec"]["propName"] = "sys_name,sys_billing_account_guid"
    params["spec"]["propValueMask"] = f"*,{resource_id}"
    params["spec"]["propType"] = "property,property"
    params["spec"]["sortType"] = "sys_name,sys_name"
    params["force"] = int(force)
    params["from"] = from_index
    params["to"] = to_index
    params["flags"] = flags
    return session.wialon_api.core_search_items(**params)


@sync_to_async
def get_phone_numbers(
    form: NotificationDispatchForm, session: WialonSession, timeout: int = 300
) -> list[str]:
    """
    Returns a list of unit assigned phone numbers by id.

    :param form: A Wialon notification dispatch form.
    :type form: ~terminusgps_notifier.forms.WialonNotificationDispatchForm
    :param session: Active Wialon API session.
    :type session: ~terminusgps.wialon.session.WialonSession
    :param timeout: Cache timeout in seconds. Default is ``300`` (5min).
    :type timeout: int
    :returns: A list of phone numbers.
    :rtype: list[str]

    """
    unit_id = form.cleaned_data["unit_id"]
    driver_phones = cache.get_or_set(
        f"{unit_id}_get_driver_phone_numbers",
        partial(get_driver_phone_numbers, unit_id, session),
        timeout=timeout,
    )
    cfield_phones = cache.get_or_set(
        f"{unit_id}_get_cfield_phone_numbers",
        partial(get_cfield_phone_numbers, unit_id, session),
        timeout=timeout,
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
    try:
        logger.debug(
            f"Calling the Wialon API to retrieve driver phones for unit #{unit_id}..."
        )
        drivers = session.wialon_api.resource_get_unit_drivers(
            **{"unitId": unit_id}
        )
        return (
            [driver[0].get("ph") for driver in drivers.values()]
            if drivers.values()
            else []
        )
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
    :returns: A list of phone numbers.
    :rtype: list[str]

    """
    try:
        logger.debug(
            f"Calling the Wialon API to retrieve cfield phones for unit #{unit_id}..."
        )
        search = session.wialon_api.core_search_item(
            **{"id": unit_id, "flags": flags.DataFlag.UNIT_CUSTOM_FIELDS}
        )
        if item := search.get("item"):
            if cfields := item.get("flds"):
                for cfield in cfields.values():
                    if cfield["n"] == cfield_key:
                        return (
                            cfield["v"].split(",")
                            if "," in cfield["v"]
                            else [cfield["v"]]
                        )
        return []
    except WialonAPIError as e:
        logger.warning(e)
        return []

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


def create_notification(
    session: WialonSession,
    resource_id: int,
    n: str,
    txt: str,
    ta: int,
    td: int,
    ma: int,
    mmtd: int,
    cdt: int,
    mast: int,
    mpst: int,
    cp: int,
    fl: int,
    tz: int,
    la: str,
    un: Sequence[int],
    sch: dict,
    ctrl_sch: dict,
    trg: dict,
    act: list[dict],
) -> dict:
    params: dict[str, typing.Any] = {}
    params["itemId"] = resource_id
    params["id"] = 0
    params["callMode"] = "create"
    params["n"] = n
    params["txt"] = txt
    params["ta"] = ta
    params["td"] = td
    params["ma"] = ma
    params["mmtd"] = mmtd
    params["cdt"] = cdt
    params["mast"] = mast
    params["mpst"] = mpst
    params["cp"] = cp
    params["fl"] = fl
    params["tz"] = tz
    params["la"] = la
    params["un"] = un
    params["sch"] = sch
    params["ctrl_sch"] = ctrl_sch
    params["trg"] = trg
    params["act"] = act
    print(f"{params = }")
    return session.wialon_api.resource_update_notification(**params)


def get_notification_data(
    session: WialonSession, resource_id: int, notification_ids: Sequence[int]
) -> dict:
    params: dict[str, typing.Any] = {}
    params["itemId"] = resource_id
    params["col"] = notification_ids
    return session.wialon_api.resource_get_notification_data(**params)


def search_item(session: WialonSession, id: int, flags: int = 1) -> dict:
    params: dict[str, typing.Any] = {}
    params["id"] = id
    params["flags"] = flags
    return session.wialon_api.core_search_item(**params)


def search_items(
    session: WialonSession,
    items_type: str,
    prop_name: str,
    prop_value_mask: str,
    sort_type: str,
    prop_type: str,
    or_logic: bool | None = None,
    force: bool = False,
    flags: int = 1,
    from_index: int = 0,
    to_index: int = 0,
) -> dict:
    params: dict[str, typing.Any] = {"spec": {}}
    params["spec"]["itemsType"] = items_type
    params["spec"]["propName"] = prop_name
    params["spec"]["propValueMask"] = prop_value_mask
    params["spec"]["sortType"] = sort_type
    params["spec"]["propType"] = prop_type
    if or_logic is not None:
        params["spec"]["or_logic"] = or_logic
    params["force"] = int(force)
    params["flags"] = flags
    params["from"] = from_index
    params["to"] = to_index
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
